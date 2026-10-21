import hashlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from client import upload_file
from protocol import CHUNK_SIZE, recv_json, send_json

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


@pytest.fixture
def server_factory(tmp_path):
    processes = []

    def start_server(name):
        backup_dir = tmp_path / name
        backup_dir.mkdir()

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        env = os.environ.copy()
        env.update({
            "BACKUP_HOST": "127.0.0.1",
            "BACKUP_PORT": str(port),
            "BACKUP_DIR": str(backup_dir),
        })

        process = subprocess.Popen(
            [PYTHON, "-u", "server.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append(process)

        for _ in range(100):
            if process.poll() is not None:
                pytest.fail("Backup server exited during startup")

            try:
                with socket.create_connection(
                    ("127.0.0.1", port), timeout=0.2
                ):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            pytest.fail("Backup server did not start")

        return port, backup_dir

    yield start_server

    for process in processes:
        process.terminate()

    for process in processes:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def test_upload_and_sha256_verification(tmp_path, server_factory):
    port, backup_dir = server_factory("node1")
    source = tmp_path / "sample.bin"
    source.write_bytes(os.urandom(200_000))

    upload_file(source, "127.0.0.1", port)

    destination = backup_dir / source.name
    assert destination.exists()
    assert hashlib.sha256(destination.read_bytes()).digest() == (
        hashlib.sha256(source.read_bytes()).digest()
    )


def test_replication_to_two_servers(tmp_path, server_factory):
    port1, dir1 = server_factory("node1")
    port2, dir2 = server_factory("node2")
    source = tmp_path / "replica.bin"
    source.write_bytes(os.urandom(150_000))

    upload_file(source, "127.0.0.1", port1)
    upload_file(source, "127.0.0.1", port2)

    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    assert hashlib.sha256((dir1 / source.name).read_bytes()).hexdigest() == expected
    assert hashlib.sha256((dir2 / source.name).read_bytes()).hexdigest() == expected


def test_interrupted_upload_resumes(tmp_path, server_factory):
    port, backup_dir = server_factory("resume-node")
    source = tmp_path / "large.bin"
    source.write_bytes(os.urandom(CHUNK_SIZE + 100_000))

    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    with socket.create_connection(("127.0.0.1", port)) as sock:
        send_json(sock, {
            "type": "UPLOAD",
            "filename": source.name,
            "size": source.stat().st_size,
            "sha256": digest,
        })

        ready = recv_json(sock)
        assert ready["status"] == "READY"
        assert ready["offset"] == 0

        with source.open("rb") as file:
            chunk = file.read(CHUNK_SIZE)

        send_json(sock, {
            "type": "CHUNK",
            "offset": 0,
            "size": len(chunk),
        })
        sock.sendall(chunk)

        ack = recv_json(sock)
        assert ack["status"] == "ACK"
        assert ack["offset"] == CHUNK_SIZE

    # Closing the connection simulates an interrupted upload.
    time.sleep(0.1)

    upload_file(source, "127.0.0.1", port)

    destination = backup_dir / source.name
    assert destination.read_bytes() == source.read_bytes()


def test_corrupted_payload_is_rejected(tmp_path, server_factory):
    port, backup_dir = server_factory("corrupt-node")

    original = b"A" * 4096
    corrupted = b"B" * 4096
    digest = hashlib.sha256(original).hexdigest()

    with socket.create_connection(("127.0.0.1", port)) as sock:
        send_json(sock, {
            "type": "UPLOAD",
            "filename": "corrupt.bin",
            "size": len(original),
            "sha256": digest,
        })

        ready = recv_json(sock)
        assert ready["status"] == "READY"

        send_json(sock, {
            "type": "CHUNK",
            "offset": 0,
            "size": len(corrupted),
        })
        sock.sendall(corrupted)

        ack = recv_json(sock)
        assert ack["status"] == "ACK"

        send_json(sock, {"type": "FINISH"})
        response = recv_json(sock)

        assert response["status"] == "ERROR"
        assert "SHA-256" in response["message"]

    assert not (backup_dir / "corrupt.bin").exists()
