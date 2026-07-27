"""System control — volume, brightness, power, processes, windows, clipboard, network, weather."""

import ast
import asyncio
import ctypes
import json
import operator
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil


class SystemControl:
    """Provides system-level operations for voice-command execution."""

    # ── Volume ──────────────────────────────────────────────

    async def get_volume(self) -> Dict[str, Any]:
        """Get current volume level (0-100) and mute state."""
        try:
            result = await self._run_shell(
                'powershell -NoProfile -Command "Get-AudioDevice -PlaybackVolume"'
            )
            vol = int(result.strip()) if result.strip().isdigit() else -1
            return {"volume": vol, "muted": False, "method": "audio_device"}
        except Exception:
            return {
                "volume": -1,
                "muted": False,
                "method": "unavailable",
                "message": "Volume control requires nircmd or PowerShell Audio module. "
                           "Install: Install-Module AudioDeviceCmdlets",
            }

    async def set_volume(self, level: int) -> Dict[str, Any]:
        """Set volume to specific level (0-100)."""
        level = max(0, min(100, level))
        try:
            val = int(level * 655.35)
            await self._run_shell(f"nircmd setsysvolume {val}")
            return {"volume": level, "status": "ok"}
        except Exception:
            pass
        try:
            await self._run_shell(
                f'powershell -NoProfile -Command "Set-AudioDevice -PlaybackVolume {level}"'
            )
            return {"volume": level, "status": "ok"}
        except Exception:
            pass
        return {"volume": level, "status": "partial", "message": "Install nircmd for reliable volume control"}

    async def volume_up(self, step: int = 5) -> Dict[str, Any]:
        """Increase volume by step."""
        try:
            await self._run_shell("nircmd setsysvolume +2000")
            return {"status": "ok", "action": "volume_up"}
        except Exception:
            return {"status": "error", "message": "Install nircmd for volume control"}

    async def volume_down(self, step: int = 5) -> Dict[str, Any]:
        """Decrease volume by step."""
        try:
            await self._run_shell("nircmd setsysvolume -2000")
            return {"status": "ok", "action": "volume_down"}
        except Exception:
            return {"status": "error", "message": "Install nircmd for volume control"}

    async def toggle_mute(self) -> Dict[str, Any]:
        """Toggle system mute."""
        try:
            await self._run_shell("nircmd mutesysvolume 2")
            return {"status": "ok", "action": "mute_toggled"}
        except Exception:
            pass
        try:
            await self._run_shell(
                "powershell -NoProfile -Command \"(New-Object -ComObject WScript.Shell).SendKeys('{VOLUME_MUTE}')\""
            )
            return {"status": "ok", "action": "mute_toggled"}
        except Exception:
            return {"status": "error", "message": "Mute toggle unavailable"}

    # ── Brightness ──────────────────────────────────────────

    async def get_brightness(self) -> Dict[str, Any]:
        """Get current screen brightness."""
        try:
            result = await self._run_shell(
                'powershell -NoProfile -Command '
                '"(Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightness).CurrentBrightness"'
            )
            brightness = int(result.strip())
            return {"brightness": brightness, "status": "ok"}
        except Exception:
            return {"brightness": -1, "status": "unavailable"}

    async def set_brightness(self, level: int) -> Dict[str, Any]:
        """Set screen brightness (0-100)."""
        level = max(0, min(100, level))
        try:
            await self._run_shell(
                'powershell -NoProfile -Command '
                f'"(Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"'
            )
            return {"brightness": level, "status": "ok"}
        except Exception:
            return {"brightness": level, "status": "unavailable"}

    # ── Power Management ────────────────────────────────────

    async def lock_screen(self) -> Dict[str, Any]:
        """Lock the Windows session."""
        await self._run_shell("rundll32.exe user32.dll,LockWorkStation")
        return {"action": "lock", "status": "ok"}

    async def sleep_pc(self) -> Dict[str, Any]:
        """Put PC to sleep."""
        await self._run_shell("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return {"action": "sleep", "status": "ok"}

    async def hibernate_pc(self) -> Dict[str, Any]:
        """Hibernate the PC."""
        await self._run_shell("rundll32.exe powrprof.dll,SetSuspendState 1,1,0")
        return {"action": "hibernate", "status": "ok"}

    async def shutdown_pc(self, delay: int = 0) -> Dict[str, Any]:
        """Shutdown the PC. delay in seconds."""
        await self._run_shell(f"shutdown /s /t {delay}")
        return {"action": "shutdown", "delay": delay, "status": "ok"}

    async def restart_pc(self, delay: int = 0) -> Dict[str, Any]:
        """Restart the PC."""
        await self._run_shell(f"shutdown /r /t {delay}")
        return {"action": "restart", "delay": delay, "status": "ok"}

    async def cancel_shutdown(self) -> Dict[str, Any]:
        """Cancel a pending shutdown."""
        await self._run_shell("shutdown /a")
        return {"action": "cancel_shutdown", "status": "ok"}

    # ── Network ─────────────────────────────────────────────

    async def get_network_info(self) -> Dict[str, Any]:
        """Get network information: IP, hostname, adapters."""
        info: Dict[str, Any] = {}
        try:
            info["hostname"] = socket.gethostname()
            info["local_ip"] = socket.gethostbyname(info["hostname"])
        except Exception:
            info["local_ip"] = "unknown"

        try:
            result = await self._run_shell(
                'powershell -NoProfile -Command '
                '"(Invoke-WebRequest -Uri https://api.ipify.org -UseBasicParsing -TimeoutSec 5).Content"'
            )
            info["public_ip"] = result.strip()
        except Exception:
            info["public_ip"] = "unknown"

        try:
            addrs = psutil.net_if_addrs()
            info["adapters"] = list(addrs.keys())
        except Exception:
            info["adapters"] = []

        try:
            conns = psutil.net_connections(kind="inet")
            info["active_connections"] = len([c for c in conns if c.status == "ESTABLISHED"])
        except Exception:
            info["active_connections"] = 0

        return info

    async def ping(self, host: str) -> Dict[str, Any]:
        """Ping a host and return latency."""
        result = await self._run_shell(f"ping -n 4 {host}")
        match = re.search(r"Average = (\d+)ms", result)
        if match:
            return {"host": host, "latency_ms": int(match.group(1)), "status": "ok"}
        return {"host": host, "status": "error", "raw": result[:200]}

    async def get_wifi_info(self) -> Dict[str, Any]:
        """Get current WiFi connection info."""
        try:
            result = await self._run_shell("netsh wlan show interfaces")
            ssid_match = re.search(r"SSID\s*:\s*(.+)", result)
            signal_match = re.search(r"Signal\s*:\s*(\d+)%", result)
            speed_match = re.search(r"Speed\s*:\s*(.+)", result)
            return {
                "ssid": ssid_match.group(1).strip() if ssid_match else "unknown",
                "signal_percent": int(signal_match.group(1)) if signal_match else 0,
                "speed": speed_match.group(1).strip() if speed_match else "unknown",
                "status": "ok",
            }
        except Exception:
            return {"status": "unavailable"}

    async def toggle_wifi(self) -> Dict[str, Any]:
        """Toggle WiFi on/off."""
        try:
            result = await self._run_shell('netsh interface show interface name="Wi-Fi"')
            if "Disabled" in result:
                await self._run_shell('netsh interface set interface name="Wi-Fi" admin=enable')
                return {"action": "wifi_enabled", "status": "ok"}
            else:
                await self._run_shell('netsh interface set interface name="Wi-Fi" admin=disable')
                return {"action": "wifi_disabled", "status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def toggle_bluetooth(self) -> Dict[str, Any]:
        """Toggle Bluetooth on/off via PowerShell."""
        try:
            await self._run_shell('powershell -NoProfile -Command "Start-Process ms-settings:bluetooth"')
            return {"action": "bluetooth_settings_opened", "status": "ok"}
        except Exception:
            return {"status": "error"}

    # ── Process Management ──────────────────────────────────

    async def list_processes(self, limit: int = 20) -> Dict[str, Any]:
        """List running processes sorted by CPU usage."""
        procs: List[Dict[str, Any]] = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                info = p.info
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu": round(info["cpu_percent"] or 0, 1),
                    "memory_mb": round(
                        (info["memory_percent"] or 0)
                        * psutil.virtual_memory().total
                        / 100
                        / 1024
                        / 1024,
                        1,
                    ),
                    "status": info["status"],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x["cpu"], reverse=True)
        return {"processes": procs[:limit], "total": len(procs)}

    async def kill_process(self, name: str = "", pid: int = 0) -> Dict[str, Any]:
        """Kill a process by name or PID."""
        if pid:
            try:
                p = psutil.Process(pid)
                p_name = p.name()
                p.terminate()
                return {"action": "killed", "pid": pid, "name": p_name, "status": "ok"}
            except psutil.NoSuchProcess:
                return {"status": "error", "message": f"Process {pid} not found"}
            except psutil.AccessDenied:
                return {"status": "error", "message": f"Access denied killing PID {pid}"}
        elif name:
            killed = 0
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    if name.lower() in p.info["name"].lower():
                        p.terminate()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return {"action": "killed", "name": name, "count": killed, "status": "ok"}
        return {"status": "error", "message": "Provide name or pid"}

    async def search_apps(self, query: str = "") -> Dict[str, Any]:
        """Search for installed applications."""
        apps: List[Dict[str, str]] = []
        search_paths = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]

        for search_path in search_paths:
            if not search_path.exists():
                continue
            try:
                for f in search_path.rglob("*.lnk"):
                    if not query or query.lower() in f.stem.lower():
                        apps.append({"name": f.stem, "path": str(f)})
                        if len(apps) >= 30:
                            break
                for f in search_path.rglob("*.exe"):
                    if not query or query.lower() in f.stem.lower():
                        apps.append({"name": f.stem, "path": str(f)})
                        if len(apps) >= 30:
                            break
            except PermissionError:
                continue
            if len(apps) >= 30:
                break

        return {"apps": apps[:30], "count": len(apps)}

    # ── Clipboard ───────────────────────────────────────────

    async def get_clipboard(self) -> Dict[str, Any]:
        """Get current clipboard content."""
        try:
            result = await self._run_shell('powershell -NoProfile -Command "Get-Clipboard"')
            return {"content": result.strip(), "status": "ok"}
        except Exception:
            return {"status": "error"}

    async def set_clipboard(self, text: str) -> Dict[str, Any]:
        """Set clipboard content."""
        try:
            escaped = text.replace("'", "''")
            await self._run_shell(
                f"powershell -NoProfile -Command \"Set-Clipboard -Value '{escaped}'\""
            )
            return {"status": "ok", "action": "clipboard_set"}
        except Exception:
            return {"status": "error"}

    # ── Window Management ───────────────────────────────────

    async def minimize_windows(self) -> Dict[str, Any]:
        """Minimize all windows (show desktop)."""

        def _do():
            ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x4D, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x4D, 0, 2, 0)
            ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)

        try:
            await asyncio.to_thread(_do)
            return {"action": "minimize_all", "status": "ok"}
        except Exception:
            return {"status": "error"}

    async def get_active_window(self) -> Dict[str, Any]:
        """Get info about the currently active window."""

        def _do():
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value, hwnd

        try:
            title, hwnd = await asyncio.to_thread(_do)
            return {"title": title, "hwnd": hwnd, "status": "ok"}
        except Exception:
            return {"status": "error"}

    # ── Weather ─────────────────────────────────────────────

    async def get_weather(self, city: str = "") -> Dict[str, Any]:
        """Get current weather using wttr.in (free, no API key)."""
        try:
            loc = city if city else ""
            result = await self._run_shell(f'curl -s "wttr.in/{loc}?format=j1"')
            data = json.loads(result)
            current = data.get("current_condition", [{}])[0]
            return {
                "temp_c": current.get("temp_C", "?"),
                "temp_f": current.get("temp_F", "?"),
                "feels_like_c": current.get("FeelsLikeC", "?"),
                "humidity": current.get("humidity", "?"),
                "wind_kmph": current.get("windspeedKmph", "?"),
                "wind_dir": current.get("winddir16Point", "?"),
                "description": current.get("weatherDesc", [{}])[0].get("value", "?"),
                "visibility_km": current.get("visibility", "?"),
                "uv_index": current.get("uvIndex", "?"),
                "location": (
                    data.get("nearest_area", [{}])[0]
                    .get("areaName", [{}])[0]
                    .get("value", city or "auto-detected")
                ),
                "status": "ok",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def get_forecast(self, city: str = "", days: int = 3) -> Dict[str, Any]:
        """Get multi-day weather forecast."""
        try:
            loc = city if city else ""
            result = await self._run_shell(f'curl -s "wttr.in/{loc}?format=j1"')
            data = json.loads(result)
            forecasts = []
            for day in data.get("weather", [])[:days]:
                hourly = day.get("hourly", [])
                desc = (
                    hourly[4].get("weatherDesc", [{}])[0].get("value", "?")
                    if len(hourly) > 4
                    else "?"
                )
                forecasts.append({
                    "date": day.get("date", ""),
                    "max_temp_c": day.get("maxtempC", "?"),
                    "min_temp_c": day.get("mintempC", "?"),
                    "description": desc,
                })
            return {"forecasts": forecasts, "status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Audio/Media Control ─────────────────────────────────

    async def media_play_pause(self) -> Dict[str, Any]:
        """Toggle media play/pause."""

        def _do():
            ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)

        try:
            await asyncio.to_thread(_do)
            return {"action": "media_toggle", "status": "ok"}
        except Exception:
            return {"status": "error"}

    async def media_next(self) -> Dict[str, Any]:
        """Skip to next track."""

        def _do():
            ctypes.windll.user32.keybd_event(0xB0, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xB0, 0, 2, 0)

        try:
            await asyncio.to_thread(_do)
            return {"action": "media_next", "status": "ok"}
        except Exception:
            return {"status": "error"}

    async def media_previous(self) -> Dict[str, Any]:
        """Go to previous track."""

        def _do():
            ctypes.windll.user32.keybd_event(0xB1, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xB1, 0, 2, 0)

        try:
            await asyncio.to_thread(_do)
            return {"action": "media_previous", "status": "ok"}
        except Exception:
            return {"status": "error"}

    # ── Calculator ──────────────────────────────────────────

    async def calculate(self, expression: str) -> Dict[str, Any]:
        """Evaluate a math expression safely."""
        allowed_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        try:
            tree = ast.parse(expression, mode="eval")
            result = _eval_node(tree.body, allowed_ops)
            return {"expression": expression, "result": result, "status": "ok"}
        except Exception as e:
            return {"expression": expression, "status": "error", "message": str(e)}

    # ── File Operations (quick access) ──────────────────────

    async def open_explorer(self, path: str = "") -> Dict[str, Any]:
        """Open Windows Explorer at a path."""
        if not path:
            path = str(Path.home())
        await self._run_shell(f'explorer "{path}"')
        return {"action": "open_explorer", "path": path, "status": "ok"}

    async def open_terminal(self, path: str = "") -> Dict[str, Any]:
        """Open a terminal at a path."""
        if path:
            await self._run_shell(f'wt -d "{path}"')
        else:
            await self._run_shell("wt")
        return {"action": "open_terminal", "path": path, "status": "ok"}

    # ── Utility ─────────────────────────────────────────────

    async def get_battery(self) -> Dict[str, Any]:
        """Get battery status (laptops only)."""
        try:
            battery = psutil.sensors_battery()
            if battery:
                return {
                    "percent": battery.percent,
                    "plugged": battery.power_plugged,
                    "remaining_min": battery.secsleft // 60 if battery.secsleft > 0 else 0,
                    "status": "ok",
                }
        except Exception:
            pass
        return {"status": "no_battery", "message": "No battery detected (desktop PC)"}

    async def get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage for all drives."""
        disks: List[Dict[str, Any]] = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "drive": part.device,
                    "total_gb": round(usage.total / 1024**3, 1),
                    "used_gb": round(usage.used / 1024**3, 1),
                    "free_gb": round(usage.free / 1024**3, 1),
                    "percent": round(usage.percent, 1),
                })
            except PermissionError:
                continue
        return {"disks": disks, "status": "ok"}

    async def get_uptime(self) -> Dict[str, Any]:
        """Get system uptime."""
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot
        days = uptime.days
        hours = uptime.seconds // 3600
        mins = (uptime.seconds % 3600) // 60
        return {"uptime": f"{days}d {hours}h {mins}m", "boot_time": boot.isoformat(), "status": "ok"}

    # ── Internal ────────────────────────────────────────────

    async def _run_shell(self, cmd: str, timeout: int = 15) -> str:
        """Run a shell command and return stdout."""
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return ""


def _eval_node(node: ast.AST, allowed_ops: dict) -> Any:
    """Safely evaluate a math AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in allowed_ops:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _eval_node(node.left, allowed_ops)
        right = _eval_node(node.right, allowed_ops)
        return allowed_ops[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in allowed_ops:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return allowed_ops[op_type](_eval_node(node.operand, allowed_ops))
    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")
