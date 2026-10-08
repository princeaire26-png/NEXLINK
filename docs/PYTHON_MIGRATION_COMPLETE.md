# NEXLINK Python Migration

The NEXLINK runtime has been consolidated onto Python.

## Replaced

| Former runtime | Replacement |
|---|---|
| React/TypeScript/Vite dashboard | PyQt6 Python desktop dashboard |
| Rust NEXLINK Agent | `nexlink_agent` Python package |
| Rust protocol crate | `nexlink_agent.protocol` |
| Tauri-style client packaging | PyInstaller |
| Separate InternetGuard product | NEXLINK Network Guard |

## Kept

- FastAPI backend
- PostgreSQL schema and migrations
- Redis infrastructure
- Ed25519 authentication model
- LAN WebSocket control channel
- Network Guard Windows firewall/hosts enforcement
- Existing SQL persistence model

The application has exactly two intended Windows executables.
