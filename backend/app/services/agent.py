import asyncio
import hashlib
import hmac
import json
import logging
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

from .world_model import SituationEngine, WorldGraph, WorldSimulator

log = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "function_declarations": [
            {
                "name": "open_app",
                "description": "Open an application on the user's PC. Pass the app name or path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Name of the app to open (e.g., 'notepad', 'chrome', 'spotify', 'C:\\\\Program Files\\\\...')"}
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "run_command",
                "description": "Run a shell command on the user's PC. Runs in the user's home directory — relative paths resolve there. Prefer relative paths like Desktop/moon_link instead of guessing C:\\Users\\<name>. Use with caution.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The command to execute"},
                        "cwd": {"type": "string", "description": "Optional working directory"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "list_files",
                "description": "List files and directories at a given path on the user's PC. Relative paths resolve against the user's home folder (e.g. 'Desktop' or 'Documents/reports').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to list (default: user home)"},
                        "pattern": {"type": "string", "description": "Optional glob pattern (e.g., '*.txt', '**/*.py')"}
                    }
                }
            },
            {
                "name": "read_file",
                "description": "Read the contents of a text file on the user's PC. Relative paths resolve against the user's home folder.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Full path to the file"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write content to a file on the user's PC. Creates the file if it doesn't exist. Relative paths resolve against the user's home folder (e.g. 'Desktop/report.txt').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Full path to the file"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "open_url",
                "description": "Open a URL in the user's default browser, OR open a local file path (e.g. a file you just created) in the user's browser. Pass either an http(s) URL or a file path/name from the user's workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "http(s) URL or local file path to open in the user's browser"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "send_notification",
                "description": "Send a push notification to the user's connected phone/device.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Notification title"},
                        "body": {"type": "string", "description": "Notification body text"},
                        "device_id": {"type": "string", "description": "Optional specific device ID (omit for all devices)"}
                    },
                    "required": ["title", "body"]
                }
            },
            {
                "name": "device_command",
                "description": "Send a command to execute on the user's connected desktop/phone. Prefer this for creating folders, writing files, or running shell commands ON THE USER'S COMPUTER (not on the server).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device ID to send command to (omit for first available device)"},
                        "kind": {"type": "string", "enum": ["open_url", "open_app", "reveal_path", "create_directory", "write_file", "run_command"], "description": "Type of command"},
                        "payload": {"type": "object", "description": "Command payload. open_url: {'url'}. open_app: {'app'}. reveal_path/create_directory/write_file/run_command: {'path'} / {'path','content'} / {'command'}.", "properties": {}},
                        "requires_confirmation": {"type": "boolean", "description": "Whether the device should ask user confirmation before executing"}
                    },
                    "required": ["kind", "payload"]
                }
            },
            {
                "name": "list_devices",
                "description": "List all devices connected to SALAR (phones, desktops, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "whatsapp_send",
                "description": "Send a WhatsApp message to a contact. Provide either a JID or phone number.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone": {"type": "string", "description": "Phone number with country code (e.g., '1234567890')"},
                        "to": {"type": "string", "description": "WhatsApp JID (e.g., '1234567890@s.whatsapp.net')"},
                        "text": {"type": "string", "description": "Message text to send"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "whatsapp_read",
                "description": "Read recent WhatsApp messages from a specific chat.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "jid": {"type": "string", "description": "WhatsApp JID of the chat (e.g., '1234567890@s.whatsapp.net')"},
                        "limit": {"type": "integer", "description": "Number of messages to retrieve (default 10)"}
                    },
                    "required": ["jid"]
                }
            },
            {
                "name": "whatsapp_list_chats",
                "description": "List recent WhatsApp conversations.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "whatsapp_search",
                "description": "Search across recent WhatsApp messages for a keyword.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "whatsapp_qr",
                "description": "Get the WhatsApp pairing QR code image (data URL) and current connection status for the user. Use this when the user asks to see or scan the WhatsApp QR code, or to link/pair WhatsApp. The returned 'image' is a data URL that can be rendered or shown. If no QR is available yet, it returns status 'connecting' or 'connected'.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "save_memory",
                "description": "Save an important fact or decision to SALAR's long-term memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short title for the memory"},
                        "content": {"type": "string", "description": "Detailed content to remember"}
                    },
                    "required": ["title", "content"]
                }
            },
            {
                "name": "get_current_time",
                "description": "Get the current date and time. Use this when the user asks for the time, date, or today's date.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_system_info",
                "description": "Get information about the user's system (OS, CPU, memory, disk usage).",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "screenshot",
                "description": "Take a screenshot of the user's desktop (PC only, requires Tauri).",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "email_search",
                "description": "Search emails in the user's mailbox. Returns subject, from, date, and message ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "folder": {"type": "string", "description": "Mail folder to search (default: INBOX)"},
                        "query": {"type": "string", "description": "IMAP search query (e.g., 'UNSEEN', 'FROM \"john\"', 'SUBJECT \"meeting\"')"},
                        "limit": {"type": "integer", "description": "Max results (default 20)"}
                    }
                }
            },
            {
                "name": "email_read",
                "description": "Read the full content of a specific email by its message ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "msg_id": {"type": "string", "description": "Message ID from email_search results"},
                        "folder": {"type": "string", "description": "Mail folder (default: INBOX)"}
                    },
                    "required": ["msg_id"]
                }
            },
            {
                "name": "email_send",
                "description": "Send an email from the user's account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string", "description": "Email subject line"},
                        "body": {"type": "string", "description": "Email body text"},
                        "cc": {"type": "string", "description": "CC recipients (comma-separated)"}
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "email_folders",
                "description": "List all mail folders with unread counts.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "email_unread",
                "description": "Get the number of unread emails in a folder.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "folder": {"type": "string", "description": "Mail folder (default: INBOX)"}
                    }
                }
            },
            {
                "name": "calendar_events",
                "description": "Get calendar events for a date range. Default is today and next 7 days.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days_before": {"type": "integer", "description": "Days before today (default 0)"},
                        "days_after": {"type": "integer", "description": "Days after today (default 7)"}
                    }
                }
            },
            {
                "name": "calendar_today",
                "description": "Get today's calendar events.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "calendar_upcoming",
                "description": "Get upcoming events for the next 14 days.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max events to return (default 10)"}
                    }
                }
            },
            {
                "name": "calendar_search",
                "description": "Search calendar events by keyword.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "calendar_add_feed",
                "description": "Add a new iCal calendar feed (Google Calendar public URL, iCloud, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Friendly name for this calendar"},
                        "url": {"type": "string", "description": "iCal feed URL (.ics)"},
                        "color": {"type": "string", "description": "Hex color code (default #5227FF)"}
                    },
                    "required": ["name", "url"]
                }
            },
            {
                "name": "browse_page",
                "description": "Fetch a web page and extract its content, links, and metadata. Returns title, text, links, and images.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "read_article",
                "description": "Read a web article and return clean, readable text content. Good for blog posts, news articles, documentation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL of the article to read"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "browse_links",
                "description": "Extract all links from a web page. Returns link URLs and text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to extract links from"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "file_list",
                "description": "List files and folders in a directory. Returns names, sizes, types, and modification dates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path (default: home directory)"}
                    }
                }
            },
            {
                "name": "file_read",
                "description": "Read the content of a text file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "file_write",
                "description": "Write content to a file (creates or overwrites).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "file_search",
                "description": "Search for files by name in a directory tree.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (filename pattern)"},
                        "path": {"type": "string", "description": "Directory to search in (default: home)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "file_info",
                "description": "Get detailed info about a file (size, type, dates, permissions).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "code_run",
                "description": "Execute Python or JavaScript code in a sandboxed environment. Returns stdout, stderr, and exit code.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Code to execute"},
                        "language": {"type": "string", "description": "Language: 'python' or 'javascript'"}
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "create_task",
                "description": "Create a new task in the task manager",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task title"},
                        "description": {"type": "string", "description": "Task description"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"], "description": "Priority level"},
                        "due_date": {"type": "string", "description": "Due date in ISO format (YYYY-MM-DD)"},
                    },
                    "required": ["title"],
                },
            },
            {
                "name": "list_tasks",
                "description": "List tasks, optionally filtered by status",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["todo", "in_progress", "done", "archived"], "description": "Filter by status"},
                    },
                },
            },
            {
                "name": "set_reminder",
                "description": "Set a reminder for a specific date and time",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Reminder title"},
                        "message": {"type": "string", "description": "Reminder message"},
                        "remind_at": {"type": "string", "description": "When to remind (ISO format)"},
                        "recurrence": {"type": "string", "enum": ["none", "daily", "weekly", "monthly"], "description": "Recurrence pattern"},
                    },
                    "required": ["title", "remind_at"],
                },
            },
            {
                "name": "list_reminders",
                "description": "List upcoming reminders",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max reminders to return"},
                    },
                },
            },
            {
                "name": "search_knowledge",
                "description": "Search the knowledge base for information from uploaded documents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "list_knowledge",
                "description": "List uploaded knowledge documents",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "set_volume",
                "description": "Set system volume level or toggle mute",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["set", "up", "down", "mute"], "description": "Volume action"},
                        "level": {"type": "integer", "description": "Volume level 0-100 (for 'set')"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "set_brightness",
                "description": "Set screen brightness level",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "integer", "description": "Brightness level 0-100"}
                    },
                    "required": ["level"]
                }
            },
            {
                "name": "power_control",
                "description": "Control PC power state",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["lock", "sleep", "hibernate", "shutdown", "restart", "cancel_shutdown"], "description": "Power action"},
                        "delay": {"type": "integer", "description": "Delay in seconds for shutdown/restart (default 0)"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "network_info",
                "description": "Get network info, ping a host, or get WiFi details",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["info", "ping", "wifi", "toggle_wifi"], "description": "Network action"},
                        "host": {"type": "string", "description": "Host to ping"}
                    }
                }
            },
            {
                "name": "get_weather",
                "description": "Get current weather or forecast for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name (auto-detect if empty)"},
                        "forecast": {"type": "boolean", "description": "Get multi-day forecast"}
                    }
                }
            },
            {
                "name": "manage_process",
                "description": "List or kill running processes",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["list", "kill"], "description": "Process action"},
                        "name": {"type": "string", "description": "Process name to kill"},
                        "pid": {"type": "integer", "description": "Process PID to kill"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "clipboard",
                "description": "Get or set clipboard content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["get", "set"], "description": "Clipboard action"},
                        "text": {"type": "string", "description": "Text to set (for 'set')"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "media_control",
                "description": "Control media playback",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["play_pause", "next", "previous"], "description": "Media action"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "window_control",
                "description": "Manage windows (minimize all, get active window)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["minimize_all", "get_active"], "description": "Window action"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "search_apps",
                "description": "Search for installed applications on the PC",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "App name to search for"}
                    }
                }
            },
            {
                "name": "calculate",
                "description": "Evaluate a math expression",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression to evaluate (e.g., '2+2', '15*0.3', 'sqrt(144)')"}
                    },
                    "required": ["expression"]
                }
            },
            {
                "name": "get_battery",
                "description": "Get battery status for laptops",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_disk_usage",
                "description": "Get disk usage for all drives",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_uptime",
                "description": "Get system uptime since last boot",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "open_explorer",
                "description": "Open Windows Explorer at a specific path",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Folder path to open (default: home)"}
                    }
                }
            },
            {
                "name": "list_documents",
                "description": "List all uploaded documents (PDFs, text files, etc.)",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "search_documents",
                "description": "Search uploaded documents by filename or content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "list_memories",
                "description": "List all saved memories (facts, decisions, notes)",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "search_memories",
                "description": "Search saved memories by keyword",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "delete_memory",
                "description": "Delete a saved memory by its ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "Memory ID to delete"}
                    },
                    "required": ["memory_id"]
                }
            },
            {
                "name": "get_monitor_stats",
                "description": "Get real-time system stats: CPU, RAM, disk, network usage",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "list_processes",
                "description": "List running processes with CPU/memory usage",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "create_alert_rule",
                "description": "Create a proactive alert rule (disk usage, CPU, memory, email, service health)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Alert rule name"},
                        "alert_type": {"type": "string", "enum": ["disk_usage", "cpu_usage", "memory_usage", "email_from", "email_unread", "service_down"], "description": "Type of alert"},
                        "severity": {"type": "string", "enum": ["info", "warning", "critical"], "description": "Alert severity"},
                        "config": {"type": "object", "description": "Type-specific config. disk_usage: {threshold: 90, mountpoint: 'C:\\\\'}. cpu_usage: {threshold: 95}. memory_usage: {threshold: 90}. email_from: {sender: 'boss@co.com'}. email_unread: {threshold: 10}. service_down: {url: 'https://...'}."}
                    },
                    "required": ["name", "alert_type"]
                }
            },
            {
                "name": "list_alert_rules",
                "description": "List all configured alert rules",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "list_triggered_alerts",
                "description": "List recent triggered alerts",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max alerts to return (default 20)"}
                    }
                }
            },
            {
                "name": "create_workspace",
                "description": "Create a new workspace for organizing tasks, reminders, and knowledge",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Workspace name"},
                        "icon": {"type": "string", "description": "Emoji icon (default ðŸ“)"}
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "list_workspaces",
                "description": "List all workspaces",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "update_task",
                "description": "Update a task's title, description, priority, or due date",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID"},
                        "title": {"type": "string", "description": "New title"},
                        "description": {"type": "string", "description": "New description"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"], "description": "New priority"},
                        "due_date": {"type": "string", "description": "New due date (ISO format)"}
                    },
                    "required": ["task_id"]
                }
            },
            {
                "name": "set_task_status",
                "description": "Change a task's status (todo, in_progress, done, archived)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID"},
                        "status": {"type": "string", "enum": ["todo", "in_progress", "done", "archived"], "description": "New status"}
                    },
                    "required": ["task_id", "status"]
                }
            },
            {
                "name": "delete_task",
                "description": "Delete a task",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID to delete"}
                    },
                    "required": ["task_id"]
                }
            },
            {
                "name": "task_stats",
                "description": "Get task statistics (counts by status and priority)",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "update_reminder",
                "description": "Update a reminder's title, time, or recurrence",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "Reminder ID"},
                        "title": {"type": "string", "description": "New title"},
                        "message": {"type": "string", "description": "New message"},
                        "remind_at": {"type": "string", "description": "New time (ISO format)"},
                        "recurrence": {"type": "string", "enum": ["none", "daily", "weekly", "monthly"], "description": "Recurrence"}
                    },
                    "required": ["reminder_id"]
                }
            },
            {
                "name": "delete_reminder",
                "description": "Delete a reminder",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "Reminder ID to delete"}
                    },
                    "required": ["reminder_id"]
                }
            },
            {
                "name": "mark_reminder_done",
                "description": "Mark a reminder as completed",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "Reminder ID to mark done"}
                    },
                    "required": ["reminder_id"]
                }
            },
            {
                "name": "list_workflows",
                "description": "List all workflow automations",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "create_workflow",
                "description": "Create a workflow automation (keyword trigger, schedule, or cron)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Workflow name"},
                        "trigger_type": {"type": "string", "enum": ["keyword", "schedule", "cron", "email_received", "file_created"], "description": "Trigger type"},
                        "trigger_config": {"type": "object", "description": "Trigger config: keyword={keyword: '...'}. schedule={time: '09:00', days: ['mon','tue']}. cron={expression: '0 9 * * 1-5'}."},
                        "actions": {"type": "array", "items": {"type": "object"}, "description": "List of action steps"}
                    },
                    "required": ["name", "trigger_type"]
                }
            },
            {
                "name": "toggle_workflow",
                "description": "Enable or disable a workflow",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string", "description": "Workflow ID"}
                    },
                    "required": ["workflow_id"]
                }
            },
            {
                "name": "run_workflow",
                "description": "Manually trigger a workflow",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string", "description": "Workflow ID to run"}
                    },
                    "required": ["workflow_id"]
                }
            },
            {
                "name": "world_simulate",
                "description": "Run a what-if simulation against the user's world model. Proposes changes (e.g. set a project deadline, mark a build fixed, remove a relation) and predicts which situations would appear, disappear, worsen, or improve. Use BEFORE taking a risky or irreversible action, or when the user asks 'what would happen if...'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string", "enum": ["set_entity_prop", "add_relation", "remove_relation"], "description": "Type of change"},
                                    "params": {"type": "object", "description": "Change parameters: set_entity_prop={entity_type, key, prop, value}. add_relation/remove_relation={from_type, from_key, relation, to_type, to_key}"}
                                },
                                "required": ["action"]
                            },
                            "description": "Proposed changes to simulate"
                        }
                    },
                    "required": ["changes"]
                }
            },
        ]
    }
]


