# NEXLINK Implementation Status

Updated for the integrated NEXLINK platform build.

| Area | Status | Notes |
|---|---|---|
| Python migration | IMPLEMENTED | Runtime source is Python/FastAPI/PyQt6/Python agent. |
| Server GUI | IMPLEMENTED | PyQt6 server control panel runs FastAPI in a background worker. |
| Client GUI | IMPLEMENTED | Command Center tabs for fleet, remote access, alerts, Network Guard, AI, automation, security, support and local guard. |
| Device identity | IMPLEMENTED | Ed25519 challenge-response foundation retained. |
| Enrollment | IMPLEMENTED | Persistent token flow and approval model retained. |
| Device monitoring | IMPLEMENTED | Real psutil metrics path retained and alert rules added. |
| Inventory | IMPLEMENTED | Hardware/network/software inventory reporting added. |
| Device groups | IMPLEMENTED | Group and membership APIs added. |
| Remote sessions | IMPLEMENTED | Database-backed session records plus operator WebSocket channel. |
| Remote desktop | PARTIALLY IMPLEMENTED | Screen streaming/input/clipboard/file transfer hooks are implemented; Windows runtime must be verified. |
| Network Guard | IMPLEMENTED | Integrated; Windows Firewall/hosts behavior still requires Windows verification. |
| AI planner | IMPLEMENTED | Deterministic baseline planner and provider abstraction. |
| AI tool governance | IMPLEMENTED | Risk levels, RBAC, approval records and explicit high-risk authorization. |
| Automation | IMPLEMENTED | Safe trigger matching and allow-listed automation actions. |
| MFA | IMPLEMENTED | TOTP setup/enable/disable/login verification. |
| RBAC | IMPLEMENTED | Owner/admin/member/viewer capability model. |
| Audit | IMPLEMENTED | Security/device/automation events recorded. |
| Conditional access | PARTIALLY IMPLEMENTED | Policy storage and security-center API exist; broad policy enforcement remains an expansion. |
| Support center | IMPLEMENTED | Support request model/API/UI. |
| Relay architecture | PARTIALLY IMPLEMENTED | Server-mediated relay works as the control path; distributed NAT traversal is not yet complete. |
| Cloud/self-hosting | PARTIALLY IMPLEMENTED | Self-hosted Docker foundation exists; public hosted service is not deployed here. |
| Mobile | PLANNED | Not part of this Windows build. |
| Billing | PLANNED | Product plans are modeled; billing is intentionally not implemented yet. |

## Verification

- Python compileall: PASS
- Python AST parse: PASS
- Pure MFA/permissions/AI/protocol smoke test: PASS
- Dependency installation in current Linux environment: BLOCKED by unavailable external package resolution
- FastAPI/PostgreSQL runtime test: NOT RUN in this environment
- PyQt6 runtime test: NOT RUN in this environment
- Windows PyInstaller build: NOT RUN here
- Windows Firewall/Network Guard test: NOT RUN here
- Two-PC LAN remote session: NOT RUN here

Do not convert any NOT RUN/BLOCKED item into PASS without actual execution.
