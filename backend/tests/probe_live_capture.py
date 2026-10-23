# -*- coding: utf-8 -*-
"""Live Interface Capture Capability Probe (Phase 11 Environment Validation).

Tests whether the active Windows host currently permits real live wire capture:
1. Native Windows Layer-3 Raw Sockets (`socket.SOCK_RAW`, `SIO_RCVALL`) on the active Wi-Fi interface (`192.168.31.49`).
2. Scapy / Npcap Layer-2 packet sniffing on the active network adapter.
"""
import socket
import sys

host_ip = "192.168.31.49"
print(f"Checking live packet capture capability on active interface ({host_ip})...\n")

raw_sock_status = "UNKNOWN"
raw_sock_detail = ""
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
    s.bind((host_ip, 0))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    s.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
    s.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
    s.close()
    raw_sock_status = "AVAILABLE"
    raw_sock_detail = "Native raw socket opened successfully with SIO_RCVALL."
except PermissionError as pe:
    raw_sock_status = "BLOCKED_BY_ENVIRONMENT"
    raw_sock_detail = f"PermissionError: [WinError 10013] {pe} (Host process is not running as Administrator)."
except Exception as ex:
    raw_sock_status = "BLOCKED_BY_ENVIRONMENT"
    raw_sock_detail = f"Error: {type(ex).__name__}: {ex}"

pcap_status = "UNKNOWN"
pcap_detail = ""
try:
    from scapy.all import sniff
    sniff(count=1, timeout=1)
    pcap_status = "AVAILABLE"
    pcap_detail = "Scapy sniffed from adapter via pcap driver."
except RuntimeError as re:
    pcap_status = "BLOCKED_BY_ENVIRONMENT"
    pcap_detail = f"RuntimeError: {re} (Npcap/WinPcap driver is not installed on this host)."
except Exception as ex:
    pcap_status = "BLOCKED_BY_ENVIRONMENT"
    pcap_detail = f"{type(ex).__name__}: {ex}"

print("=" * 65)
print("       PHASE 11 LIVE ENVIRONMENT CAPTURE VALIDATION           ")
print("=" * 65)
print(f"1. Native Raw Socket (SIO_RCVALL on {host_ip}):")
print(f"   Status : {raw_sock_status}")
print(f"   Detail : {raw_sock_detail}\n")

print("2. Scapy / Npcap Driver Sniffing:")
print(f"   Status : {pcap_status}")
print(f"   Detail : {pcap_detail}")
print("=" * 65)

if raw_sock_status == "AVAILABLE" or pcap_status == "AVAILABLE":
    print("\nResult: LIVE capture is supported on current host session.")
    sys.exit(0)
else:
    print("\nResult: LIVE capture is BLOCKED_BY_ENVIRONMENT on current host session.")
    print("Controlled test vectors validate decoding math; real wire capture requires elevation/Npcap.")
    sys.exit(2)