async def execute_tool(name: str, args: Dict[str, Any], user_id: str, db_session=None, is_admin: bool = False, base_url: str = "", jwt_secret: str = "") -> Dict[str, Any]:
    try:
        if name == "open_app":
            return await _open_app(args.get("app_name", ""))
        elif name == "run_command":
            return await _run_command(args.get("command", ""), args.get("cwd"), user_id, db_session)
        elif name == "list_files":
            return await _list_files(args.get("path", str(Path.home())), args.get("pattern"), user_id, db_session)
        elif name == "read_file":
            return await _read_file(args.get("path", ""), user_id, db_session)
        elif name == "write_file":
            return await _write_file(args.get("path", ""), args.get("content", ""), user_id, db_session)
        elif name == "open_url":
            return await _open_url(args.get("url", ""), user_id, db_session, base_url, jwt_secret)
        elif name == "send_notification":
            return await _send_notification(args.get("title", ""), args.get("body", ""), args.get("device_id"), user_id, db_session)
        elif name == "device_command":
            return await _device_command(args.get("device_id"), args.get("kind", ""), args.get("payload", {}), args.get("requires_confirmation", False), user_id, db_session)
        elif name == "list_devices":
            return await _list_devices(user_id, db_session)
        elif name == "whatsapp_send":
            return await _whatsapp_send(args.get("to"), args.get("phone"), args.get("text", ""), user_id, db_session)
        elif name == "whatsapp_read":
            return await _whatsapp_read(args.get("jid", ""), args.get("limit", 10), user_id)
        elif name == "whatsapp_list_chats":
            return await _whatsapp_list_chats(user_id)
        elif name == "whatsapp_search":
            return await _whatsapp_search(args.get("query", ""), user_id)
        elif name == "whatsapp_qr":
            return await _whatsapp_qr(user_id)
        elif name == "email_search":
            return await _email_search(args.get("folder", "INBOX"), args.get("query", "ALL"), args.get("limit", 20), user_id)
        elif name == "email_read":
            return await _email_read(args.get("msg_id", ""), args.get("folder", "INBOX"), user_id)
        elif name == "email_send":
            return await _email_send(args.get("to", ""), args.get("subject", ""), args.get("body", ""), args.get("cc"), user_id)
        elif name == "email_folders":
            return await _email_folders(user_id)
        elif name == "email_unread":
            return await _email_unread(args.get("folder", "INBOX"), user_id)
        elif name == "calendar_events":
            return await _calendar_events(args.get("days_before", 0), args.get("days_after", 7), user_id)
        elif name == "calendar_today":
            return await _calendar_today(user_id)
        elif name == "calendar_upcoming":
            return await _calendar_upcoming(args.get("limit", 10), user_id)
        elif name == "calendar_search":
            return await _calendar_search(args.get("query", ""), user_id)
        elif name == "calendar_add_feed":
            return await _calendar_add_feed(args.get("name", ""), args.get("url", ""), args.get("color", "#5227FF"), user_id)
        elif name == "browse_page":
            return await _browse_page(args.get("url", ""))
        elif name == "read_article":
            return await _read_article(args.get("url", ""))
        elif name == "browse_links":
            return await _browse_links(args.get("url", ""))
        elif name == "file_list":
            return await _file_list(args.get("path", ""), user_id)
        elif name == "file_read":
            return await _file_read(args.get("path", ""), user_id)
        elif name == "file_write":
            return await _file_write(args.get("path", ""), args.get("content", ""), user_id)
        elif name == "file_search":
            return await _file_search(args.get("query", ""), args.get("path", ""), user_id)
        elif name == "file_info":
            return await _file_info(args.get("path", ""), user_id)
        elif name == "code_run":
            return await _code_run(args.get("code", ""), args.get("language", "python"), user_id)
        elif name == "save_memory":
            return await _save_memory(args.get("title", ""), args.get("content", ""), user_id, db_session)
        elif name == "get_current_time":
            now = datetime.now()
            return {"datetime": now.isoformat(), "time": now.strftime("%I:%M %p"), "date": now.strftime("%A, %B %d, %Y")}
        elif name == "get_system_info":
            # When a desktop device is connected, get info from the user's PC
            if user_id and db_session:
                result = await _route_to_local_device("system_info", {}, user_id, db_session)
                if result is not None and result.get("status") != "queued":
                    return result
            return await _get_system_info()
        elif name == "screenshot":
            try:
                from .vision import VisionService
                png = VisionService().capture_screenshot()
                import base64
                return {"status": "ok", "mime_type": "image/png", "image_base64": base64.b64encode(png).decode()[:200000]}
            except Exception as exc:
                return {"status": "screenshot_requested", "detail": f"Screenshot requires Tauri desktop app ({exc})"}
        elif name == "create_task":
            return await _create_task(args.get("title", ""), args.get("description", ""), args.get("priority", "medium"), args.get("due_date", ""), user_id)
        elif name == "list_tasks":
            return await _list_tasks(args.get("status", ""), user_id)
        elif name == "set_reminder":
            return await _set_reminder(args.get("title", ""), args.get("message", ""), args.get("remind_at", ""), args.get("recurrence", "none"), user_id)
        elif name == "list_reminders":
            return await _list_reminders(args.get("limit", 10), user_id)
        elif name == "search_knowledge":
            return await _search_knowledge(args.get("query", ""), args.get("limit", 5), user_id)
        elif name == "list_knowledge":
            return await _list_knowledge(user_id)
        elif name == "set_volume":
            return await _set_volume(args.get("action", "set"), args.get("level", 50))
        elif name == "set_brightness":
            return await _set_brightness(args.get("level", 50))
        elif name == "power_control":
            return await _power_control(args.get("action", "lock"), args.get("delay", 0))
        elif name == "network_info":
            return await _network_info(args.get("action", "info"), args.get("host", ""))
        elif name == "get_weather":
            return await _get_weather(args.get("city", ""), args.get("forecast", False))
        elif name == "manage_process":
            return await _manage_process(args.get("action", "list"), args.get("name", ""), args.get("pid", 0))
        elif name == "clipboard":
            return await _clipboard(args.get("action", "get"), args.get("text", ""))
        elif name == "media_control":
            return await _media_control(args.get("action", "play_pause"))
        elif name == "window_control":
            return await _window_control(args.get("action", "minimize_all"))
        elif name == "search_apps":
            return await _search_apps(args.get("query", ""))
        elif name == "calculate":
            return await _calculate(args.get("expression", ""))
        elif name == "get_battery":
            return await _get_battery()
        elif name == "get_disk_usage":
            return await _get_disk_usage()
        elif name == "get_uptime":
            return await _get_uptime()
        elif name == "open_explorer":
            return await _open_explorer(args.get("path", ""))
        elif name == "list_documents":
            return await _list_documents(user_id)
        elif name == "search_documents":
            return await _search_documents(args.get("query", ""), user_id)
        elif name == "list_memories":
            return await _list_memories(user_id)
        elif name == "search_memories":
            return await _search_memories(args.get("query", ""), user_id)
        elif name == "delete_memory":
            return await _delete_memory(args.get("memory_id", ""), user_id)
        elif name == "get_monitor_stats":
            if not is_admin:
                return {"error": "Monitor stats require admin privileges"}
            return await _get_monitor_stats()
        elif name == "list_processes":
            if not is_admin:
                return {"error": "Process listing requires admin privileges"}
            return await _list_processes_agent()
        elif name == "create_alert_rule":
            if not is_admin:
                return {"error": "Alert rules require admin privileges"}
            return await _create_alert_rule(args.get("name", ""), args.get("alert_type", ""), args.get("severity", "warning"), args.get("config", {}))
        elif name == "list_alert_rules":
            if not is_admin:
                return {"error": "Alert rules require admin privileges"}
            return await _list_alert_rules()
        elif name == "list_triggered_alerts":
            if not is_admin:
                return {"error": "Alert rules require admin privileges"}
            return await _list_triggered_alerts(args.get("limit", 20))
        elif name == "create_workspace":
            return await _create_workspace(args.get("name", ""), args.get("icon", "ðŸ“"), user_id)
        elif name == "list_workspaces":
            return await _list_workspaces(user_id)
        elif name == "update_task":
            return await _update_task(args.get("task_id", ""), args.get("title", ""), args.get("description", ""), args.get("priority", ""), args.get("due_date", ""), user_id)
        elif name == "set_task_status":
            return await _set_task_status(args.get("task_id", ""), args.get("status", ""), user_id)
        elif name == "delete_task":
            return await _delete_task(args.get("task_id", ""), user_id)
        elif name == "task_stats":
            return await _task_stats(user_id)
        elif name == "update_reminder":
            return await _update_reminder(args.get("reminder_id", ""), args.get("title", ""), args.get("message", ""), args.get("remind_at", ""), args.get("recurrence", ""), user_id)
        elif name == "delete_reminder":
            return await _delete_reminder(args.get("reminder_id", ""), user_id)
        elif name == "mark_reminder_done":
            return await _mark_reminder_done(args.get("reminder_id", ""), user_id)
        elif name == "list_workflows":
            return await _list_workflows(user_id)
        elif name == "create_workflow":
            return await _create_workflow(args.get("name", ""), args.get("trigger_type", ""), args.get("trigger_config", {}), args.get("actions", []), user_id)
        elif name == "toggle_workflow":
            return await _toggle_workflow(args.get("workflow_id", ""), user_id)
        elif name == "run_workflow":
            return await _run_workflow(args.get("workflow_id", ""), user_id)
        elif name == "world_simulate":
            return await _world_simulate(args.get("changes", []), user_id, db_session)
        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as e:
        log.error("Tool %s failed: %s", name, e)
        return {"error": str(e)}


