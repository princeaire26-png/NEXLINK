# NEXLINK Master Architecture

## Product

**NEXLINK — Connect. Control. Understand. Automate.**

NEXLINK is one integrated remote-computing and device-management platform. Network Guard is a subsystem of NEXLINK Client; it is not a separate executable.

## Product planes

```text
                         NEXLINK
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   REMOTE ACCESS        DEVICE MANAGEMENT    NETWORK GUARD
        │                   │                   │
   Desktop streaming    Telemetry           Internet control
   Input control        Inventory            Domain policies
   Clipboard            Alerts               Vouchers
   File transfer        Groups               LAN preservation
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                       NEXLINK AI
                            │
                 Detect → Diagnose → Plan
                            │
                 Authorize → Execute → Verify
                            │
                     SECURITY CENTER
                            │
             RBAC • MFA • Audit • Device Trust
                            │
                   AUTOMATION / RMM ENGINE
```

## What is implemented in this build

### Remote Access
- PostgreSQL-backed remote session lifecycle.
- Authenticated operator WebSocket channel.
- Server-to-agent action routing.
- Windows-first screen capture via Pillow/ImageGrab.
- Adaptive JPEG screen frames.
- Mouse/keyboard input hooks via PyAutoGUI.
- Clipboard channel.
- Read-only remote file download; administrator-gated upload path exists in the protocol.
- Multi-monitor capture is requested through `ImageGrab(all_screens=True)`.

### Device Management / RMM
- Live CPU/RAM/disk/uptime/OS metrics.
- Inventory payloads.
- Windows software inventory collection.
- Device groups and group membership.
- Health alerts from real telemetry.
- Support requests.
- Maintenance actions with role/risk checks.
- Software installation action with explicit authorization.

### Network Guard
- Integrated into the same Client executable.
- Internet block/unblock.
- Domain blocking.
- Voucher/session support.
- Server-issued network actions.
- LAN-preserving firewall strategy remains part of the Windows-specific verification.

### NEXLINK AI
- Provider-neutral AI abstraction.
- Structured tool registry.
- Deterministic baseline action planner.
- Tool risk levels.
- RBAC-aware policy decisions.
- Pending approval records for high-risk operations.
- Agent-side diagnostic tools.
- High-risk execution requires explicit authorization.

### Security Center
- Ed25519 device identity and challenge-response.
- Enrollment approval/revocation.
- Immediate WebSocket revocation.
- JWT access/refresh sessions.
- Refresh-token rotation.
- TOTP MFA endpoints.
- RBAC/capability matrix.
- Conditional-access policy storage.
- Audit trail.

### Automation
- Event/condition matching.
- Allow-listed action types.
- Automation run records.
- Metric-triggered health checks/alerts/notifications.

### Multi-tenant / commercial foundation
- Organizations and memberships.
- Organization-scoped groups, policies and automations.
- Support requests.
- Relay node metadata.
- Personal/business/enterprise plan field is retained in organization data.
- Self-hosted deployment remains Docker-compatible.

### Connectivity
- LAN-first operation.
- Server-mediated remote control acts as the relay path when endpoints cannot directly communicate.
- Relay node registry exists for a future distributed relay tier.
- Direct P2P/NAT traversal is an architectural extension, not claimed as completed here.

## Verification status

The source has passed Python compilation/AST parsing in the available Linux environment.

The environment could not install missing dependencies because external package resolution was unavailable. Therefore full FastAPI/PyQt6 runtime tests were not run here.

Windows-only behavior remains **NOT VERIFIED** until a real Windows build and two-PC LAN test are completed, especially:

- PyInstaller executables.
- UAC/elevation.
- Windows Firewall Network Guard behavior.
- Pillow screen capture.
- PyAutoGUI input injection.
- Windows software inventory.
- Agent service lifecycle.
- Real two-PC enrollment/authentication/metrics.
- Real remote-control session.

## Explicitly not claimed complete

These are intentionally not labeled production-ready yet:

- NAT traversal / STUN/TURN-class direct connectivity.
- Remote audio.
- Remote printing.
- Video-grade session recording.
- Mobile applications.
- Public cloud infrastructure and billing.
- Enterprise SSO/SAML/OIDC.
- Distributed relay fleet.
- Full patch-management catalog.

Those are extension points, not fake implementations.
