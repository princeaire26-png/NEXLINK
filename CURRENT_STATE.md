# NEXLINK Current State

## Runtime
- Backend: Python/FastAPI
- Client: Python/PyQt6 Command Center
- Device agent: Python, bundled into NEXLINK Client
- Network Guard: integrated Python/Windows Firewall/hosts subsystem
- Remote Access: authenticated screen/input/clipboard/file-transfer transport
- RMM: monitoring, inventory, software inventory, groups and alerts
- AI: provider-neutral planner/tool registry/policy/approval flow
- Security Center: Ed25519, enrollment approval/revocation, JWT sessions, TOTP MFA, RBAC, audit and policy storage
- Automation: event/condition engine with allow-listed actions
- Infrastructure: PostgreSQL + Redis + Docker self-hosting foundation

## Windows outputs
- NEXLINK-Server.exe
- NEXLINK-Client.exe

## Removed runtime stacks
- Node.js
- TypeScript
- React
- Vite
- Rust/Cargo
- Tauri
- separate InternetGuard executable

## Verification
Source compilation and AST checks pass in the available environment. Full dependency-backed server/client runtime testing and Windows build/runtime testing still require an environment with the declared dependencies and a real Windows machine.