async def _world_simulate(changes: List[Dict[str, Any]], user_id: str, db_session=None) -> Dict[str, Any]:
    if db_session is None:
        return {"error": "No database session available for simulation"}
    if not changes:
        return {"error": "No changes provided â€” pass at least one change to simulate"}
    try:
        graph = WorldGraph(db_session)
        engine = SituationEngine(graph)
        simulator = WorldSimulator(graph, engine)
        result = simulator.simulate(user_id, changes)
        return result.to_dict()
    except Exception as exc:
        return {"error": f"Simulation failed: {exc}"}


async def _open_app(app_name: str) -> Dict[str, Any]:
    if not app_name:
        return {"error": "No app name provided"}

    system = platform.system().lower()
    try:
        if system == "windows":
            if "\\" in app_name or "/" in app_name:
                proc = await asyncio.create_subprocess_exec(
                    "cmd", "/c", "start", "", app_name,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    "cmd", "/c", "start", app_name,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
        elif system == "darwin":
            proc = await asyncio.create_subprocess_exec(
                "open", "-a", app_name,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                app_name,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        return {"status": "opened", "app": app_name}
    except asyncio.TimeoutError:
        return {"status": "launched", "app": app_name, "note": "Process may still be starting"}
    except FileNotFoundError:
        return {"error": f"App not found: {app_name}"}
    except Exception as e:
        return {"error": str(e)}


async def _run_command(command: str, cwd: str = None, user_id: str = "", db_session=None) -> Dict[str, Any]:
    if not command:
        return {"error": "No command provided"}
    # 1. Prefer running on the user's own computer via their connected desktop app
    if user_id and db_session:
        result = await _route_to_local_device("run_command", {"command": command}, user_id, db_session)
        if result is not None:
            return {**result, "note": "Ran on your computer."}
    # 2. Fall back to this host (works when the backend runs on the user's machine)
    try:
        kwargs = {"stdout": asyncio.subprocess.PIPE, "stderr": asyncio.subprocess.PIPE}
        if cwd:
            kwargs["cwd"] = cwd
        system = platform.system().lower()
        if system == "windows":
            proc = await asyncio.create_subprocess_exec("cmd", "/c", command, **kwargs)
        else:
            proc = await asyncio.create_subprocess_exec("sh", "-c", command, **kwargs)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return {
            "status": "completed",
            "exit_code": proc.returncode,
            "stdout": stdout.decode(errors="replace")[:5000],
            "stderr": stderr.decode(errors="replace")[:2000]
        }
    except asyncio.TimeoutError:
        return {"error": "Command timed out after 30s"}
    except Exception as e:
        return {"error": str(e)}


async def _list_files(path: str, pattern: str = None, user_id: str = "", db_session=None) -> Dict[str, Any]:
    if not path:
        path = str(Path.home())
    # 1. Prefer listing on the user's own computer via their connected desktop app
    if user_id and db_session:
        payload: Dict[str, Any] = {"path": path}
        if pattern:
            payload["pattern"] = pattern
        result = await _route_to_local_device("list_files", payload, user_id, db_session)
        if result is not None and result.get("status") != "queued":
            return result
        if result is not None:
            return {**result, "note": "Waiting for your computer â€” listing queued."}
    # 2. Fall back to this host
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"Path not found: {path}"}
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}
        entries = []
        if pattern:
            items = list(p.glob(pattern))[:50]
        else:
            items = sorted(p.iterdir())[:50]
        for item in items:
            stat = item.stat()
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
        return {"path": str(p), "entries": entries, "count": len(entries)}
    except Exception as e:
        return {"error": str(e)}


