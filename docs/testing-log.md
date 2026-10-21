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
