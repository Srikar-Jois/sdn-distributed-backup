import json
import socket
import struct

BUFFER_SIZE = 64 * 1024
CHUNK_SIZE = 1024 * 1024
MAX_HEADER_SIZE = 64 * 1024


def recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Connection closed before receiving all data")
        data.extend(chunk)
    return bytes(data)


def send_json(sock, message):
    payload = json.dumps(message).encode("utf-8")
    if len(payload) > MAX_HEADER_SIZE:
        raise ValueError("JSON header too large")
    sock.sendall(struct.pack("!I", len(payload)) + payload)


def recv_json(sock):
    header_length = struct.unpack("!I", recv_exact(sock, 4))[0]
    if header_length <= 0 or header_length > MAX_HEADER_SIZE:
        raise ValueError("Invalid JSON header length")
    return json.loads(recv_exact(sock, header_length).decode("utf-8"))
