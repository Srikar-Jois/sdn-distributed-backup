# Testing Log

## 1. Automated tests

Command:

```bash
.venv/bin/python -m pytest -v
```

Latest recorded result: **9 passed** in approximately 0.57 seconds.

### Integration tests

| Test | Purpose | Result |
|---|---|---|
| `test_upload_and_sha256_verification` | Upload a file and compare the stored file's SHA-256 digest with the source | PASS |
| `test_replication_to_two_servers` | Upload to two independent backup servers and verify both copies | PASS |
| `test_interrupted_upload_resumes` | Interrupt a transfer after a chunk acknowledgement and resume it | PASS |
| `test_corrupted_payload_is_rejected` | Send bytes that do not match the declared digest and check that finalization is rejected | PASS |

### Protocol unit tests

| Test | Purpose | Result |
|---|---|---|
| `test_fragmented_message` | Handle a message arriving in fragments | PASS |
| `test_invalid_header_length` | Reject an invalid message length | PASS |
| `test_invalid_json` | Reject malformed JSON | PASS |
| `test_json_round_trip` | Verify JSON message encoding and decoding | PASS |
| `test_recv_exact_incomplete_data` | Handle incomplete data when reading an exact byte count | PASS |

## 2. SDN connectivity

The Mininet topology's `pingall` test reported **0% packet loss (6/6 received)**. OpenFlow 1.3 flow-table dumps from switches `s1` and `s2` showed learned forwarding rules and a lower-priority controller action.

## 3. Manual replication test

The distributed client uploaded a test file to both backup nodes. The resulting files were checked against the source using SHA-256, and replication succeeded on both nodes.

## 4. Manual failure test

One backup server was stopped while the other remained available. The distributed client reported one successful node and one failed node, demonstrating that it records partial success rather than incorrectly reporting that every replica was created.

## 5. Manual recovery test

The client was configured to retry while one backup server was unavailable. The server was restarted during the retry period, and a later attempt succeeded. The final client summary reported success on both nodes.

## 6. Permanent outage test

With one backup server unavailable and retries limited to three attempts, the distributed client reported one successful node and one failed node. This was the expected result for a permanent outage during that test.

## 7. Overall result

The recorded automated and manual tests support the core project requirements: SDN connectivity, multi-node replication, interrupted-upload resumption, content-integrity checks, and reporting/retrying around unavailable backup nodes.

These results apply to the tested environment and scenarios; they do not establish production-scale performance or security.

## SDN failover and performance test

- Automated tests: 9 passed.
- Normal-network uploads: 1 MiB, 5 MiB, and 10 MiB files uploaded to both backup servers.
- Link-failure test: primary inter-switch link disabled at both ends; the redundant path remained available.
- Ping result: 497 received out of 497 transmitted, 0% packet loss; average RTT 0.119 ms.
- During-failure transfer: 5 MiB file successfully replicated to both servers; SHA-256 checksums matched.
- Throughput and elapsed-time samples: `benchmarks/benchmark_results.csv`.
- Detailed ping result: `benchmarks/failover_test.txt`.
- Recovery-time measurement: `benchmarks/failover_recovery_measurement.txt` records an observed ICMP recovery interval of 0.001572 seconds (1.572 ms). This is the measured interval defined by the script, not the switch's internal processing latency.

## Latest SDN fast-failover verification

- Automated tests: 9 passed.
- OpenFlow group verification: both `s1` and `s2` reported `type=ff` groups with primary and backup buckets.
- Failure procedure: disabled the primary inter-switch link at both ends (`s1-eth2` and `s2-eth1`), leaving the redundant link available.
- Connectivity during failure: `h1` pinged backup server `10.0.0.2`; 5 packets transmitted, 5 received, 0% packet loss. Reported average RTT was 0.479 ms.
- Recovery measurement: observed ICMP recovery interval of 1.572 ms, as recorded in `benchmarks/failover_recovery_measurement.txt`.
- Recovery: primary interfaces restored to the up state.
- Performance measurements and graph: see the existing benchmark results and graph files in the repository.
- Scope: this verifies failure-based fast failover; it does not demonstrate adaptive path selection based on throughput or latency.
