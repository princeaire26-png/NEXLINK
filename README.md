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

1. Start PostgreSQL on the server PC, or install Docker Desktop for the Server's automatic PostgreSQL setup. Redis is optional for the current core runtime.
2. Launch `NEXLINK-Server.exe` from its complete onedir bundle; the Server GUI starts the API and LAN discovery responder.
3. Launch `NEXLINK-Client.exe` from its complete onedir bundle as Administrator on Windows. Its setup dialog scans for Servers on the LAN; choose a result or enter an address manually.
4. After setup, the Server GUI's **Clients detected on this LAN** table should show the Client. Discovery is not enrollment or approval.
5. Sign in to the NEXLINK server from the Client Command Center.
6. Create an enrollment token, enroll the endpoint, and approve it.
7. Verify it becomes **ONLINE** and real metrics appear.
8. Open **Devices / Remote** to start a remote session.
9. Use **Network Guard**, **Alerts**, **NEXLINK AI**, **Automation**, **Security Center**, and **Support Center** from the same client.

## Windows build

On Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\BUILD_NEXLINK_WINDOWS.ps1
```

The executables are inside onedir bundles. Keep each executable beside its `_internal` directory; do not copy an `.exe` out by itself.

```text
dist\NEXLINK-Server\NEXLINK-Server.exe
dist\NEXLINK-Client\NEXLINK-Client.exe
```

The build also creates client/server ZIPs and a combined `dist\NEXLINK-Windows-Bundle.zip`.

## Verification rule

The project deliberately distinguishes **implemented**, **partially implemented**, **not verified**, and **blocked**. Linux source checks do not certify Windows behavior. A Windows build and real two-PC LAN test are still required before declaring the platform production-ready.
