# NEXLINK Platform Build

NEXLINK is now structured as one platform with these integrated domains:

- Remote Access: authenticated remote desktop session, keyboard/mouse input, clipboard channel, adaptive screen streaming.
- Device Management: live metrics, device inventory, software inventory, groups, health alerts, support requests.
- Network Guard: Internet control, domain blocking, LAN-preserving policy enforcement and vouchers.
- NEXLINK AI: provider-neutral planner, structured tools, risk classification and explicit authorization for high-risk actions.
- Security Center: RBAC, MFA/TOTP, device identity, enrollment approval, session revocation, audit events and conditional-access policies.
- Automation: event/condition matching with an allow-listed action vocabulary.
- Connectivity: LAN-first direct connection with a relay/signaling abstraction for future NAT traversal and Internet relay deployment.
- Deployment: self-hosted infrastructure remains Docker-compatible; hosted deployment can use the same FastAPI/PostgreSQL/Redis services.

## Reality rule

This source implements the architecture and executable paths that can be represented safely in Python, but Windows runtime behavior still requires Windows verification. In particular, screen capture, keyboard/mouse injection, Windows Firewall, PyInstaller, and the two-PC LAN path must be tested on Windows before being called production-ready.

## Build outputs

The intended product remains exactly two Windows applications:

- `NEXLINK-Server.exe`
- `NEXLINK-Client.exe`

Network Guard is a subsystem of NEXLINK Client, not a third executable.
