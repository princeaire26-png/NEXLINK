"""NEXLINK Windows server runtime, database bootstrap, and infrastructure setup."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_DB_URL = "postgresql+asyncpg://nexlink:nexlink_dev@127.0.0.1:5432/nexlink"
DOCKER_DB_URL = "postgresql+asyncpg://nexlink:nexlink_dev@127.0.0.1:55432/nexlink"


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "NEXLINK"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path() -> Path:
    return _config_dir() / "server.json"


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def _normalize_db_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _db_ping(url: str) -> bool:
    try:
        import asyncpg
        conn = await asyncpg.connect(_normalize_db_url(url), timeout=4)
        await conn.execute("SELECT 1")
        await conn.close()
        return True
    except Exception:
        return False


def database_reachable(url: str | None = None) -> bool:
    return asyncio.run(_db_ping(url or os.environ.get("DATABASE_URL", DEFAULT_DB_URL)))


def infrastructure_status() -> dict[str, bool]:
    """Report infrastructure without making Docker a hard dependency."""
    db_url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    return {
        "postgres_port": _port_open("127.0.0.1", 5432),
        "nexlink_docker_postgres_port": _port_open("127.0.0.1", 55432),
        "postgres": database_reachable(db_url),
        "redis": _port_open("127.0.0.1", 6379) or _port_open("127.0.0.1", 56379),
        "docker": _docker_path() is not None,
        "docker_ready": _docker_ready(),
    }


def _docker_path() -> str | None:
    found = shutil.which("docker")
    if found:
        return found
    if os.name == "nt":
        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "com.docker.cli.exe",
            Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
        ]
        for path in candidates:
            if path.exists():
                return str(path)
    return None


def _docker_ready() -> bool:
    docker = _docker_path()
    if not docker:
        return False
    try:
        return subprocess.run([docker, "info"], capture_output=True, text=True, timeout=8, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _launch_docker_desktop() -> bool:
    if os.name != "nt":
        return False
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "Docker" / "Docker" / "Docker Desktop.exe",
    ]
    exe = next((p for p in candidates if p.exists()), None)
    if not exe:
        return False
    try:
        subprocess.Popen([str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    deadline = time.time() + 90
    while time.time() < deadline:
        if _docker_ready():
            return True
        time.sleep(2)
    return False


def _ensure_server_config() -> None:
    config = {}
    path = _config_path()
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            config = {}

    if not config.get("jwt_secret_key") or len(config["jwt_secret_key"]) < 32:
        import secrets
        config["jwt_secret_key"] = secrets.token_urlsafe(48)

    config.setdefault("database_url", os.environ.get("DATABASE_URL", DEFAULT_DB_URL))
    config.setdefault("redis_url", os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"))
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    os.environ.setdefault("HOST", "0.0.0.0")
    os.environ.setdefault("PORT", "8000")
    os.environ.setdefault("DATABASE_URL", config["database_url"])
    os.environ.setdefault("REDIS_URL", config["redis_url"])
    os.environ.setdefault("JWT_SECRET_KEY", config["jwt_secret_key"])


def _save_database_url(url: str) -> None:
    path = _config_path()
    try:
        config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        config = {}
    config["database_url"] = url
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    os.environ["DATABASE_URL"] = url


def _start_local_postgres_services() -> None:
    if os.name != "nt":
        return
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             "Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Where-Object {$_.Status -ne 'Running'} | Start-Service"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        if result.returncode != 0:
            return
    except (OSError, subprocess.SubprocessError):
        return


def _run_migrations(url: str) -> None:
    """Provision a fresh local NEXLINK database and record migration markers."""
    async def runner():
        import asyncpg
        conn = await asyncpg.connect(_normalize_db_url(url), timeout=8)
        try:
            await conn.execute("CREATE TABLE IF NOT EXISTS nexlink_schema_migrations (version VARCHAR(32) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            rows = await conn.fetch("SELECT version FROM nexlink_schema_migrations")
            applied = {row["version"] for row in rows}
            migrations = _runtime_root() / "backend" / "migrations" / "postgres"
            ordered = [
                ("001", "users", migrations / "001_initial_schema.sql"),
                ("002", "enrollment_tokens", migrations / "002_enrollment_and_metrics.sql"),
                ("003", "device_connections", migrations / "003_python_backend_schema.sql"),
                ("004", "device_alerts", migrations / "004_nexlink_platform.sql"),
            ]
            for version, marker_table, file in ordered:
                if version in applied:
                    continue
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=$1)",
                    marker_table,
                )
                if not exists:
                    await conn.execute(file.read_text(encoding="utf-8"))
                await conn.execute("INSERT INTO nexlink_schema_migrations(version) VALUES($1) ON CONFLICT DO NOTHING", version)
        finally:
            await conn.close()
    asyncio.run(runner())


def _docker_compose_up() -> None:
    docker = _docker_path()
    if not docker:
        raise RuntimeError("Docker CLI is not installed.")
    root = _runtime_root()
    compose = root / "deployment-compose.server.yml"
    if not compose.exists():
        raise RuntimeError("NEXLINK Docker infrastructure definition is missing from the installation.")
    env = os.environ.copy()
    # Keep the NEXLINK container isolated from any PostgreSQL installation already
    # occupying 5432. This makes Docker a fallback, not a replacement for local DBs.
    env.setdefault("NEXLINK_POSTGRES_PORT", "55432")
    env.setdefault("NEXLINK_REDIS_PORT", "56379")
    subprocess.run(
        [docker, "compose", "-f", str(compose), "up", "-d", "postgres", "redis"],
        cwd=str(root), env=env, check=True,
    )


def _ensure_database() -> str:
    """Return a working DB URL, preferring installed PostgreSQL and falling back to Docker."""
    configured = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    _start_local_postgres_services()
    if database_reachable(configured):
        _run_migrations(configured)
        return configured

    docker = _docker_path()
    if docker:
        if not _docker_ready() and not _launch_docker_desktop():
            raise RuntimeError(
                "Docker Desktop is installed but is not running. Start Docker Desktop and click Retry."
            )
        _docker_compose_up()
        deadline = time.time() + 90
        docker_url = DOCKER_DB_URL
        while time.time() < deadline:
            if database_reachable(docker_url):
                _run_migrations(docker_url)
                _save_database_url(docker_url)
                return docker_url
            time.sleep(2)
        raise RuntimeError(
            "NEXLINK started Docker PostgreSQL but it did not become ready within 90 seconds. "
            "Open Docker Desktop, verify the NEXLINK postgres container is healthy, then Retry."
        )

    raise RuntimeError(
        "NEXLINK could not connect to PostgreSQL. Install PostgreSQL 16+ and configure the "
        "NEXLINK database connection, or install/start Docker Desktop. NEXLINK does not "
        "require Redis for its current core runtime."
    )


def _start_infrastructure() -> str:
    return _ensure_database()


def _configure_api_firewall() -> None:
    if os.name != "nt":
        return
    rule = "NEXLINK-Server-API"
    result = subprocess.run(
        ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule}"],
        capture_output=True, text=True, check=False,
    )
    if "LocalPort" in result.stdout and "8000" in result.stdout:
        return
    subprocess.run([
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={rule}", "dir=in", "action=allow", "protocol=TCP",
        "localport=8000", "profile=private,domain",
    ], check=True)
    discovery_rule = "NEXLINK-LAN-Discovery"
    discovery_check = subprocess.run(
        ["netsh", "advfirewall", "firewall", "show", "rule", f"name={discovery_rule}"],
        capture_output=True, text=True, check=False,
    )
    if "LocalPort" not in discovery_check.stdout or "39501" not in discovery_check.stdout:
        subprocess.run([
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={discovery_rule}", "dir=in", "action=allow", "protocol=UDP",
            "localport=39501", "profile=private,domain",
        ], check=False)


def main() -> int:
    _ensure_server_config()
    if "--self-test" in sys.argv:
        from app.main import app
        required = {"/health", "/api/v1/remote/sessions"}
        paths = {getattr(route, "path", "") for route in app.routes}
        missing = sorted(required - paths)
        print("NEXLINK Server package:", "OK" if app else "MISSING")
        print("Required routes:", "OK" if not missing else "MISSING " + ", ".join(missing))
        return 0 if app and not missing else 1

    _start_infrastructure()
    _configure_api_firewall()
    from nexlink_discovery import DiscoveryResponder
    from app.main import app
    import uvicorn
    discovery = DiscoveryResponder(api_port=int(os.environ.get("PORT", "8000"))).start()
    try:
        uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), log_level="info")
    finally:
        discovery.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
