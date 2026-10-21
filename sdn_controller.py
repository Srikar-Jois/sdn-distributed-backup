from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3


class BackupSDNController(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    CLIENT_MAC = "00:00:00:00:00:01"
    BACKUP1_MAC = "00:00:00:00:00:02"
    BACKUP2_MAC = "00:00:00:00:00:03"

    GROUP_ID = 1

    def add_flow(self, datapath, priority, match, actions):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        instructions = []
        if actions:
            instructions.append(
                parser.OFPInstructionActions(
                    ofproto.OFPIT_APPLY_ACTIONS,
                    actions,
                )
            )

        datapath.send_msg(
            parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=instructions,
            )
        )

    def add_output_actions(self, parser, ports):
        return [parser.OFPActionOutput(port) for port in ports]

    def install_failover_group(self, datapath, ports):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        buckets = []
        for port in ports:
            buckets.append(
                parser.OFPBucket(
                    weight=0,
                    watch_port=port,
                    watch_group=ofproto.OFPG_ANY,
                    actions=[parser.OFPActionOutput(port)],
                )
            )

        datapath.send_msg(
            parser.OFPGroupMod(
                datapath=datapath,
                command=ofproto.OFPGC_ADD,
                type_=ofproto.OFPGT_FF,
                group_id=self.GROUP_ID,
                buckets=buckets,
            )
        )

        self.logger.info(
            "Installed fast-failover group on switch %s using ports %s",
            datapath.id,
            ports,
        )

    def add_group_flow(self, datapath, priority, in_port, dst_mac):
        parser = datapath.ofproto_parser

        self.add_flow(
            datapath,
            priority,
            parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst_mac,
            ),
            [parser.OFPActionGroup(self.GROUP_ID)],
        )

    def add_arp_flow(self, datapath, in_port, output_ports):
        parser = datapath.ofproto_parser

        self.add_flow(
            datapath,
            100,
            parser.OFPMatch(
                in_port=in_port,
                eth_type=0x0806,
            ),
            self.add_output_actions(parser, output_ports),
        )

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        desc = msg.desc

        reasons = {
            ofproto.OFPPR_ADD: "ADD",
            ofproto.OFPPR_DELETE: "DELETE",
            ofproto.OFPPR_MODIFY: "MODIFY",
        }
        link_down = bool(desc.state & ofproto.OFPPS_LINK_DOWN)

        self.logger.warning(
            "PORT_STATUS switch=%s port=%s reason=%s link_down=%s; "
            "fast-failover group uses the first live bucket",
            datapath.id,
            desc.port_no,
            reasons.get(msg.reason, str(msg.reason)),
            link_down,
        )

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id

        # Default behavior: drop unmatched packets instead of flooding.
        self.add_flow(
            datapath,
            0,
            parser.OFPMatch(),
            [],
        )

        if dpid == 1:
            # s1: h1 is on port 1; parallel links to s2 are ports 2 and 3.
            self.install_failover_group(datapath, [2, 3])

            # Client traffic to either backup uses the active link.
            self.add_group_flow(
                datapath, 100, 1, self.BACKUP1_MAC
            )
            self.add_group_flow(
                datapath, 100, 1, self.BACKUP2_MAC
            )

            # Traffic returning to the client goes to h1.
            for port in (2, 3):
                self.add_flow(
                    datapath,
                    100,
                    parser.OFPMatch(
                        in_port=port,
                        eth_dst=self.CLIENT_MAC,
                    ),
                    [parser.OFPActionOutput(1)],
                )

            # ARP from h1 can cross either link. s2 will not forward
            # received ARP broadcasts back onto an inter-switch link.
            self.add_arp_flow(datapath, 1, [2, 3])
            for port in (2, 3):
                self.add_arp_flow(datapath, port, [1])

        elif dpid == 2:
            # s2: parallel links to s1 are ports 1 and 2;
            # h2 and h3 are on ports 3 and 4.
            self.install_failover_group(datapath, [1, 2])

            # Deliver client-bound traffic from either link to h1
            # using the first available inter-switch link in reverse.
            for port in (3, 4):
                self.add_group_flow(
                    datapath, 100, port, self.CLIENT_MAC
                )

            # Traffic arriving from s1 goes to the correct backup.
            for port in (1, 2):
                self.add_flow(
                    datapath,
                    100,
                    parser.OFPMatch(
                        in_port=port,
                        eth_dst=self.BACKUP1_MAC,
                    ),
                    [parser.OFPActionOutput(3)],
                )
                self.add_flow(
                    datapath,
                    100,
                    parser.OFPMatch(
                        in_port=port,
                        eth_dst=self.BACKUP2_MAC,
                    ),
                    [parser.OFPActionOutput(4)],
                )

            # Permit communication between the two backup hosts.
            self.add_flow(
                datapath,
                100,
                parser.OFPMatch(
                    in_port=3,
                    eth_dst=self.BACKUP2_MAC,
                ),
                [parser.OFPActionOutput(4)],
            )
            self.add_flow(
                datapath,
                100,
                parser.OFPMatch(
                    in_port=4,
                    eth_dst=self.BACKUP1_MAC,
                ),
                [parser.OFPActionOutput(3)],
            )

            # ARP arriving from s1 goes only to the backup hosts.
            for port in (1, 2):
                self.add_arp_flow(datapath, port, [3, 4])

            # ARP from either backup host reaches the other host and
            # both inter-switch links, without causing a switching loop.
            self.add_arp_flow(datapath, 3, [4, 1, 2])
            self.add_arp_flow(datapath, 4, [3, 1, 2])

        else:
            self.logger.warning(
                "Switch %s connected with unexpected datapath ID",
                dpid,
            )
            return

        self.logger.info(
            "Installed forwarding rules on switch %s",
            dpid,
        )