async def _read_file(path: str, user_id: str = "", db_session=None) -> Dict[str, Any]:
    if not path:
        return {"error": "No path provided"}
    # 1. Prefer reading on the user's own computer via their connected desktop app
    if user_id and db_session:
        result = await _route_to_local_device("read_file", {"path": path}, user_id, db_session)
        if result is not None and result.get("status") != "queued":
            return result
        if result is not None:
            return {**result, "note": "Waiting for your computer â€” read queued."}
    # 2. Fall back to this host
    try:
        p = Path(path)
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if p.stat().st_size > 1_000_000:
            return {"error": "File too large (>1MB)"}
        content = p.read_text(encoding="utf-8", errors="replace")
        return {"path": str(p), "content": content[:10000], "size": p.stat().st_size}
    except Exception as e:
        return {"error": str(e)}


async def _write_file(path: str, content: str, user_id: str = "", db_session=None) -> Dict[str, Any]:
    if not path:
        return {"error": "No path provided"}
    # 1. Prefer writing on the user's own computer via their connected desktop app
    if user_id and db_session:
        result = await _route_to_local_device("write_file", {"path": path, "content": content}, user_id, db_session)
        if result is not None:
            return {**result, "note": "Written to your computer."}
    # 2. Fall back to the server-side sandbox
    try:
        p = Path(path)
        if not p.is_absolute() and user_id:
            fm = _get_file_manager(user_id)
            p = fm.root / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"status": "written", "path": str(p), "size": len(content)}
    except Exception as e:
        return {"error": str(e)}


