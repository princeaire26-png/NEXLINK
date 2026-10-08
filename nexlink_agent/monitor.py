"""Cross-platform system metrics for NEXLINK."""
from __future__ import annotations
import platform, time, socket, psutil
from datetime import datetime, timezone

_BOOT=time.time()
def collect()->dict:
    vm=psutil.virtual_memory(); du=psutil.disk_usage(psutil.disk_partitions()[0].mountpoint if psutil.disk_partitions() else "/")
    return {
      "cpu_percent": psutil.cpu_percent(interval=0.2),
      "cpu_cores": psutil.cpu_count(logical=True) or 1,
      "memory_total_bytes": vm.total, "memory_used_bytes": vm.used, "memory_percent": vm.percent,
      "disk_total_bytes": du.total, "disk_used_bytes": du.used, "disk_percent": du.percent,
      "uptime_seconds": int(time.time()-psutil.boot_time()),
      "hostname": socket.gethostname(), "os_name": platform.system(), "os_version": platform.version(),
      "architecture": platform.machine(), "recorded_at": datetime.now(timezone.utc).isoformat()
    }
