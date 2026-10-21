import hashlib
import json
import os
import socket
import threading
from pathlib import Path

from protocol import CHUNK_SIZE, recv_exact, recv_json, send_json

HOST = os.environ.get("BACKUP_HOST", "0.0.0.0")
PORT = int(os.environ.get("BACKUP_PORT", "9000"))
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "backups")).resolve()
PARTIAL_DIR = BACKUP_DIR / ".partial"
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while True:
            data = file.read(1024 * 1024)
            if not data:
                break
            digest.update(data)
    return digest.hexdigest()


def send_error(conn, message):
    try:
        send_json(conn, {"status": "ERROR", "message": str(message)})
    except (OSError, ConnectionError, ValueError):
        pass


def handle_client(conn, address):
    try:
        with conn:
            conn.settimeout(300)
            request = recv_json(conn)

            if request.get("type") != "UPLOAD":
                send_error(conn, "Expected UPLOAD request")
                return

            filename = request.get("filename")
            size = request.get("size")
            digest = request.get("sha256")

            if (
                not isinstance(filename, str)
                or not filename
                or filename in {".", ".."}
                or Path(filename).name != filename
                or "/" in filename
                or "\\" in filename
            ):
                send_error(conn, "Invalid filename")
                return

            if type(size) is not int or not 0 <= size <= MAX_FILE_SIZE:
                send_error(conn, "Invalid file size")
                return

            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest.lower())
            ):
                send_error(conn, "Invalid SHA-256")
                return

            digest = digest.lower()
            PARTIAL_DIR.mkdir(parents=True, exist_ok=True)
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)

            part_path = PARTIAL_DIR / f"{digest}.part"
            manifest_path = PARTIAL_DIR / f"{digest}.json"
            manifest = {
                "filename": filename,
                "size": size,
                "sha256": digest,
                "chunk_size": CHUNK_SIZE,
            }

            if manifest_path.exists():
                try:
                    existing = json.loads(manifest_path.read_text())
                except (OSError, json.JSONDecodeError):
                    send_error(conn, "Partial-upload manifest is corrupt")
                    return
                if existing != manifest:
                    send_error(conn, "Upload metadata does not match saved partial")
                    return
            else:
                if part_path.exists():
                    send_error(conn, "Partial file exists without a manifest")
                    return
                temp_manifest = manifest_path.with_suffix(".json.tmp")
                temp_manifest.write_text(json.dumps(manifest))
                os.replace(temp_manifest, manifest_path)

            if part_path.exists():
                offset = part_path.stat().st_size
                if offset > size:
                    send_error(conn, "Saved partial is larger than expected")
                    return
                aligned_offset = (offset // CHUNK_SIZE) * CHUNK_SIZE
                if offset != aligned_offset and offset != size:
                    with open(part_path, "r+b") as partial:
                        partial.truncate(aligned_offset)
                        partial.flush()
                        os.fsync(partial.fileno())
                    offset = aligned_offset
            else:
                offset = 0

            send_json(conn, {
                "status": "READY",
                "offset": offset,
                "chunk_size": CHUNK_SIZE,
            })

            with open(part_path, "r+b" if part_path.exists() else "wb") as partial:
                partial.seek(offset)

                while True:
                    message = recv_json(conn)
                    message_type = message.get("type")

                    if message_type == "CHUNK":
                        chunk_offset = message.get("offset")
                        chunk_size = message.get("size")
                        expected_size = min(CHUNK_SIZE, size - offset)

                        if (
                            type(chunk_offset) is not int
                            or type(chunk_size) is not int
                            or chunk_offset != offset
                            or chunk_size != expected_size
                            or chunk_size <= 0
                        ):
                            send_error(conn, "Invalid chunk offset or size")
                            return

                        data = recv_exact(conn, chunk_size)
                        partial.write(data)
                        partial.flush()
                        os.fsync(partial.fileno())
                        offset += chunk_size

                        send_json(conn, {
                            "status": "ACK",
                            "offset": offset,
                        })

                    elif message_type == "FINISH":
                        if offset != size:
                            send_error(conn, f"Incomplete upload: {offset}/{size} bytes")
                            return
                        break
                    else:
                        send_error(conn, "Unknown transfer message")
                        return

            if part_path.stat().st_size != size or sha256_file(part_path) != digest:
                send_error(conn, "Final size or SHA-256 verification failed")
                return

            destination = BACKUP_DIR / filename
            os.replace(part_path, destination)
            manifest_path.unlink(missing_ok=True)

            send_json(conn, {
                "status": "COMPLETE",
                "filename": filename,
                "size": size,
                "sha256": digest,
            })
            print(f"[OK] {address}: saved {destination} ({size} bytes)")

    except (ConnectionError, ConnectionResetError, BrokenPipeError, socket.timeout) as exc:
        print(f"[INTERRUPTED] {address}: {exc}. Partial upload retained.")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {address}: {exc}")
        send_error(conn, exc)


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    PARTIAL_DIR.mkdir(parents=True, exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        print(f"Backup server listening on {HOST}:{PORT}")
        print(f"Files will be saved in: {BACKUP_DIR}")
        print(f"Partial uploads and manifests: {PARTIAL_DIR}")

        while True:
            conn, address = server.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, address),
                daemon=True,
            ).start()


if __name__ == "__main__":
    main()
