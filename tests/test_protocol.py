import json
import socket
import struct
import threading
import unittest

from protocol import (
    send_json,
    recv_json,
    recv_exact,
    MAX_HEADER_SIZE,
)


class TestProtocol(unittest.TestCase):

    def test_json_round_trip(self):
        left, right = socket.socketpair()
        try:
            message = {
                "type": "UPLOAD",
                "filename": "sample.bin",
                "size": 1024,
                "sha256": "a" * 64,
            }
            send_json(left, message)
            self.assertEqual(recv_json(right), message)
        finally:
            left.close()
            right.close()

    def test_fragmented_message(self):
        left, right = socket.socketpair()
        message = {"type": "TEST", "value": 123}
        payload = json.dumps(message).encode("utf-8")
        packet = struct.pack("!I", len(payload)) + payload

        def send_fragments():
            try:
                for byte in packet:
                    left.sendall(bytes([byte]))
            finally:
                left.close()

        sender = threading.Thread(target=send_fragments)
        sender.start()
        try:
            self.assertEqual(recv_json(right), message)
        finally:
            right.close()
            sender.join()

    def test_recv_exact_incomplete_data(self):
        left, right = socket.socketpair()
        try:
            left.sendall(b"abc")
            left.close()
            with self.assertRaises(ConnectionError):
                recv_exact(right, 5)
        finally:
            right.close()

    def test_invalid_header_length(self):
        left, right = socket.socketpair()
        try:
            left.sendall(struct.pack("!I", MAX_HEADER_SIZE + 1))
            with self.assertRaises(ValueError):
                recv_json(right)
        finally:
            left.close()
            right.close()

    def test_invalid_json(self):
        left, right = socket.socketpair()
        try:
            payload = b"not-json"
            left.sendall(struct.pack("!I", len(payload)) + payload)
            with self.assertRaises(ValueError):
                recv_json(right)
        finally:
            left.close()
            right.close()


if __name__ == "__main__":
    unittest.main()