async def _open_url(url: str, user_id: str = "", db_session=None, base_url: str = "", jwt_secret: str = "") -> Dict[str, Any]:
    if not url:
        return {"error": "No URL provided"}
    raw = url.strip()
    if raw.startswith("file://"):
        raw = raw[len("file://"):]
    # 1. If it's a local file path that exists in the user's sandbox â†’ serve it over HTTP
    served = None
    if not raw.startswith(("http://", "https://")):
        served = _serve_local_file(raw, user_id, base_url, jwt_secret)
    if served:
        url = served
    elif not raw.startswith(("http://", "https://")):
        url = "https://" + raw
    # 2. Prefer routing through the user's connected device so it opens in THEIR browser
    if user_id and db_session:
        result = await _device_command(None, "open_url", {"url": url}, False, user_id, db_session)
        if result.get("status") in ("queued", "awaiting_approval"):
            return {**result, "url": url, "note": "Opening in your browser on your connected device."}
        # no_device â†’ fall through to local open attempt
    # 3. Try opening on this host (works when the backend runs on the user's own machine)
    try:
        system = platform.system().lower()
        if system == "windows":
            proc = await asyncio.create_subprocess_exec("cmd", "/c", "start", url.replace("&", "^&"),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        elif system == "darwin":
            proc = await asyncio.create_subprocess_exec("open", url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        else:
            proc = await asyncio.create_subprocess_exec("xdg-open", url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(proc.communicate(), timeout=10)
        return {"status": "opened", "url": url}
    except FileNotFoundError:
        return {"status": "no_browser", "url": url, "detail": f"No desktop browser is available on this server. Open this link in your browser: {url}"}
    except Exception as e:
        return {"error": str(e), "url": url}


def _serve_local_file(path: str, user_id: str, base_url: str, jwt_secret: str = "") -> Optional[str]:
    """Resolve a local file path within the user's sandbox and return a signed served URL, or None."""
    if not path or not user_id or not base_url:
        return None
    if not jwt_secret:
        from ..config import Settings
        jwt_secret = Settings().jwt_secret
    fm = _get_file_manager(user_id)
    target = None
    try:
        target = fm._resolve(path)
    except Exception:
        pass
    if target is None or not target.is_file():
        try:
            target = fm.root / Path(path).name
        except Exception:
            target = None
    if target is None or not target.is_file():
        return None
    try:
        rel = target.relative_to(fm.root).as_posix()
    except ValueError:
        return None
    exp = int(time.time()) + 3600
    sig = hmac.new(jwt_secret.encode(), f"{user_id}:{rel}:{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{base_url.rstrip('/')}/api/files/serve?uid={quote(user_id)}&path={quote(rel)}&exp={exp}&sig={sig}"


async def _send_notification(title: str, body: str, device_id: str, user_id: str, db_session=None) -> Dict[str, Any]:
    if not title or not body:
        return {"error": "Title and body are required"}
    if not db_session:
        return {"error": "No database session available"}
    from ..models import Device, Command
    from sqlalchemy import select
    query = select(Device).where(Device.user_id == user_id)
    if device_id:
        query = query.where(Device.id == device_id)
    devices = list(db_session.scalars(query))
    if not devices:
        return {"status": "no_devices", "detail": "No connected devices found to send notification to"}
    created = []
    for device in devices:
        cmd = Command(
            user_id=user_id, device_id=device.id, kind="notification",
            payload_json=json.dumps({"title": title, "body": body}),
            requires_confirmation=False, status="queued",
        )
        db_session.add(cmd)
        created.append(device.name)
    db_session.commit()
    return {"status": "queued", "devices": created, "title": title, "body": body}


CONFIRMATION_KINDS = {"reveal_path"}


async def _route_to_local_device(kind: str, payload: dict, user_id: str, db_session=None, wait_seconds: int = 25) -> Optional[Dict[str, Any]]:
    """Try to execute a file/shell operation on the user's own computer via their
    connected desktop app. Returns the device result dict, or None when no device
    is available (caller should fall back to server-side execution)."""
    if not db_session:
        return None
    from ..models import Device
    from sqlalchemy import select
    device = db_session.scalar(select(Device).where(Device.user_id == user_id))
    if device is None:
        return None
    result = await _device_command(None, kind, payload, False, user_id, db_session)
    status_value = result.get("status")
    if status_value not in ("queued", "awaiting_approval"):
        return None
    command_id = result.get("command_id")
    if not command_id:
        return {**result, "note": "Queued on your computer."}
    # Poll for the desktop app to pick up and complete the command.
    from ..models import Command
    import time as _time
    deadline = _time.monotonic() + wait_seconds
    while _time.monotonic() < deadline:
        await asyncio.sleep(1)
        db_session.expire_all()
        cmd = db_session.get(Command, command_id)
        if cmd is None:
            return None
        if cmd.status == "completed":
            try:
                payload_result = json.loads(cmd.result_json) if cmd.result_json else {}
            except Exception:
                payload_result = {}
            inner = payload_result.get("result") or payload_result
            return {"status": "completed_on_device", "device": result.get("device"), **(inner if isinstance(inner, dict) else {})}
        if cmd.status == "failed":
            return {"error": "Your computer reported a failure running this command.", "detail": cmd.result_json}
    return {"status": "queued", "device": result.get("device"), "command_id": command_id,
            "note": "Sent to your computer â€” it will run when your SALAR desktop app is online."}


async def _device_command(device_id: str, kind: str, payload: dict, requires_confirmation: bool, user_id: str, db_session=None) -> Dict[str, Any]:
    if not kind:
        return {"error": "Command kind is required"}
    if not db_session:
        return {"error": "No database session available"}
    from ..models import Device, Command
    from sqlalchemy import select
    if device_id:
        device = db_session.scalar(select(Device).where(Device.id == device_id, Device.user_id == user_id))
    else:
        device = db_session.scalar(select(Device).where(Device.user_id == user_id).order_by(Device.last_seen_at.desc().nullslast()))
    if device is None:
        return {"status": "no_device", "detail": "No connected device found"}
    needs_confirm = requires_confirmation or kind in CONFIRMATION_KINDS
    cmd = Command(
        user_id=user_id, device_id=device.id, kind=kind,
        payload_json=json.dumps(payload),
        requires_confirmation=needs_confirm,
        status="awaiting_confirmation" if needs_confirm else "queued",
    )
    db_session.add(cmd)
    db_session.commit()
    return {
        "status": "awaiting_approval" if needs_confirm else "queued",
        "device": device.name, "device_id": device.id,
        "kind": kind, "command_id": cmd.id,
    }


async def _list_devices(user_id: str, db_session=None) -> Dict[str, Any]:
    if not db_session:
        return {"error": "No database session available"}
    from ..models import Device
    from sqlalchemy import select
    devices = list(db_session.scalars(select(Device).where(Device.user_id == user_id).order_by(Device.created_at.desc())))
    if not devices:
        return {"devices": [], "count": 0, "detail": "No devices registered"}
    return {
        "devices": [{"id": d.id, "name": d.name, "platform": d.platform, "last_seen": str(d.last_seen_at) if d.last_seen_at else "never"} for d in devices],
        "count": len(devices),
    }


async def _save_memory(title: str, content: str, user_id: str, db_session=None) -> Dict[str, Any]:
    if not title or not content:
        return {"error": "Title and content are required"}
    if db_session:
        from ..models import Memory
        memory = Memory(user_id=user_id, title=title, content=content, layer="long_term")
        db_session.add(memory)
        db_session.commit()
        return {"status": "saved", "title": title}
    return {"status": "memory_prepared", "title": title, "detail": "No DB session available"}


async def _get_system_info() -> Dict[str, Any]:
    import platform as pf
    info = {
        "os": pf.system(),
        "os_version": pf.version(),
        "hostname": pf.node(),
        "python": pf.python_version(),
        "machine": pf.machine(),
        "processor": pf.processor() or "unknown",
    }
    try:
        import shutil
        total, used, free = shutil.disk_usage("C:\\" if pf.system() == "Windows" else "/")
        info["disk"] = {"total_gb": round(total / (1024**3), 1), "used_gb": round(used / (1024**3), 1), "free_gb": round(free / (1024**3), 1)}
    except Exception:
        pass
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["memory"] = {"total_gb": round(mem.total / (1024**3), 1), "used_percent": mem.percent}
        info["cpu_percent"] = psutil.cpu_percent(interval=1)
    except ImportError:
        pass
    return info


async def _get_whatsapp_client():
    from .whatsapp import WhatsAppClient
    return WhatsAppClient()


async def _whatsapp_send(to: str, phone: str, text: str, user_id: str, db_session=None) -> Dict[str, Any]:
    if not text:
        return {"error": "Message text is required"}
    client = await _get_whatsapp_client()
    try:
        result = await client.send_message(to=to, phone=phone, text=text, user_id=user_id)
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        await client.close()


async def _whatsapp_read(jid: str, limit: int, user_id: str) -> Dict[str, Any]:
    if not jid:
        return {"error": "Chat JID is required"}
    client = await _get_whatsapp_client()
    try:
        messages = await client.get_messages(jid, limit=limit, user_id=user_id)
        return {"jid": jid, "messages": messages, "count": len(messages)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        await client.close()


async def _whatsapp_list_chats(user_id: str) -> Dict[str, Any]:
    client = await _get_whatsapp_client()
    try:
        chats = await client.get_chats(user_id)
        return {"chats": chats, "count": len(chats)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        await client.close()


async def _whatsapp_search(query: str, user_id: str) -> Dict[str, Any]:
    if not query:
        return {"error": "Search query is required"}
    client = await _get_whatsapp_client()
    try:
        chats = await client.get_chats(user_id)
        results = []
        query_lower = query.lower()
        for chat in chats:
            if query_lower in (chat.get("lastMessage") or "").lower():
                results.append(chat)
        if not results:
            for chat in chats:
                messages = await client.get_messages(chat["jid"], limit=20, user_id=user_id)
                for msg in messages:
                    if query_lower in (msg.get("text") or "").lower():
                        results.append({"chat": chat["jid"], "sender": msg.get("senderName", ""), "text": msg["text"]})
                        break
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        await client.close()


async def _whatsapp_qr(user_id: str) -> Dict[str, Any]:
    client = await _get_whatsapp_client()
    try:
        info = await client.get_qr(user_id)
        return info
    except Exception as e:
        return {"error": str(e)}
    finally:
        await client.close()


def _get_email_client(user_id: str):
    from .state import email_accounts
    cfg = email_accounts.get(user_id)
    if not cfg:
        return None
    from .email_client import EmailAccount
    return EmailAccount(**cfg)


async def _email_search(folder: str, query: str, limit: int, user_id: str) -> Dict[str, Any]:
    client = _get_email_client(user_id)
    if not client:
        return {"error": "No email account configured. Add one in Settings."}
    try:
        loop = asyncio.get_event_loop()
        emails = await loop.run_in_executor(None, lambda: client.search_emails(folder=folder, query=query, limit=limit))
        return {"emails": emails, "count": len(emails), "folder": folder}
    except Exception as e:
        return {"error": str(e)}


async def _email_read(msg_id: str, folder: str, user_id: str) -> Dict[str, Any]:
    if not msg_id:
        return {"error": "Message ID is required"}
    client = _get_email_client(user_id)
    if not client:
        return {"error": "No email account configured. Add one in Settings."}
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: client.read_email(msg_id=msg_id, folder=folder))
    except Exception as e:
        return {"error": str(e)}


async def _email_send(to: str, subject: str, body: str, cc: str, user_id: str) -> Dict[str, Any]:
    if not to or not subject or not body:
        return {"error": "To, subject, and body are required"}
    client = _get_email_client(user_id)
    if not client:
        return {"error": "No email account configured. Add one in Settings."}
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: client.send_email(to=to, subject=subject, body=body, cc=cc))
    except Exception as e:
        return {"error": str(e)}


async def _email_folders(user_id: str) -> Dict[str, Any]:
    client = _get_email_client(user_id)
    if not client:
        return {"error": "No email account configured. Add one in Settings."}
    try:
        loop = asyncio.get_event_loop()
        folders = await loop.run_in_executor(None, client.get_folders_with_counts)
        return {"folders": folders, "count": len(folders)}
    except Exception as e:
        return {"error": str(e)}


async def _email_unread(folder: str, user_id: str) -> Dict[str, Any]:
    client = _get_email_client(user_id)
    if not client:
        return {"error": "No email account configured. Add one in Settings."}
    try:
        loop = asyncio.get_event_loop()
        count = await loop.run_in_executor(None, lambda: client.get_unread_count(folder))
        return {"folder": folder, "unread": count}
    except Exception as e:
        return {"error": str(e)}


def _get_calendar_manager(user_id: str):
    from ..api.calendar import _calendar_managers
    if user_id not in _calendar_managers:
        from .calendar_client import CalendarManager
        _calendar_managers[user_id] = CalendarManager()
    return _calendar_managers[user_id]


async def _calendar_events(days_before: int, days_after: int, user_id: str) -> Dict[str, Any]:
    mgr = _get_calendar_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        events = await loop.run_in_executor(None, lambda: mgr.get_all_events(days_before=days_before, days_after=days_after))
        return {"events": events, "count": len(events)}
    except Exception as e:
        return {"error": str(e)}


async def _calendar_today(user_id: str) -> Dict[str, Any]:
    mgr = _get_calendar_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        events = await loop.run_in_executor(None, mgr.get_today_events)
        return {"events": events, "count": len(events)}
    except Exception as e:
        return {"error": str(e)}


async def _calendar_upcoming(limit: int, user_id: str) -> Dict[str, Any]:
    mgr = _get_calendar_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        events = await loop.run_in_executor(None, lambda: mgr.get_upcoming(limit))
        return {"events": events, "count": len(events)}
    except Exception as e:
        return {"error": str(e)}


async def _calendar_search(query: str, user_id: str) -> Dict[str, Any]:
    if not query:
        return {"error": "Search query is required"}
    mgr = _get_calendar_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        events = await loop.run_in_executor(None, lambda: mgr.search(query))
        return {"events": events, "count": len(events)}
    except Exception as e:
        return {"error": str(e)}


async def _calendar_add_feed(name: str, url: str, color: str, user_id: str) -> Dict[str, Any]:
    if not name or not url:
        return {"error": "Name and URL are required"}
    mgr = _get_calendar_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: mgr.add_feed(name, url, color))
    except Exception as e:
        return {"error": str(e)}


def _get_browser():
    from .browser import WebBrowser
    return WebBrowser()


async def _browse_page(url: str) -> Dict[str, Any]:
    if not url:
        return {"error": "URL is required"}
    browser = _get_browser()
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: browser.fetch_page(url))
        # Truncate text for agent consumption
        if "text" in result and len(result["text"]) > 5000:
            result["text"] = result["text"][:5000] + "\n\n[Truncated...]"
        return result
    except Exception as e:
        return {"error": str(e)}


async def _read_article(url: str) -> Dict[str, Any]:
    if not url:
        return {"error": "URL is required"}
    browser = _get_browser()
    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, lambda: browser.read_article(url))
        return {"url": url, "content": text[:8000]}
    except Exception as e:
        return {"error": str(e)}


async def _browse_links(url: str) -> Dict[str, Any]:
    if not url:
        return {"error": "URL is required"}
    browser = _get_browser()
    try:
        loop = asyncio.get_event_loop()
        links = await loop.run_in_executor(None, lambda: browser.extract_links(url))
        return {"url": url, "links": links[:50], "count": len(links)}
    except Exception as e:
        return {"error": str(e)}


def _get_file_manager(user_id: str):
    from .file_manager import DEFAULT_ROOT, FileManager
    root = (DEFAULT_ROOT / user_id) if DEFAULT_ROOT else None
    return FileManager(root=str(root) if root else None)


async def _file_list(path: str, user_id: str) -> Dict[str, Any]:
    fm = _get_file_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fm.list_dir(path))
    except Exception as e:
        return {"error": str(e)}


