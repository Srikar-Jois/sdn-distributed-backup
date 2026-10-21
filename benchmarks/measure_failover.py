import queue
import re
import threading
import time
from pathlib import Path

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.log import setLogLevel


class BackupTopo(Topo):
    def build(self):
        s1 = self.addSwitch("s1", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", protocols="OpenFlow13")
        h1 = self.addHost(
            "h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01"
        )
        h2 = self.addHost(
            "h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02"
        )
        h3 = self.addHost(
            "h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03"
        )
        self.addLink(h1, s1)
        self.addLink(s1, s2)
        self.addLink(s1, s2)
        self.addLink(h2, s2)
        self.addLink(h3, s2)


def main():
    output = Path("benchmarks/failover_recovery_measurement.txt")
    output.parent.mkdir(exist_ok=True)

    net = Mininet(
        topo=BackupTopo(),
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=True,
    )
    net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653,
    )

    ping = None
    reader = None
    events = queue.Queue()
    lines = []

    try:
        net.start()
        time.sleep(3)

        h1 = net.get("h1")
        s1 = net.get("s1")
        s2 = net.get("s2")

        ping = h1.popen(
            ["ping", "-D", "-n", "-i", "0.02", "-W", "1", "10.0.0.2"],
            stdout=-1,
            stderr=-2,
            text=True,
            bufsize=1,
        )

        def read_ping():
            for line in ping.stdout:
                events.put(line)

        reader = threading.Thread(target=read_ping, daemon=True)
        reader.start()

        success_re = re.compile(r"^\[(\d+(?:\.\d+)?)\].*bytes from")
        baseline = 0
        deadline = time.monotonic() + 10

        while baseline < 3 and time.monotonic() < deadline:
            try:
                line = events.get(timeout=0.5)
            except queue.Empty:
                continue
            match = success_re.search(line)
            if match:
                baseline += 1

        if baseline < 3:
            raise RuntimeError("Ping did not establish baseline connectivity.")

        lines.append(f"Baseline successful replies: {baseline}")

        # Disable both ends of the primary inter-switch link.
        s1.cmd("ip link set s1-eth2 down")
        s2.cmd("ip link set s2-eth1 down")
        disabled_at = time.time()
        lines.append(f"Primary link disable completed (epoch): {disabled_at:.6f}")

        first_reply = None
        deadline = time.monotonic() + 10

        while time.monotonic() < deadline:
            try:
                line = events.get(timeout=0.5)
            except queue.Empty:
                continue

            match = success_re.search(line)
            if match:
                timestamp = float(match.group(1))
                if timestamp >= disabled_at:
                    first_reply = timestamp
                    break

        if first_reply is None:
            lines.append("Recovery time: NOT MEASURED — no successful reply within 10 seconds.")
            raise RuntimeError(lines[-1])

        recovery = max(0.0, first_reply - disabled_at)
        lines.append(f"First successful reply timestamp (epoch): {first_reply:.6f}")
        lines.append(f"Observed ICMP recovery interval (seconds): {recovery:.6f}")
        lines.append(
            "Definition: interval from completion of both link-disable commands "
            "to the timestamp of the first successful ping reply."
        )

        # Restore the primary link.
        s1.cmd("ip link set s1-eth2 up")
        s2.cmd("ip link set s2-eth1 up")
        time.sleep(2)
        lines.append("Primary link restored: yes")

    except Exception as exc:
        lines.append(f"Test error: {exc}")
        raise

    finally:
        if ping is not None:
            ping.terminate()
            try:
                ping.wait(timeout=2)
            except Exception:
                ping.kill()

        # Ensure the primary link is restored before shutting down.
        try:
            if net.started:
                net.get("s1").cmd("ip link set s1-eth2 up")
                net.get("s2").cmd("ip link set s2-eth1 up")
        except Exception:
            pass

        net.stop()
        output.write_text(
            "SDN failover recovery measurement\n"
            "=================================\n"
            + "\n".join(lines)
            + "\n"
        )
        print(output.read_text())


if __name__ == "__main__":
    setLogLevel("warning")
    main()
