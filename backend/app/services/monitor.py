"""System monitor — real-time CPU, RAM, disk, network, process stats."""

import asyncio
import json
import os
import platform
import shutil
import time
from typing import Dict, Any, List

import psutil


def get_snapshot() -> Dict[str, Any]:
    """Get a single system snapshot."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_freq = psutil.cpu_freq()
    cpu_count = psutil.cpu_count()

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    disk_parts = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk_parts.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": usage.percent,
            })
        except PermissionError:
            continue

    net = psutil.net_io_counters()
    boot = psutil.boot_time()
    uptime_seconds = int(time.time() - boot)

    # Top processes by CPU
    top_procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            if info["cpu_percent"] and info["cpu_percent"] > 0:
                top_procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    top_procs.sort(key=lambda p: p.get("cpu_percent", 0), reverse=True)
    top_procs = top_procs[:10]

    # Top processes by memory
    top_mem = []
    for proc in psutil.process_iter(["pid", "name", "memory_percent", "memory_info"]):
        try:
            info = proc.info
            if info["memory_percent"] and info["memory_percent"] > 0:
                top_mem.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "memory_percent": round(info["memory_percent"], 1),
                    "rss_mb": round(info["memory_info"].rss / (1024**2), 1) if info["memory_info"] else 0,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    top_mem.sort(key=lambda p: p.get("memory_percent", 0), reverse=True)
    top_mem = top_mem[:10]

    return {
        "timestamp": time.time(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "hostname": platform.node(),
            "uptime_seconds": uptime_seconds,
        },
        "cpu": {
            "percent": cpu_percent,
            "freq_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
            "cores_physical": cpu_count,
            "cores_logical": psutil.cpu_count(logical=True),
            "per_core": psutil.cpu_percent(interval=0, percpu=True),
        },
        "memory": {
            "total_gb": round(mem.total / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "percent": mem.percent,
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_used_gb": round(swap.used / (1024**3), 2),
            "swap_percent": swap.percent,
        },
        "disk": {
            "partitions": disk_parts,
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
            "connections": len(psutil.net_connections()),
        },
        "processes": {
            "total": len(list(psutil.process_iter())),
            "top_cpu": [{"pid": p["pid"], "name": p["name"], "cpu_percent": round(p["cpu_percent"], 1)} for p in top_procs],
            "top_memory": top_mem,
        },
    }


# For network rate calculation (delta between snapshots)
_prev_net = {"bytes_sent": 0, "bytes_recv": 0, "time": 0}


def get_network_rate() -> Dict[str, float]:
    """Get network send/receive rate in bytes/sec."""
    global _prev_net
    net = psutil.net_io_counters()
    now = time.time()
    dt = now - _prev_net["time"]
    if dt < 0.1:
        dt = 1.0
    rate_sent = (net.bytes_sent - _prev_net["bytes_sent"]) / dt if _prev_net["time"] > 0 else 0
    rate_recv = (net.bytes_recv - _prev_net["bytes_recv"]) / dt if _prev_net["time"] > 0 else 0
    _prev_net = {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "time": now}
    return {
        "bytes_sent_per_sec": max(0, rate_sent),
        "bytes_recv_per_sec": max(0, rate_recv),
    }


async def monitor_stream(interval: float = 2.0):
    """Async generator that yields system snapshots."""
    # Prime the CPU percent tracker
    psutil.cpu_percent(interval=0, percpu=True)
    _prev_net["bytes_sent"] = psutil.net_io_counters().bytes_sent
    _prev_net["bytes_recv"] = psutil.net_io_counters().bytes_recv
    _prev_net["time"] = time.time()
    await asyncio.sleep(1)

    while True:
        snapshot = get_snapshot()
        rates = get_network_rate()
        snapshot["network"]["rate_sent"] = round(rates["bytes_sent_per_sec"], 0)
        snapshot["network"]["rate_recv"] = round(rates["bytes_recv_per_sec"], 0)
        snapshot["network"]["rate_sent_human"] = _human_bytes(rates["bytes_sent_per_sec"])
        snapshot["network"]["rate_recv_human"] = _human_bytes(rates["bytes_recv_per_sec"])
        yield snapshot
        await asyncio.sleep(interval)


def _human_bytes(b: float) -> str:
    if b < 1024:
        return f"{b:.0f} B/s"
    elif b < 1024**2:
        return f"{b/1024:.1f} KB/s"
    elif b < 1024**3:
        return f"{b/1024**2:.1f} MB/s"
    else:
        return f"{b/1024**3:.2f} GB/s"


def get_processes() -> Dict[str, Any]:
    """List all processes with CPU/memory usage."""
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": round(info.get("cpu_percent", 0) or 0, 1),
                "memory_percent": round(info.get("memory_percent", 0) or 0, 1),
                "status": info.get("status", "unknown"),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda p: p["cpu_percent"], reverse=True)
    return {"processes": procs[:50], "total": len(procs)}