async def _file_read(path: str, user_id: str) -> Dict[str, Any]:
    if not path:
        return {"error": "Path is required"}
    fm = _get_file_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: fm.read_file(path))
        if "content" in result and len(result["content"]) > 8000:
            result["content"] = result["content"][:8000] + "\n\n[Truncated...]"
        return result
    except Exception as e:
        return {"error": str(e)}


async def _file_write(path: str, content: str, user_id: str) -> Dict[str, Any]:
    if not path:
        return {"error": "Path is required"}
    fm = _get_file_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fm.write_file(path, content))
    except Exception as e:
        return {"error": str(e)}


async def _file_search(query: str, path: str, user_id: str) -> Dict[str, Any]:
    if not query:
        return {"error": "Search query is required"}
    fm = _get_file_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, lambda: fm.search(query, path))
        return {"results": results[:30], "count": len(results)}
    except Exception as e:
        return {"error": str(e)}


async def _file_info(path: str, user_id: str) -> Dict[str, Any]:
    if not path:
        return {"error": "Path is required"}
    fm = _get_file_manager(user_id)
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fm.file_info(path))
    except Exception as e:
        return {"error": str(e)}


async def _code_run(code: str, language: str, user_id: str) -> Dict[str, Any]:
    if not code:
        return {"error": "Code is required"}
    from .code_interpreter import CodeInterpreter
    from .file_manager import DEFAULT_ROOT
    workspace = (DEFAULT_ROOT / user_id / "sandbox") if DEFAULT_ROOT else None
    interp = CodeInterpreter(workspace=str(workspace) if workspace else None)
    return await interp.execute(code, language)


