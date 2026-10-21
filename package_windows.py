"""Verify the Windows PyInstaller output and create the three release ZIPs."""
from __future__ import annotations

import struct
import sys
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
CLIENT = DIST / "NEXLINK-Client"
SERVER = DIST / "NEXLINK-Server"
PACKAGE = DIST / "NEXLINK-Windows"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Windows bundle verification failed: {message}")


def verify_pe(path: Path) -> None:
    require(path.is_file(), f"missing executable: {path}")
    data = path.read_bytes()
    require(len(data) > 0, f"empty executable: {path}")
    require(data[:2] == b"MZ", f"not an MZ executable: {path}")
    require(len(data) >= 0x40, f"truncated DOS header: {path}")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    require(data[pe_offset : pe_offset + 4] == b"PE\0\0", f"invalid PE signature: {path}")


def zip_tree(source: Path, destination: Path) -> None:
    require(source.is_dir(), f"missing bundle directory: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for file in sorted(source.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(source).as_posix())
    require(destination.is_file() and destination.stat().st_size > 0, f"empty archive: {destination}")


def verify_archive(path: Path, executable_name: str, required_entries: tuple[str, ...]) -> None:
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        require(executable_name in names, f"{path.name} is missing {executable_name}")
        for entry in required_entries:
            require(entry in names, f"{path.name} is missing {entry}")


def main() -> int:
    client_exe = CLIENT / "NEXLINK-Client.exe"
    server_exe = SERVER / "NEXLINK-Server.exe"
    verify_pe(client_exe)
    verify_pe(server_exe)

    qt_payloads: dict[Path, tuple[str, str]] = {}
    for bundle, icon_name in ((CLIENT, "nexlink-client.ico"), (SERVER, "nexlink-server.ico")):
        require((bundle / "_internal" / "assets" / "icons" / icon_name).is_file(),
                f"{icon_name} is missing from {bundle.name}")
        qt_core = next(bundle.rglob("Qt6Core.dll"), None)
        qt_plugin = next(bundle.rglob("qwindows.dll"), None)
        require(qt_core is not None, f"Qt6Core.dll is missing from {bundle.name}")
        require(qt_plugin is not None, f"Qt Windows platform plugin is missing from {bundle.name}")
        qt_payloads[bundle] = (qt_core.relative_to(bundle).as_posix(), qt_plugin.relative_to(bundle).as_posix())

    (PACKAGE / "Client" / "assets" / "icons").mkdir(parents=True, exist_ok=True)
    (PACKAGE / "Server" / "assets" / "icons").mkdir(parents=True, exist_ok=True)
    (PACKAGE / "Client" / "config").mkdir(parents=True, exist_ok=True)
    (PACKAGE / "Server" / "config").mkdir(parents=True, exist_ok=True)

    shutil.copytree(CLIENT, PACKAGE / "Client", dirs_exist_ok=True)
    shutil.copytree(SERVER, PACKAGE / "Server", dirs_exist_ok=True)
    shutil.copy2(ROOT / "assets" / "icons" / "nexlink-client.ico", PACKAGE / "Client" / "assets" / "icons" / "nexlink-client.ico")
    shutil.copy2(ROOT / "assets" / "icons" / "nexlink-client.svg", PACKAGE / "Client" / "assets" / "icons" / "nexlink-client.svg")
    shutil.copy2(ROOT / "assets" / "icons" / "nexlink-server.ico", PACKAGE / "Server" / "assets" / "icons" / "nexlink-server.ico")
    shutil.copy2(ROOT / "assets" / "icons" / "nexlink-server.svg", PACKAGE / "Server" / "assets" / "icons" / "nexlink-server.svg")

    (PACKAGE / "Client" / "config" / "README.txt").write_text(
        "NEXLINK Client configuration is created in %LOCALAPPDATA%\\NEXLINK. "
        "This package contains no API keys, passwords, or environment secrets. "
        "Use a protected network and configure HTTPS/WSS for remote deployments.\n",
        encoding="utf-8",
    )
    (PACKAGE / "Server" / "config" / "README.txt").write_text(
        "NEXLINK Server creates its JWT signing configuration in %LOCALAPPDATA%\\NEXLINK "
        "on first launch. Configure database, Redis, and AI provider settings through "
        "the server environment. No credentials or provider API keys are bundled.\n",
        encoding="utf-8",
    )
    (PACKAGE / "README.txt").write_text(
        "NEXLINK Windows Bundle\n\n"
        "Client\\NEXLINK-Client.exe is the operator and endpoint application.\n"
        "Server\\NEXLINK-Server.exe is the FastAPI control plane and desktop manager.\n"
        "Keep each executable beside its _internal folder. The Server requires "
        "Docker Desktop or PostgreSQL and Redis services already running.\n"
        "Run both applications as Administrator where Windows Firewall/Network Guard requires it.\n"
        "Configuration and generated secrets are kept outside this package under %LOCALAPPDATA%\\NEXLINK.\n",
        encoding="utf-8",
    )

    client_zip = DIST / "NEXLINK-Client-Windows.zip"
    server_zip = DIST / "NEXLINK-Server-Windows.zip"
    bundle_zip = DIST / "NEXLINK-Windows-Bundle.zip"
    zip_tree(PACKAGE / "Client", client_zip)
    zip_tree(PACKAGE / "Server", server_zip)
    zip_tree(PACKAGE, bundle_zip)

    client_qt_core, client_qt_plugin = qt_payloads[CLIENT]
    server_qt_core, server_qt_plugin = qt_payloads[SERVER]
    verify_archive(client_zip, "NEXLINK-Client.exe", (
        "config/README.txt",
        "assets/icons/nexlink-client.ico",
        client_qt_core,
        client_qt_plugin,
    ))
    verify_archive(server_zip, "NEXLINK-Server.exe", (
        "config/README.txt",
        "assets/icons/nexlink-server.ico",
        server_qt_core,
        server_qt_plugin,
    ))
    verify_archive(
        bundle_zip,
        "Client/NEXLINK-Client.exe",
        ("Server/NEXLINK-Server.exe", "README.txt"),
    )
    print("Verified Windows PE headers, non-empty executables, PyInstaller bundles, Qt DLLs/plugins, icons, config docs, and all three ZIPs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
