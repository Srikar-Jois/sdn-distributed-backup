
import os
import sys
import time

from client import upload_file


RETRY_ATTEMPTS = int(os.getenv("BACKUP_RETRY_ATTEMPTS", "12"))
RETRY_DELAY = float(os.getenv("BACKUP_RETRY_DELAY", "5"))


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python3 distributed_client.py "
            "FILE HOST:PORT [HOST:PORT ...]"
        )
        sys.exit(1)

    if RETRY_ATTEMPTS < 1 or RETRY_DELAY < 0:
        print("Retry attempts must be >= 1 and delay must be >= 0")
        sys.exit(1)

    path = sys.argv[1]
    nodes = []

    for node in sys.argv[2:]:
        try:
            host, port = node.rsplit(":", 1)
            port = int(port)

            if not host or not 1 <= port <= 65535:
                raise ValueError

            nodes.append((host, port))
        except ValueError:
            print(f"Invalid node address: {node}")
            sys.exit(1)

    successes = []
    failures = []

    for host, port in nodes:
        address = f"{host}:{port}"
        print(f"\n=== Replicating to {address} ===")

        success = False

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            if attempt > 1:
                print(
                    f"Retrying {address} "
                    f"(attempt {attempt}/{RETRY_ATTEMPTS})..."
                )

            try:
                upload_file(path, host, port)
                successes.append(address)
                success = True
                break
            except Exception as exc:
                print(
                    f"Attempt {attempt}/{RETRY_ATTEMPTS} "
                    f"failed on {address}: {exc}"
                )

                if attempt < RETRY_ATTEMPTS:
                    print(f"Waiting {RETRY_DELAY:g} seconds before retry...")
                    time.sleep(RETRY_DELAY)

        if not success:
            failures.append(address)
            print(f"Giving up on {address} after {RETRY_ATTEMPTS} attempts.")

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

