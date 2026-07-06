"""
Mini DHCP Server — one-shot DHCP for headless device provisioning.
Gives an IP to the first Ethernet-connected client, then you SSH in.

Requires: scapy, WinPcap/Npcap  (pip install scapy; then install npcap)

Usage:
    python dhcp_server.py                          # auto-detect Ethernet
    python dhcp_server.py --interface "以太网"      # specific iface name
    python dhcp_server.py --net 192.168.50.0/24    # custom subnet
    python dhcp_server.py --interface-idx 22        # by iface index
"""
from scapy.all import *
from scapy.layers.dhcp import DHCP, BOOTP
from scapy.layers.inet import IP, UDP
from scapy.layers.l2 import Ether
import argparse, ipaddress, sys


def pick_interface():
    """Auto-select the best physical Ethernet interface."""
    candidates = []
    for name, iface in IFACES.data.items():
        # Prefer real Ethernet: name contains "以太" or "Ethernet" or "Realtek"
        if any(k in name for k in ["以太", "Ethernet", "Realtek", "enp", "eth"]):
            if "VMware" not in name and "Virtual" not in name and "Hyper-V" not in name:
                candidates.append((name, iface))
    if not candidates:
        # Fallback: any interface
        for name, iface in IFACES.data.items():
            candidates.append((name, iface))
    if not candidates:
        print("ERROR: No network interfaces found.")
        sys.exit(1)

    print("Available interfaces:")
    for i, (name, _) in enumerate(candidates):
        print(f"  [{i}] {name}")
    print(f"  Auto-selecting [{0}] {candidates[0][0]}")
    return candidates[0][0]


def parse_subnet(cidr):
    """Parse 192.168.100.0/24 -> (server_ip, netmask, network_addr, start, end)"""
    net = ipaddress.IPv4Network(cidr, strict=False)
    hosts = list(net.hosts())
    if len(hosts) < 3:
        print("ERROR: Subnet too small, need at least 3 usable addresses.")
        sys.exit(1)
    server_ip = str(hosts[0])
    pool_start = str(hosts[1])
    pool_end = str(hosts[-1])
    return server_ip, str(net.netmask), str(net.network_address), pool_start, pool_end


