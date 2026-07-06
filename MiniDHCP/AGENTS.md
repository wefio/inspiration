# MiniDHCP

One-shot DHCP server for provisioning headless devices over Ethernet cable.  
A Windows Python script that gives an IP to whatever is plugged into the other end, so you can SSH in.

## When to use this

You have a headless device (SBC, Jetson, Raspberry Pi, router, etc.) with NO screen, NO keyboard, and NO pre-configured IP. The only link is a direct Ethernet cable between your Windows machine and the device. The device defaults to DHCP — but with no DHCP server on the wire, it never gets an IP and you can't reach it.

Run MiniDHCP on the Windows side. It answers DHCP DISCOVER/REQUEST, assigns an IP, and tells you the SSH command.

## Prerequisites (one-time)

```
pip install scapy
```

Then install WinPcap/Npcap:
```
winget install --id DaiyuuNobori.Win10Pcap
```

Or download from https://npcap.com/

## Usage

```powershell
# Auto-detect physical Ethernet interface, pool 192.168.100.x
python C:\Documents\GitHub\MiniDHCP\dhcp_server.py

# Specify interface by name
python C:\Documents\GitHub\MiniDHCP\dhcp_server.py --interface "以太网"

# Specify interface by index (from Get-NetAdapter)
python C:\Documents\GitHub\MiniDHCP\dhcp_server.py --interface-idx 22

# Custom subnet
python C:\Documents\GitHub\MiniDHCP\dhcp_server.py --net 10.0.0.0/24
```

## Workflow (for AI agents)

1. **Identify the physical Ethernet port** on the Windows machine:
   ```powershell
   Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object Name, InterfaceDescription, Status, LinkSpeed
   ```
   Pick the Realtek/Intel physical port, NOT VMware/Virtual/Hyper-V adapters.

2. **Set a static IP** on that interface so the DHCP server has an address:
   ```powershell
   Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -Command "netsh interface ip set address name=\"以太网\" source=static addr=192.168.100.1 mask=255.255.255.0"'
   ```

3. **Add a firewall rule** for DHCP:
   ```powershell
   Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -Command "netsh advfirewall firewall add rule name=\"DHCP Server\" dir=in action=allow protocol=UDP localport=67"'
   ```

4. **Run the server** in background:
   ```powershell
   python C:\Documents\GitHub\MiniDHCP\dhcp_server.py
   ```

5. **Tell the user**: "Unplug and replug the Ethernet cable on the target device."

6. **When you see `ACK sent!`**, SSH to the printed IP:
   ```bash
   ssh root@192.168.100.2   # or ubuntu@192.168.100.2
   ```

## How it works

- Listens on UDP port 67 for DHCP DISCOVER/REQUEST packets
- Responds with DHCP OFFER/ACK, assigning the first IP in the pool
- One client at a time — simple, single-purpose
- Uses scapy for raw packet crafting (requires Npcap/WinPcap on Windows)

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No network interfaces found` | Check `Get-NetAdapter`, pass `--interface` explicitly |
| No DISCOVER seen | Cable not plugged in, or target device not doing DHCP. Check link lights. |
| `PermissionError` | Must run as Administrator (for raw socket) |
| scapy import error | `pip install scapy` |
| `WinPcap is not installed` | Install Npcap: `winget install DaiyuuNobori.Win10Pcap` |

## Example session

```
> python dhcp_server.py
Available interfaces:
  [0] Realtek PCIe GbE Family Controller
  [1] Intel I219-V
  Auto-selecting [0] Realtek PCIe GbE Family Controller
MiniDHCP Server
  Interface : Realtek PCIe GbE Family Controller
  Server IP : 192.168.100.1/255.255.255.0
  Pool      : 192.168.100.2 - 192.168.100.254
  Lease     : 86400s

Waiting for DHCP DISCOVER... (unplug/replug the target device's cable)

[*] DHCP DISCOVER from 00:e0:5a:13:36:e1 -> offering 192.168.100.2
    OFFER sent: 192.168.100.2
[*] DHCP REQUEST from 00:e0:5a:13:36:e1 for 192.168.100.2
    ACK sent! Client: 192.168.100.2

    ========================================
    SSH:  ssh root@192.168.100.2
     or:  ssh ubuntu@192.168.100.2
    ========================================
```
