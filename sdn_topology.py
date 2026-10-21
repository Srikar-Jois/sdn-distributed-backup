from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel


class BackupTopo(Topo):
    def build(self):
        s1 = self.addSwitch("s1", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", protocols="OpenFlow13")

        client = self.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
        backup1 = self.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
        backup2 = self.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")

        self.addLink(client, s1)
        self.addLink(s1, s2)
        self.addLink(s1, s2)
        self.addLink(backup1, s2)
        self.addLink(backup2, s2)


def run():
    topo = BackupTopo()
    net = Mininet(
        topo=topo,
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

    try:
        net.start()
        print("\nBackup SDN topology started.")
        print("Hosts: h1 (client), h2 and h3 (backup nodes)")
        print("Try: pingall")
        CLI(net)
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