def dhcp_offer(pkt, cfg):
    mac = pkt[Ether].src
    xid = pkt[BOOTP].xid
    ip = cfg["pool_start"]
    cfg["offered"][mac] = ip

    print(f"[*] DHCP DISCOVER from {mac} -> offering {ip}")

    opts = [
        ("message-type", "offer"),
        ("server_id", cfg["server_ip"]),
        ("subnet_mask", cfg["netmask"]),
        ("router", cfg["server_ip"]),
        ("domain_name_server", cfg["server_ip"]),
        ("lease_time", cfg["lease_time"]),
        ("renewal_time", cfg["lease_time"] // 2),
        ("rebinding_time", cfg["lease_time"] * 7 // 8),
        "end",
    ]

    pkt = (
        Ether(src=get_if_hwaddr(cfg["iface"]), dst=mac) /
        IP(src=cfg["server_ip"], dst="255.255.255.255") /
        UDP(sport=67, dport=68) /
        BOOTP(op=2, xid=xid, yiaddr=ip, siaddr=cfg["server_ip"],
              chaddr=pkt[BOOTP].chaddr, flags=pkt[BOOTP].flags) /
        DHCP(options=opts)
    )
    sendp(pkt, iface=cfg["iface"], verbose=False)
    print(f"    OFFER sent: {ip}")


def dhcp_ack(pkt, cfg):
    mac = pkt[Ether].src
    xid = pkt[BOOTP].xid

    req_ip = None
    for opt in pkt[DHCP].options:
        if isinstance(opt, tuple) and opt[0] == "requested_addr":
            req_ip = opt[1]
            break

    ip = req_ip or cfg["offered"].get(mac, cfg["pool_start"])
    cfg["assigned"] = ip

    print(f"[*] DHCP REQUEST from {mac} for {ip}")

    opts = [
        ("message-type", "ack"),
        ("server_id", cfg["server_ip"]),
        ("subnet_mask", cfg["netmask"]),
        ("router", cfg["server_ip"]),
        ("domain_name_server", cfg["server_ip"]),
        ("lease_time", cfg["lease_time"]),
        ("renewal_time", cfg["lease_time"] // 2),
        ("rebinding_time", cfg["lease_time"] * 7 // 8),
        "end",
    ]

    pkt = (
        Ether(src=get_if_hwaddr(cfg["iface"]), dst=mac) /
        IP(src=cfg["server_ip"], dst="255.255.255.255") /
        UDP(sport=67, dport=68) /
        BOOTP(op=2, xid=xid, yiaddr=ip, siaddr=cfg["server_ip"],
              chaddr=pkt[BOOTP].chaddr, flags=pkt[BOOTP].flags) /
        DHCP(options=opts)
    )
    sendp(pkt, iface=cfg["iface"], verbose=False)
    print(f"    ACK sent! Client: {ip}")
    print(f"")
    print(f"    ========================================")
    print(f"    SSH:  ssh root@{ip}")
    print(f"     or:  ssh ubuntu@{ip}")
    print(f"    ========================================")
    print(f"")


def handler(pkt, cfg):
    if not pkt.haslayer(DHCP):
        return
    mt = None
    for opt in pkt[DHCP].options:
        if isinstance(opt, tuple) and opt[0] == "message-type":
            mt = opt[1]
            break
    if mt == 1:
        dhcp_offer(pkt, cfg)
    elif mt == 3:
        dhcp_ack(pkt, cfg)


def main():
    parser = argparse.ArgumentParser(description="Mini DHCP Server")
    parser.add_argument("--interface", help="Interface name (e.g. '以太网', 'Ethernet')")
    parser.add_argument("--interface-idx", type=int, help="Interface index (e.g. 22)")
    parser.add_argument("--net", default="192.168.100.0/24", help="Subnet CIDR (default: 192.168.100.0/24)")
    parser.add_argument("--lease-time", type=int, default=86400, help="Lease time in seconds")
    args = parser.parse_args()

    # Pick interface
    if args.interface_idx:
        from scapy.arch.windows import get_windows_if_list
        iflist = get_windows_if_list()
        iface_name = None
        for i in iflist:
            if i.get("interface_index") == args.interface_idx:
                iface_name = i["name"]
                break
        if not iface_name:
            print(f"ERROR: No interface with index {args.interface_idx}")
            sys.exit(1)
    elif args.interface:
        iface_name = args.interface
    else:
        iface_name = pick_interface()

    # Parse subnet
    server_ip, netmask, network, pool_start, pool_end = parse_subnet(args.net)

    cfg = {
        "iface": iface_name,
        "server_ip": server_ip,
        "netmask": netmask,
        "network": network,
        "pool_start": pool_start,
        "pool_end": pool_end,
        "lease_time": args.lease_time,
        "offered": {},
        "assigned": None,
    }

    print(f"MiniDHCP Server")
    print(f"  Interface : {iface_name}")
    print(f"  Server IP : {server_ip}/{netmask}")
    print(f"  Pool      : {pool_start} - {pool_end}")
    print(f"  Lease     : {args.lease_time}s")
    print(f"")
    print(f"Waiting for DHCP DISCOVER... (unplug/replug the target device's cable)")
    print(f"")

    try:
        sniff(iface=iface_name, filter="udp and port 67", prn=lambda p: handler(p, cfg), store=False)
    except KeyboardInterrupt:
        print("")
        if cfg["assigned"]:
            print(f"Client was assigned: {cfg['assigned']}")
        else:
            print("No client assigned. Exiting.")


if __name__ == "__main__":
    main()
