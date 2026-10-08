# NEXLINK — Intelligent Remote Computing Platform

**Connect. Control. Understand. Automate.**

NEXLINK is a single Windows/LAN platform designed to combine **TeamViewer-class remote access + RMM/device management + Network Guard + AI-assisted IT operations + Security Center + automation**.

There are exactly two Windows applications:

- `NEXLINK-Server.exe` — control plane, authentication, device registry, signaling/relay, policies, audit and APIs.
- `NEXLINK-Client.exe` — operator Command Center plus the authenticated endpoint agent and integrated Network Guard.

There is **no separate Internet Guard executable**.

## Integrated product

```text
                         NEXLINK
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   REMOTE ACCESS        DEVICE MANAGEMENT    NETWORK GUARD
        │                   │                   │
   Desktop / Input      Monitoring           Internet control
   Clipboard            Inventory             Domain blocking
   File transfer        Alerts                Policies / vouchers
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                       NEXLINK AI
                            │
                 Detect → Diagnose → Plan
                 Authorize → Execute → Verify
                            │
                     SECURITY CENTER
                            │
                RBAC • MFA • Audit • Trust
                            │
                      AUTOMATION / RMM
```

## Current platform layers

- Remote desktop session transport and Windows-first screen/input implementation.
- Device monitoring, inventory, software inventory, groups and health alerts.
- Network Guard integrated into the endpoint client.
- AI planner/tool registry with risk-based authorization.
- RBAC, TOTP MFA, device identity, enrollment approval and revocation.
- Audit events and conditional-access policy storage.
- Automation rules with an allow-listed action vocabulary.
- Support center and relay-node architecture.
- PostgreSQL + Redis infrastructure with Docker self-hosting support.

See [`docs/NEXLINK_MASTER_ARCHITECTURE.md`](docs/NEXLINK_MASTER_ARCHITECTURE.md) for the implementation/verification boundary.

## LAN deployment

1. Start PostgreSQL and Redis on the server PC, or use `NEXLINK-Server.exe --auto-infra` with Docker Desktop.
2. Launch `NEXLINK-Server.exe`.
3. Launch `NEXLINK-Client.exe` on an endpoint as Administrator on Windows.
4. Sign in to the NEXLINK server from the Command Center.
5. Create an enrollment token.
6. Enroll the endpoint and approve it.
7. Verify it becomes **ONLINE** and real metrics appear.
8. Open **Devices / Remote** to start a remote session.
9. Use **Network Guard**, **Alerts**, **NEXLINK AI**, **Automation**, **Security Center**, and **Support Center** from the same client.

## Windows build

On Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\BUILD_NEXLINK_WINDOWS.ps1
```

Expected outputs:

```text
dist\NEXLINK-Server.exe
dist\client\NEXLINK-Client.exe
```

The build no longer requires Node/npm/Cargo for the application runtime.

## Verification rule

The project deliberately distinguishes **implemented**, **partially implemented**, **not verified**, and **blocked**. Linux source checks do not certify Windows behavior. A Windows build and real two-PC LAN test are still required before declaring the platform production-ready.