async def _create_task(title: str, description: str, priority: str, due_date: str, user_id: str) -> Dict[str, Any]:
    if not title:
        return {"error": "Title is required"}
    from ..database import get_db
    from ..models import Task
    from datetime import datetime, timezone
    import secrets
    task_id = secrets.token_urlsafe(16)[:16]
    due = None
    if due_date:
        try:
            due = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass
    try:
        session = get_db.__wrapped__.__defaults__[0] if hasattr(get_db, '__wrapped__') else None
    except:
        session = None
    return {"task_id": task_id, "title": title, "priority": priority, "status": "todo", "message": "Task created. Use the Tasks tab to manage it."}


async def _list_tasks(status: str, user_id: str) -> Dict[str, Any]:
    return {"message": f"Listing tasks{' with status=' + status if status else ''}. Check the Tasks tab for full details.", "hint": "Use the Tasks dashboard to view and manage tasks."}


async def _set_reminder(title: str, message: str, remind_at: str, recurrence: str, user_id: str) -> Dict[str, Any]:
    if not title or not remind_at:
        return {"error": "Title and remind_at are required"}
    return {"title": title, "remind_at": remind_at, "recurrence": recurrence, "message": "Reminder set. SALAR will notify you at the scheduled time."}


async def _list_reminders(limit: int, user_id: str) -> Dict[str, Any]:
    return {"message": f"Listing up to {limit} reminders. Check the Reminders tab for full details."}


async def _search_knowledge(query: str, limit: int, user_id: str) -> Dict[str, Any]:
    if not query:
        return {"error": "Query is required"}
    from ..models import KnowledgeChunk, KnowledgeDocument
    try:
        db = next(get_db_session(user_id))
        words = query.lower().split()
        conditions = [KnowledgeChunk.content.ilike(f"%{w}%") for w in words if len(w) > 2]
        if not conditions:
            return {"results": [], "message": "No searchable terms in query"}
        q = db.query(KnowledgeChunk).join(KnowledgeDocument).filter(
            KnowledgeChunk.user_id == user_id,
            *conditions
        ).limit(limit).all()
        results = []
        for chunk in q:
            doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == chunk.document_id).first()
            results.append({
                "content": chunk.content[:500],
                "document": doc.filename if doc else "unknown",
                "chunk_index": chunk.chunk_index,
            })
        return {"results": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}


async def _list_knowledge(user_id: str) -> Dict[str, Any]:
    from ..models import KnowledgeDocument
    try:
        db = next(get_db_session(user_id))
        docs = db.query(KnowledgeDocument).filter(KnowledgeDocument.user_id == user_id).all()
        return {"documents": [{"id": d.id, "filename": d.filename, "chunk_count": d.chunk_count} for d in docs], "count": len(docs)}
    except Exception as e:
        return {"error": str(e)}


def get_db_session(user_id: str):
    """Get a DB session generator for agent tool use."""
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_url = os.environ.get("SALAR_DATABASE_URL", "sqlite:///./data/salar.db")
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _get_sc():
    from .system_control import SystemControl
    return SystemControl()

async def _set_volume(action: str, level: int) -> Dict[str, Any]:
    sc = _get_sc()
    if action == "up":
        return await sc.volume_up()
    elif action == "down":
        return await sc.volume_down()
    elif action == "mute":
        return await sc.toggle_mute()
    else:
        return await sc.set_volume(level)

async def _set_brightness(level: int) -> Dict[str, Any]:
    return await _get_sc().set_brightness(level)

async def _power_control(action: str, delay: int) -> Dict[str, Any]:
    sc = _get_sc()
    if action == "lock": return await sc.lock_screen()
    elif action == "sleep": return await sc.sleep_pc()
    elif action == "hibernate": return await sc.hibernate_pc()
    elif action == "shutdown": return await sc.shutdown_pc(delay)
    elif action == "restart": return await sc.restart_pc(delay)
    elif action == "cancel_shutdown": return await sc.cancel_shutdown()
    return {"error": f"Unknown power action: {action}"}

async def _network_info(action: str, host: str) -> Dict[str, Any]:
    sc = _get_sc()
    if action == "ping":
        if not host: return {"error": "Host is required for ping"}
        return await sc.ping(host)
    elif action == "wifi":
        return await sc.get_wifi_info()
    elif action == "toggle_wifi":
        return await sc.toggle_wifi()
    return await sc.get_network_info()

async def _get_weather(city: str, forecast: bool) -> Dict[str, Any]:
    sc = _get_sc()
    if forecast:
        return await sc.get_forecast(city)
    return await sc.get_weather(city)

async def _manage_process(action: str, name: str, pid: int) -> Dict[str, Any]:
    sc = _get_sc()
    if action == "kill":
        return await sc.kill_process(name, pid)
    return await sc.list_processes()

async def _clipboard(action: str, text: str) -> Dict[str, Any]:
    sc = _get_sc()
    if action == "set":
        return await sc.set_clipboard(text)
    return await sc.get_clipboard()

async def _media_control(action: str) -> Dict[str, Any]:
    sc = _get_sc()
    if action == "next": return await sc.media_next()
    elif action == "previous": return await sc.media_previous()
    return await sc.media_play_pause()

async def _window_control(action: str) -> Dict[str, Any]:
    sc = _get_sc()
    if action == "get_active": return await sc.get_active_window()
    return await sc.minimize_windows()

async def _search_apps(query: str) -> Dict[str, Any]:
    return await _get_sc().search_apps(query)

async def _calculate(expression: str) -> Dict[str, Any]:
    return await _get_sc().calculate(expression)

async def _get_battery() -> Dict[str, Any]:
    return await _get_sc().get_battery()

async def _get_disk_usage() -> Dict[str, Any]:
    return await _get_sc().get_disk_usage()

async def _get_uptime() -> Dict[str, Any]:
    return await _get_sc().get_uptime()

async def _open_explorer(path: str) -> Dict[str, Any]:
    return await _get_sc().open_explorer(path)


async def _list_documents(user_id: str) -> Dict[str, Any]:
    from ..models import Document
    try:
        db = next(get_db_session(user_id))
        docs = db.query(Document).filter(Document.user_id == user_id).all()
        return {"documents": [{"id": d.id, "filename": d.filename, "content_type": d.content_type, "size": d.size} for d in docs], "count": len(docs)}
    except Exception as e:
        return {"error": str(e)}


async def _search_documents(query: str, user_id: str) -> Dict[str, Any]:
    if not query:
        return {"error": "Query is required"}
    from ..models import Document
    try:
        db = next(get_db_session(user_id))
        docs = db.query(Document).filter(
            Document.user_id == user_id,
            Document.filename.ilike(f"%{query}%")
        ).limit(20).all()
        return {"documents": [{"id": d.id, "filename": d.filename, "content_type": d.content_type} for d in docs], "count": len(docs)}
    except Exception as e:
        return {"error": str(e)}


async def _list_memories(user_id: str) -> Dict[str, Any]:
    from ..models import Memory
    try:
        db = next(get_db_session(user_id))
        memories = db.query(Memory).filter(Memory.user_id == user_id).order_by(Memory.created_at.desc()).limit(50).all()
        return {"memories": [{"id": m.id, "title": m.title, "content": m.content[:200], "layer": m.layer, "created_at": str(m.created_at)} for m in memories], "count": len(memories)}
    except Exception as e:
        return {"error": str(e)}


async def _search_memories(query: str, user_id: str) -> Dict[str, Any]:
    if not query:
        return {"error": "Query is required"}
    from ..models import Memory
    try:
        db = next(get_db_session(user_id))
        memories = db.query(Memory).filter(
            Memory.user_id == user_id,
            (Memory.title.ilike(f"%{query}%") | Memory.content.ilike(f"%{query}%"))
        ).limit(20).all()
        return {"memories": [{"id": m.id, "title": m.title, "content": m.content[:300], "layer": m.layer} for m in memories], "count": len(memories)}
    except Exception as e:
        return {"error": str(e)}


async def _delete_memory(memory_id: str, user_id: str) -> Dict[str, Any]:
    if not memory_id:
        return {"error": "Memory ID is required"}
    from ..models import Memory
    try:
        db = next(get_db_session(user_id))
        m = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id).first()
        if not m:
            return {"error": "Memory not found"}
        db.delete(m)
        db.commit()
        return {"status": "deleted", "id": memory_id}
    except Exception as e:
        return {"error": str(e)}


async def _get_monitor_stats() -> Dict[str, Any]:
    from .monitor import get_snapshot
    return get_snapshot()


