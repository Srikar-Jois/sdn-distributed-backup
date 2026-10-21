import hashlib
import os
import socket
import sys
import time
from pathlib import Path

from protocol import CHUNK_SIZE, recv_exact, recv_json, send_json

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while True:
            data = file.read(1024 * 1024)
            if not data:
                break
            digest.update(data)
    return digest.hexdigest()


def require_status(response, expected):
    if response.get("status") != expected:
        raise RuntimeError(response.get("message", f"Unexpected server response: {response}"))


def upload_file(path, host=DEFAULT_HOST, port=DEFAULT_PORT):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    size = path.stat().st_size
    digest = sha256_file(path)
    filename = path.name

    print(f"File: {filename}")
    print(f"Size: {size} bytes")
    print(f"SHA-256: {digest}")
    start_time = time.time()

    with socket.create_connection((host, port), timeout=30) as sock:
        sock.settimeout(300)
        send_json(sock, {
            "type": "UPLOAD",
            "filename": filename,
            "size": size,
            "sha256": digest,
        })

        response = recv_json(sock)
        require_status(response, "READY")
        offset = response.get("offset")
        chunk_size = response.get("chunk_size")

        if type(offset) is not int or not 0 <= offset <= size:
            raise RuntimeError("Server returned an invalid resume offset")
        if chunk_size != CHUNK_SIZE:
            raise RuntimeError("Client/server chunk size mismatch")

        if offset:
            print(f"Resuming from byte {offset} of {size}")

        with open(path, "rb") as file:
            file.seek(offset)

            while offset < size:
                data = file.read(min(CHUNK_SIZE, size - offset))
                if not data:
                    raise RuntimeError("Local file ended unexpectedly")

                send_json(sock, {
                    "type": "CHUNK",
                    "offset": offset,
                    "size": len(data),
                })
                sock.sendall(data)

                ack = recv_json(sock)
                require_status(ack, "ACK")
                offset = ack.get("offset")

                if type(offset) is not int or offset > size:
                    raise RuntimeError("Invalid acknowledgement from server")

                percent = 100 if size == 0 else offset * 100 / size
                print(f"\rTransferred {offset}/{size} bytes ({percent:.1f}%)", end="", flush=True)

        send_json(sock, {"type": "FINISH"})
        result = recv_json(sock)
        require_status(result, "COMPLETE")

    elapsed = max(time.time() - start_time, 0.000001)
    print(f"\nUpload complete: {result['filename']}")
    print(f"Elapsed: {elapsed:.2f} seconds")
    print(f"Throughput: {size / elapsed / (1024 * 1024):.2f} MiB/s")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3, 4):
        print("Usage: python3 client.py FILE [SERVER_IP [PORT]]")
        sys.exit(1)

    file_path = sys.argv[1]
    server_host = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_HOST
    server_port = int(sys.argv[3]) if len(sys.argv) == 4 else DEFAULT_PORT

    try:
        upload_file(file_path, server_host, server_port)
    except (OSError, ValueError, RuntimeError, ConnectionError) as exc:
        print(f"Upload failed: {exc}")
        sys.exit(1)
