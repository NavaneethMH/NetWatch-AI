# -*- coding: utf-8 -*-
"""Step 0 preflight: inspect host networking environment for Phase 9."""
import subprocess
import socket
import re
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import psutil

print("=== PREFLIGHT: Host Network Environment ===\n")

# 1. psutil interfaces
print("--- Active IPv4 Interfaces ---")
addrs = psutil.net_if_addrs()
stats = psutil.net_if_stats()
active_ifaces = []
for iface, addr_list in addrs.items():
    for a in addr_list:
        if a.family == socket.AF_INET and not a.address.startswith('127.') and not a.address.startswith('169.254.'):
            is_up = stats[iface].isup if iface in stats else False
            speed = stats[iface].speed if iface in stats else 0
            print(f"  {iface}: {a.address}/{a.netmask}  up={is_up}  speed={speed}Mbps")
            if is_up:
                active_ifaces.append({
                    'name': iface,
                    'ip': a.address,
                    'mask': a.netmask,
                })

# 2. Default route
print("\n--- Default Route ---")
r = subprocess.run(['route', 'print', '-4'], capture_output=True, text=True)
gw_ip = None
gw_iface_ip = None
for line in r.stdout.splitlines():
    parts = line.split()
    if len(parts) >= 5 and parts[0] == '0.0.0.0' and parts[1] == '0.0.0.0':
        gw_ip = parts[2]
        gw_iface_ip = parts[3]
        print(f"  Gateway: {gw_ip}  via local IP: {gw_iface_ip}")
        break

# 3. Identify LAN interface
print("\n--- LAN Interface Selection ---")
lan_iface = None
for iface in active_ifaces:
    if iface['ip'] == gw_iface_ip:
        lan_iface = iface
        break
if not lan_iface and active_ifaces:
    # Fallback: pick first non-virtual
    for iface in active_ifaces:
        if '192.168.56' not in iface['ip'] and 'VirtualBox' not in iface.get('desc', ''):
            lan_iface = iface
            break

if lan_iface:
    import ipaddress
    net = ipaddress.IPv4Network(f"{lan_iface['ip']}/{lan_iface['mask']}", strict=False)
    print(f"  Selected: {lan_iface['name']}")
    print(f"  Local IP: {lan_iface['ip']}")
    print(f"  Subnet mask: {lan_iface['mask']}")
    print(f"  Subnet: {net}")
    print(f"  Prefix length: /{net.prefixlen}")
    print(f"  Host count: {net.num_addresses - 2}")
    print(f"  Safe to auto-scan (<=512 hosts): {net.num_addresses - 2 <= 512}")
else:
    print("  No suitable LAN interface found!")

# 4. Virtual/VPN/loopback adapters to exclude
print("\n--- Adapters to EXCLUDE ---")
exclude_keywords = ['VirtualBox', 'Virtual', 'Loopback', 'Bluetooth', 'Wi-Fi Direct', 'Pseudo']
for iface, addr_list in addrs.items():
    for kw in exclude_keywords:
        if kw.lower() in iface.lower():
            for a in addr_list:
                if a.family == socket.AF_INET:
                    print(f"  EXCLUDE: {iface} ({a.address})")
            break

# 5. OS ARP table - real neighbors
print("\n--- OS ARP Table (real neighbors only) ---")
r2 = subprocess.run(['arp', '-a'], capture_output=True, text=True)
dynamic_entries = []
for line in r2.stdout.splitlines():
    if 'dynamic' in line.lower():
        parts = line.split()
        if len(parts) >= 2:
            ip = parts[0]
            mac = parts[1]
            # Exclude multicast/broadcast
            first_octet = int(ip.split('.')[0]) if ip.count('.') == 3 else 999
            if first_octet < 224:
                dynamic_entries.append((ip, mac))
                print(f"  IP={ip}  MAC={mac}")
print(f"  Total dynamic ARP entries: {len(dynamic_entries)}")

# 6. Hostname resolution
print("\n--- Hostname Resolution ---")
for ip, mac in dynamic_entries:
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        print(f"  {ip} -> {hostname}")
    except Exception:
        print(f"  {ip} -> <unresolvable>")

# 7. Scapy capability
print("\n--- Scapy ARP Capability ---")
try:
    from scapy.all import conf
    l2 = str(conf.L2socket)
    if 'NotAvailable' in l2 or 'wpcap.dll missing' in l2:
        print("  Scapy: UNAVAILABLE (no Npcap/wpcap.dll)")
        print("  Fallback strategy: OS ARP table + controlled ICMP ping")
    else:
        print(f"  Scapy: AVAILABLE ({l2})")
except Exception as e:
    print(f"  Scapy: ERROR ({e})")

# 8. ICMP ping test to gateway
print("\n--- ICMP Reachability ---")
if gw_ip:
    r3 = subprocess.run(['ping', '-n', '1', '-w', '1000', gw_ip],
                        capture_output=True, text=True)
    reachable = 'TTL=' in r3.stdout or 'bytes=' in r3.stdout
    state = 'REACHABLE' if reachable else 'UNREACHABLE'
    print(f"  Gateway {gw_ip}: {state}")

print("\n=== PREFLIGHT COMPLETE ===")
