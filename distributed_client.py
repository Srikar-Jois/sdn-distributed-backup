import sys
from client import upload_file


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 distributed_client.py FILE HOST:PORT [HOST:PORT ...]")
        sys.exit(1)

    path = sys.argv[1]
    nodes = []

    for node in sys.argv[2:]:
        try:
            host, port = node.rsplit(":", 1)
            nodes.append((host, int(port)))
        except ValueError:
            print(f"Invalid node address: {node}")
            sys.exit(1)

    successes = []
    failures = []

    for host, port in nodes:
        print(f"\n=== Replicating to {host}:{port} ===")
        try:
            upload_file(path, host, port)
            successes.append(f"{host}:{port}")
        except Exception as exc:
            print(f"Replication failed on {host}:{port}: {exc}")
            failures.append(f"{host}:{port}")

    print("\n=== DISTRIBUTED BACKUP SUMMARY ===")
    print(f"Successful nodes: {len(successes)}/{len(nodes)}")
    for node in successes:
        print(f"  OK: {node}")
    for node in failures:
        print(f"  FAILED: {node}")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
