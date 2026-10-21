# SDN-Based Distributed Backup System

A Python-based distributed backup system that transfers files to multiple backup nodes over a Software-Defined Networking (SDN) topology. The system supports chunked uploads, resumable transfers, SHA-256 integrity verification, and retries when a backup node is temporarily unavailable.

## Features

- Distributed file replication to multiple backup servers.
- Chunked file transfer using a JSON-based TCP protocol.
- Resumption of interrupted uploads.
- SHA-256 verification to detect corrupted transfers.
- Retry handling for temporarily unavailable backup nodes.
- OpenFlow 1.3 learning-switch controller.
- Mininet topology for testing SDN connectivity and backup-node failures.
- Automated unit and integration tests using pytest.

## Architecture

The topology contains three hosts and two switches:

- `h1` — client that uploads files.
- `h2` — backup node at `10.0.0.2`, port `9001`.
- `h3` — backup node at `10.0.0.3`, port `9002`.
- `s1`, `s2` — OpenFlow switches controlled by the SDN controller.

See [docs/architecture.md](docs/architecture.md) for details.

## Requirements

- Python 3
- Mininet and Open vSwitch
- An OpenFlow 1.3-compatible controller, using OS-Ken in this project
- pytest for automated testing

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
```

Install any additional dependencies required by your environment and the SDN controller.

## Run automated tests

From the repository root:

```bash
.venv/bin/python -m pytest -v
```

The current test suite contains nine tests covering protocol handling, uploads, replication, interrupted uploads, and integrity verification.

## Run the SDN topology

Start the SDN controller and Mininet topology according to your environment's OS-Ken and Mininet setup:

```bash
sudo python3 sdn_topology.py
```

Inside the Mininet CLI, test connectivity:

```text
pingall
```

Inspect OpenFlow 1.3 rules from a separate terminal:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
sudo ovs-ofctl -O OpenFlow13 dump-flows s2
```

## Backup server and client

The backup server accepts configuration through environment variables:

- `BACKUP_HOST` — address to bind to.
- `BACKUP_PORT` — TCP port.
- `BACKUP_DIR` — directory for received backups.

Example for a backup node:

```bash
BACKUP_HOST=127.0.0.1 BACKUP_PORT=9001 BACKUP_DIR=backups \
  .venv/bin/python -u server.py
```

Upload a file to one server:

```bash
.venv/bin/python client.py path/to/file.bin 127.0.0.1 9001
```

Replicate a file to multiple backup nodes:

```bash
.venv/bin/python distributed_client.py path/to/file.bin \
  10.0.0.2:9001 10.0.0.3:9002
```

The distributed client supports retry configuration through `BACKUP_RETRY_ATTEMPTS` and `BACKUP_RETRY_DELAY`, measured in attempts and seconds respectively.

## Project documentation

- [Architecture](docs/architecture.md)
- [Testing log](docs/testing-log.md)
- [Project report](docs/project-report.md)

## Limitations and future work

Potential improvements include authenticated clients, encrypted transport, persistent job tracking, stronger concurrent-upload coordination, monitoring, and more extensive automated network-failure tests.
