# NEXLINK LAN Auto-Discovery

NEXLINK Client automatically discovers NEXLINK Server instances on the local LAN.

## Protocol

- UDP discovery port: `39501`
- Client broadcasts a small `NEXLINK-DISCOVERY-V1` probe.
- Server replies with hostname, API port and local IPv4 addresses.
- The Client selects the first discovered server and persists its URL.
- Discovery is informational only; enrollment/authentication still occurs through the normal NEXLINK API and cryptographic device identity flow.
- No Internet scanning is performed.

## Windows firewall

The Server adds `NEXLINK-LAN-Discovery` for inbound UDP 39501 on Private/Domain profiles, alongside the TCP 8000 API rule.

## Multiple servers

If multiple NEXLINK Servers are found, the Client displays them in the setup dialog so the user can choose the correct organization/server.