async def _list_processes_agent() -> Dict[str, Any]:
    from .monitor import get_processes
    return get_processes()


async def _create_alert_rule(name: str, alert_type: str, severity: str, config: dict) -> Dict[str, Any]:
    if not name or not alert_type:
        return {"error": "Name and alert_type are required"}
    try:
        from ..api.alerts import get_engine
        engine = get_engine()
        return engine.add_rule(name, alert_type, config, severity)
    except Exception as e:
        return {"error": str(e)}


async def _list_alert_rules() -> Dict[str, Any]:
    try:
        from ..api.alerts import get_engine
        return {"rules": get_engine().list_rules()}
    except Exception as e:
        return {"error": str(e)}


async def _list_triggered_alerts(limit: int) -> Dict[str, Any]:
    try:
        from ..api.alerts import get_engine
        return {"alerts": get_engine().list_triggered(limit=limit)}
    except Exception as e:
        return {"error": str(e)}


async def _create_workspace(name: str, icon: str, user_id: str) -> Dict[str, Any]:
    if not name:
        return {"error": "Name is required"}
    from ..models import Workspace
    import secrets
    try:
        db = next(get_db_session(user_id))
        ws = Workspace(id=secrets.token_urlsafe(16)[:16], user_id=user_id, name=name, icon=icon, color="#5227FF", is_default=False)
        db.add(ws)
        db.commit()
        return {"id": ws.id, "name": ws.name, "icon": ws.icon, "message": f"Workspace '{name}' created"}
    except Exception as e:
        return {"error": str(e)}


async def _list_workspaces(user_id: str) -> Dict[str, Any]:
    from ..models import Workspace
    try:
        db = next(get_db_session(user_id))
        wss = db.query(Workspace).filter(Workspace.user_id == user_id).all()
        return {"workspaces": [{"id": w.id, "name": w.name, "icon": w.icon, "is_default": w.is_default} for w in wss], "count": len(wss)}
    except Exception as e:
        return {"error": str(e)}


async def _update_task(task_id: str, title: str, description: str, priority: str, due_date: str, user_id: str) -> Dict[str, Any]:
    if not task_id:
        return {"error": "Task ID is required"}
    from ..models import Task
    from datetime import datetime
    try:
        db = next(get_db_session(user_id))
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            return {"error": "Task not found"}
        if title: task.title = title
        if description: task.description = description
        if priority: task.priority = priority
        if due_date:
            try: task.due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except: pass
        db.commit()
        return {"status": "updated", "id": task_id, "title": task.title}
    except Exception as e:
        return {"error": str(e)}


async def _set_task_status(task_id: str, status: str, user_id: str) -> Dict[str, Any]:
    if not task_id or not status:
        return {"error": "Task ID and status are required"}
    from ..models import Task
    try:
        db = next(get_db_session(user_id))
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            return {"error": "Task not found"}
        task.status = status
        db.commit()
        return {"status": "updated", "id": task_id, "new_status": status}
    except Exception as e:
        return {"error": str(e)}


async def _delete_task(task_id: str, user_id: str) -> Dict[str, Any]:
    if not task_id:
        return {"error": "Task ID is required"}
    from ..models import Task
    try:
        db = next(get_db_session(user_id))
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            return {"error": "Task not found"}
        db.delete(task)
        db.commit()
        return {"status": "deleted", "id": task_id}
    except Exception as e:
        return {"error": str(e)}


async def _task_stats(user_id: str) -> Dict[str, Any]:
    from ..models import Task
    from sqlalchemy import func
    try:
        db = next(get_db_session(user_id))
        by_status = dict(db.query(Task.status, func.count()).filter(Task.user_id == user_id).group_by(Task.status).all())
        by_priority = dict(db.query(Task.priority, func.count()).filter(Task.user_id == user_id).group_by(Task.priority).all())
        return {"by_status": by_status, "by_priority": by_priority, "total": sum(by_status.values())}
    except Exception as e:
        return {"error": str(e)}


async def _update_reminder(reminder_id: str, title: str, message: str, remind_at: str, recurrence: str, user_id: str) -> Dict[str, Any]:
    if not reminder_id:
        return {"error": "Reminder ID is required"}
    from ..models import Reminder
    from datetime import datetime
    try:
        db = next(get_db_session(user_id))
        r = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user_id).first()
        if not r:
            return {"error": "Reminder not found"}
        if title: r.title = title
        if message: r.message = message
        if remind_at:
            try: r.remind_at = datetime.fromisoformat(remind_at.replace('Z', '+00:00'))
            except: pass
        if recurrence: r.recurrence = recurrence
        db.commit()
        return {"status": "updated", "id": reminder_id, "title": r.title}
    except Exception as e:
        return {"error": str(e)}


async def _delete_reminder(reminder_id: str, user_id: str) -> Dict[str, Any]:
    if not reminder_id:
        return {"error": "Reminder ID is required"}
    from ..models import Reminder
    try:
        db = next(get_db_session(user_id))
        r = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user_id).first()
        if not r:
            return {"error": "Reminder not found"}
        db.delete(r)
        db.commit()
        return {"status": "deleted", "id": reminder_id}
    except Exception as e:
        return {"error": str(e)}


async def _mark_reminder_done(reminder_id: str, user_id: str) -> Dict[str, Any]:
    if not reminder_id:
        return {"error": "Reminder ID is required"}
    from ..models import Reminder
    try:
        db = next(get_db_session(user_id))
        r = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user_id).first()
        if not r:
            return {"error": "Reminder not found"}
        r.is_done = True
        r.notified = True
        db.commit()
        return {"status": "done", "id": reminder_id, "title": r.title}
    except Exception as e:
        return {"error": str(e)}


async def _list_workflows(user_id: str) -> Dict[str, Any]:
    from ..models import Workflow
    try:
        db = next(get_db_session(user_id))
        wfs = db.query(Workflow).filter(Workflow.user_id == user_id).all()
        return {"workflows": [{"id": w.id, "name": w.name, "trigger_type": w.trigger_type, "enabled": w.enabled} for w in wfs], "count": len(wfs)}
    except Exception as e:
        return {"error": str(e)}


async def _create_workflow(name: str, trigger_type: str, trigger_config: dict, actions: list, user_id: str) -> Dict[str, Any]:
    if not name or not trigger_type:
        return {"error": "Name and trigger_type are required"}
    from ..models import Workflow
    import secrets, json
    try:
        db = next(get_db_session(user_id))
        wf = Workflow(
            id=secrets.token_urlsafe(16)[:16], user_id=user_id, name=name,
            trigger_type=trigger_type, trigger_config=json.dumps(trigger_config),
            actions=json.dumps(actions), enabled=True
        )
        db.add(wf)
        db.commit()
        return {"id": wf.id, "name": wf.name, "trigger_type": wf.trigger_type, "message": f"Workflow '{name}' created"}
    except Exception as e:
        return {"error": str(e)}


async def _toggle_workflow(workflow_id: str, user_id: str) -> Dict[str, Any]:
    if not workflow_id:
        return {"error": "Workflow ID is required"}
    from ..models import Workflow
    try:
        db = next(get_db_session(user_id))
        wf = db.query(Workflow).filter(Workflow.id == workflow_id, Workflow.user_id == user_id).first()
        if not wf:
            return {"error": "Workflow not found"}
        wf.enabled = not wf.enabled
        db.commit()
        return {"status": "updated", "id": workflow_id, "enabled": wf.enabled}
    except Exception as e:
        return {"error": str(e)}


async def _run_workflow(workflow_id: str, user_id: str) -> Dict[str, Any]:
    if not workflow_id:
        return {"error": "Workflow ID is required"}
    from ..models import Workflow, WorkflowRun
    import secrets, json
    try:
        db = next(get_db_session(user_id))
        wf = db.query(Workflow).filter(Workflow.id == workflow_id, Workflow.user_id == user_id).first()
        if not wf:
            return {"error": "Workflow not found"}
        run = WorkflowRun(id=secrets.token_urlsafe(16)[:16], workflow_id=workflow_id, user_id=user_id, status="completed", result="Manually triggered")
        db.add(run)
        db.commit()
        return {"status": "triggered", "workflow": wf.name, "run_id": run.id}
    except Exception as e:
        return {"error": str(e)}
