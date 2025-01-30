import os
import platform

import psutil
from fastapi.routing import APIRouter

router = APIRouter()


def is_docker():
    """Check if the script is running inside a Docker container."""
    # Check for /.dockerenv file
    if os.path.exists("/.dockerenv"):
        return True
    # Check for Docker-specific cgroup entries
    if os.path.isfile("/proc/1/cgroup"):
        with open("/proc/1/cgroup", "rt") as f:
            return any("docker" in line or "kubepods" in line for line in f)
    return False


def get_cpu_limit():
    """Get the CPU limit set for the container or system."""
    if platform.system() == "Linux" and is_docker():
        # Check for cgroups v1
        cpu_quota_path = "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"
        cpu_period_path = "/sys/fs/cgroup/cpu/cpu.cfs_period_us"
        if os.path.exists(cpu_quota_path) and os.path.exists(cpu_period_path):
            with open(cpu_quota_path, "r") as f:
                cpu_quota = int(f.read())
            with open(cpu_period_path, "r") as f:
                cpu_period = int(f.read())
            if cpu_quota > 0 and cpu_period > 0:
                cpu_limit = cpu_quota / cpu_period
                return cpu_limit
            else:
                return psutil.cpu_count()
        # Check for cgroups v2
        cpu_max_path = "/sys/fs/cgroup/cpu.max"
        if os.path.exists(cpu_max_path):
            with open(cpu_max_path, "r") as f:
                cpu_max = f.read().strip()
            cpu_quota_str, cpu_period_str = cpu_max.split()
            if cpu_quota_str == "max":
                return psutil.cpu_count()
            else:
                cpu_quota = int(cpu_quota_str)
                cpu_period = int(cpu_period_str)
                if cpu_quota > 0 and cpu_period > 0:
                    cpu_limit = cpu_quota / cpu_period
                    return cpu_limit
        # Default to system CPU count
        return psutil.cpu_count()
    else:
        # On Windows or outside Docker
        return psutil.cpu_count()


def get_memory_limit():
    """Get the memory limit set for the container or system."""
    if platform.system() == "Linux" and is_docker():
        # Check for cgroups v1
        memory_limit_path = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
        if os.path.exists(memory_limit_path):
            with open(memory_limit_path, "r") as f:
                mem_limit = int(f.read())
            # Adjust if no limit is set
            if mem_limit > psutil.virtual_memory().total:
                mem_limit = psutil.virtual_memory().total
            return mem_limit
        # Check for cgroups v2
        memory_max_path = "/sys/fs/cgroup/memory.max"
        if os.path.exists(memory_max_path):
            with open(memory_max_path, "r") as f:
                mem_limit_str = f.read().strip()
            if mem_limit_str == "max":
                return psutil.virtual_memory().total
            else:
                mem_limit = int(mem_limit_str)
            return mem_limit
        # Default to system memory
        return psutil.virtual_memory().total
    else:
        # On Windows or outside Docker
        return psutil.virtual_memory().total


def get_current_memory_usage():
    """Get the current memory usage of the container or process."""
    if platform.system() == "Linux" and is_docker():
        # Check for cgroups v1
        memory_usage_path = "/sys/fs/cgroup/memory/memory.usage_in_bytes"
        if os.path.exists(memory_usage_path):
            with open(memory_usage_path, "r") as f:
                mem_usage = int(f.read())
            return mem_usage
        # Check for cgroups v2
        memory_current_path = "/sys/fs/cgroup/memory.current"
        if os.path.exists(memory_current_path):
            with open(memory_current_path, "r") as f:
                mem_usage = int(f.read())
            return mem_usage
    # Default to process memory usage
    process = psutil.Process(os.getpid())
    return process.memory_info().rss


async def get_current_cpu_usage():
    """Get the current CPU usage of the process."""
    process = psutil.Process(os.getpid())
    # Call twice to get accurate reading
    # process.cpu_percent(interval=None)
    # await asyncio.sleep(
    #     1
    # )  # Wait asynchronously for a second to get an accurate reading
    return process.cpu_percent(interval=None)


@router.get("/summary")
async def get_stats_summary():
    """FastAPI endpoint to retrieve system stats."""
    cpu_limit = get_cpu_limit()
    mem_limit = get_memory_limit()
    mem_usage = get_current_memory_usage()
    cpu_usage_percent = await get_current_cpu_usage()
    stats = {
        "is_docker": is_docker(),
        "cpu_core_limit": cpu_limit,
        "cpu_usage_percent": cpu_usage_percent,
        "memory_limit_mb": mem_limit / 1024 / 1024,
        "memory_usage_mb": mem_usage / 1024 / 1024,
    }
    return stats
