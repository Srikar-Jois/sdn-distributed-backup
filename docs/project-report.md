# SDN-Based Distributed Backup System

## Abstract

This project implements a distributed file backup system over a Software-Defined Networking (SDN) test network. A client transfers files to multiple backup servers using a custom TCP protocol. The application supports chunked transfers, resumption after interrupted connections, SHA-256 integrity verification, and retries when a backup node is unavailable. A Mininet topology and an OpenFlow 1.3 learning-switch controller provide the network environment for testing.

## 1. Problem statement

A file stored on only one machine can become unavailable if that machine fails or loses its data. Maintaining copies on multiple backup nodes can improve availability, but the system must also handle interrupted transfers, detect corrupted files, and report failures when a backup destination cannot be reached.

This project explores a small distributed backup system and tests its behavior under normal operation and selected node-failure scenarios.

## 2. Objectives

- Transfer files from a client to multiple backup nodes.
- Divide file transfers into manageable chunks.
- Resume an interrupted transfer from a recorded offset.
- Verify the completed file using SHA-256.
- Retry uploads when a destination is temporarily unavailable.
- Use an SDN-controlled Mininet topology to validate network connectivity.
- Test protocol and application behavior using automated tests.

## 3. Technologies used

- Python 3 for the backup client, server, protocol, and controller application.
- TCP sockets for file transfer.
- JSON messages with length-prefix framing.
- SHA-256 for file-integrity verification.
- OS-Ken and OpenFlow 1.3 for SDN control.
- Mininet and Open vSwitch for network emulation.
- pytest for automated testing.

## 4. System design

The virtual network contains client host `h1` (`10.0.0.1`), backup host `h2` (`10.0.0.2`), backup host `h3` (`10.0.0.3`), and switches `s1` and `s2`.

The client computes a file's size and SHA-256 digest, then initiates an upload. The server responds with an upload offset so that an existing partial transfer can continue. The client sends chunks and waits for acknowledgements. After all data is transferred, the server verifies the final size and digest before accepting the file as complete.

The distributed client repeats this process for each requested backup endpoint. Its summary distinguishes successful nodes from failed nodes. Configurable retries allow a destination to recover during an upload attempt sequence.

## 5. Implementation

### 5.1 Message protocol

The protocol module frames JSON messages with a four-byte length prefix. This allows the receiver to determine where a message ends despite TCP delivering data in arbitrary-sized segments. The implementation also validates header lengths and handles incomplete reads.

### 5.2 Chunked and resumable transfer

Files are transferred in chunks of up to 1 MiB. The server acknowledges accepted chunks and tracks the transfer offset. When a connection is interrupted, a later client attempt can request the current offset and continue rather than necessarily retransmitting the entire file.

### 5.3 Integrity verification

The client supplies a SHA-256 digest for the original file. The server verifies the completed content against that digest and the expected size. A payload that does not match the expected digest is rejected at finalization.

### 5.4 Distributed replication and retries

The distributed client accepts multiple `HOST:PORT` endpoints and attempts each node independently. Retry count and delay are configurable through environment variables. The summary makes partial success visible if one node succeeds while another remains unavailable.

### 5.5 SDN network

The Mininet topology connects the client and backup nodes through two OpenFlow switches. The OS-Ken controller implements learning-switch behavior using OpenFlow 1.3. The topology is used to test host connectivity and inspect switch flow tables.

## 6. Testing and results

### Automated testing

The full pytest suite completed with **9 passed**:

- Four integration tests for upload integrity, two-node replication, interrupted-upload resumption, and corrupted-payload rejection.
- Five protocol unit tests for fragmented messages, invalid header lengths, malformed JSON, JSON round trips, and incomplete reads.

### SDN connectivity

Mininet `pingall` reported 0% packet loss, with all six host-to-host ping checks succeeding. Flow-table inspection on `s1` and `s2` showed learned forwarding entries and controller actions.

### Failure and recovery scenarios

Manual tests demonstrated that:
- Both backup nodes could receive a file, with stored copies matching the source digest.
- When one node was stopped, the client reported the successful node separately from the failed node.
- Restarting an unavailable node during the retry window allowed a later attempt to succeed.
- A node that remained unavailable was reported as failed after the configured retry attempts.

These tests validate the implemented behavior for the scenarios exercised; they are not a guarantee against every possible network or storage failure.

## 7. Limitations

- The current project is a prototype rather than a production backup service.
- SHA-256 verification does not authenticate clients or encrypt traffic.
- Backup availability still depends on the number of reachable and healthy nodes.
- Concurrent uploads of identical content and conflicting filenames require further coordination and testing.
- Monitoring, long-term backup retention, deletion policies, and administrative controls are outside the current core implementation.
- Large-scale throughput and performance have not been comprehensively benchmarked.

## 8. Future improvements

- Add TLS and client authentication.
- Improve coordination for concurrent uploads and partial-upload cleanup.
- Add structured logs, metrics, and a monitoring interface.
- Add automated tests for server crashes, disk errors, concurrent uploads, and larger files.
- Evaluate throughput and recovery behavior under different network conditions.
- Add configurable retention, backup listing, and restore operations.

## 9. Conclusion

The project demonstrates a working prototype of distributed file backup over an SDN-managed virtual network. The implementation combines chunked transfer, resumability, SHA-256 verification, multi-node uploads, and retry-based failure handling. Automated tests and Mininet experiments passed for the documented scenarios, providing a foundation for further reliability, security, and performance improvements.

## SDN Failover and Performance Evaluation

### Normal-network throughput

Files of 1 MiB, 5 MiB, and 10 MiB were uploaded to both backup servers through Mininet. All six uploads completed successfully.

| File size | h2 throughput | h3 throughput |
|---:|---:|---:|
| 1 MiB | 33.16 MiB/s | 51.30 MiB/s |
| 5 MiB | 47.45 MiB/s | 42.23 MiB/s |
| 10 MiB | 34.92 MiB/s | 31.43 MiB/s |

### Link failure and recovery

The primary inter-switch link was disabled at both ends while the redundant link remained available. A timestamped ping test to h2 received 497 of 497 packets, reporting 0% packet loss, average RTT of 0.119 ms, and maximum RTT of 2.331 ms. A separate 5 MiB upload test during link failure successfully replicated the file to both backup servers with matching SHA-256 checksums.

The ping log did not record the exact link-toggle timestamps, so an exact failover recovery duration cannot be derived from that run.

### Limitations

Throughput values are single-run measurements from a virtualized Mininet environment. They demonstrate successful transfers and provide an initial performance baseline, but are not repeated-trial averages or a controlled comparison of all possible network conditions. Raw measurements are in `benchmarks/benchmark_results.csv`.
