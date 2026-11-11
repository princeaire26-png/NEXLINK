# NEXLINK LAN Auto-Discovery

The Windows Client setup dialog scans the local LAN for NEXLINK Server instances.
It fills in a single match automatically and offers a choice when it finds more
than one. The address can still be entered manually or the scan can be repeated.
After the Client is configured, its bundled Agent periodically announces itself;
the Server GUI lists clients seen recently.

## Protocol

- UDP discovery port: `39501`
- On setup, the Client broadcasts a small `NEXLINK-DISCOVERY-V1` probe.
- Server replies with hostname, API port and local IPv4 addresses.
- A single discovered Server is selected in the setup dialog; with multiple matches, the user chooses one. The selected URL is saved when setup is submitted.
- Once running, the Client sends a LAN beacon every five seconds with its device ID, device name, hostname, application version, OS and timestamp. The Server displays recently seen devices for 20 seconds after the last beacon.
- Discovery is informational only; it does not enroll, approve or authenticate a Client. Enrollment/authentication still occurs through the normal NEXLINK API and cryptographic device identity flow.
- No Internet scanning is performed.
- UDP broadcast discovery generally works only within the same LAN/broadcast domain. Guest Wi-Fi isolation, VLAN boundaries, VPN routing or network policy can block it; use the manual Server address in that case.

## Windows firewall

The Server executable adds `NEXLINK-LAN-Discovery` for inbound UDP 39501 on Private/Domain profiles, alongside the TCP 8000 API rule. The checks are independent so an existing TCP rule does not skip the UDP rule.

The UDP beacons are unauthenticated LAN discovery messages, not access grants. They reveal the device metadata listed above to devices on the local broadcast network; keep this feature on networks you trust.

## Multiple servers

If multiple NEXLINK Servers are found, the Client displays them in the setup dialog so the user can choose the correct organization/server. The Server GUI's "Clients detected on this LAN" table is separate from enrollment: discovered clients still need a valid enrollment token and approval.
