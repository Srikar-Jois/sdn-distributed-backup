# System Architecture

## 1. Overview

The project combines a TCP-based distributed backup application with an SDN-managed virtual network. The client sends a file to multiple backup servers. The servers store the received file and verify its contents using SHA-256.

## 2. Network topology

```text
                 SDN Controller
                       |
                  OpenFlow 1.3
                       |
          h1 ---- s1 ------- s2 ---- h2
         Client             |       Backup 1
                            |
                            +------- h3
                                    Backup 2
```

The Mininet topology uses:

| Component | Role | Address / interface |
|---|---|---|
| h1 | Backup client | 10.0.0.1 |
| h2 | Backup server 1 | 10.0.0.2 |
| h3 | Backup server 2 | 10.0.0.3 |
| s1 | OpenFlow switch | Connects h1 to the network |
| s2 | OpenFlow switch | Connects the backup hosts |

The controller implements a learning-switch application using OpenFlow 1.3. Connectivity and flow-table entries were verified during testing.

## 3. Application components

### `protocol.py`

Implements message framing for TCP communication. Each JSON message is prefixed with a four-byte length field. The receiver reads the specified number of bytes, allowing it to handle fragmented TCP messages. The module defines a 1 MiB chunk size and a maximum JSON header size of 64 KiB.

### `client.py`

Connects to a backup server, calculates the source file's SHA-256 digest, sends upload metadata, transfers chunks, and follows server acknowledgements. It can continue from a server-provided offset when a partial upload already exists.

### `server.py`

Accepts client connections and stores incoming files in the configured backup directory. It tracks partial uploads, acknowledges received chunks, and checks the completed file's size and SHA-256 digest before placing it at the final destination.

### `distributed_client.py`

Attempts to upload the same file to each specified backup endpoint. It supports configurable retries and reports which nodes succeeded or failed. Its exit status indicates whether all requested nodes succeeded.

### `sdn_controller.py`

Implements the SDN learning-switch logic using OS-Ken and OpenFlow 1.3. The switches initially send unknown traffic to the controller; learned forwarding rules allow subsequent traffic to be forwarded based on observed addresses.

### `sdn_topology.py`

Defines the Mininet network used to test connectivity between the client and two backup hosts.

## 4. Upload protocol

At a high level, an upload follows these steps:

1. The client calculates the file size and SHA-256 digest.
2. The client sends an `UPLOAD` message with the filename, size, and digest.
3. The server responds with a `READY` message and the current upload offset.
4. The client sends file chunks with their offsets and lengths.
5. The server acknowledges accepted chunks.
6. The client sends `FINISH` after all bytes have been transferred.
7. The server checks the completed file's size and digest and reports success or an error.

The transfer uses TCP for reliable byte delivery. Chunk-level acknowledgements and persisted partial data provide application-level progress tracking and resumption.

## 5. Failure handling

If a client disconnects during an upload, the partial data and associated metadata can be used to resume the transfer. If a backup node is unavailable, the distributed client retries according to its configured policy and reports the final outcome for each node.

The system can still report a successful backup to one node when another node is unavailable. This does not mean every requested replica was created; the per-node summary must be checked.

## 6. Integrity and security considerations

SHA-256 is used to detect accidental or malicious changes to file contents relative to the digest supplied by the client. It does not authenticate the client or protect the network connection from eavesdropping or tampering. Production use should add authentication and encrypted transport, as well as appropriate access controls on backup directories.
