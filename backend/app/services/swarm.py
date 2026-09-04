# backend/app/services/swarm.py
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from ..models import AgentRun, AgentRunStep, token_id, utcnow

log = logging.getLogger(__name__)

AGENT_SPECS: Dict[str, Dict[str, Any]] = {
    "Researcher": {
        "description": "Finds and cross-checks information from the web and private knowledge.",
        "tools": ["browse_page", "browse_links", "read_article", "search_knowledge", "search_documents"],
        "signals": ["research", "find", "investigate", "compare", "sources", "look up", "search", "explain"],
    },
    "Architect": {
        "description": "Designs system architectures, schemas, blueprints, and API contracts.",
        "tools": ["file_read", "file_write", "search_documents", "search_knowledge"],
        "signals": ["architecture", "design", "schema", "blueprint", "structure", "database", "api design"],
    },
    "Coder": {
        "description": "Writes, fixes, refactors, and executes code in sandboxed runners.",
        "tools": ["run_command", "code_run", "file_read", "file_write", "list_files", "read_file", "write_file", "file_search"],
        "signals": ["code", "program", "build", "fix", "debug", "refactor", "script", "python", "function"],
    },
    "Browser": {
        "description": "Navigates, extracts content, and interacts with web pages.",
        "tools": ["browse_page", "browse_links", "read_article", "open_url"],
        "signals": ["browser", "website", "web page", "url", "download page", "form"],
    },
    "File Manager": {
        "description": "Organizes, renames, categorizes, and indexes document files.",
        "tools": ["list_files", "file_list", "file_info", "file_read", "file_write", "file_search", "read_file", "write_file"],
        "signals": ["file", "folder", "organize", "downloads", "document", "backup", "sort"],
    },
    "Vision": {
        "description": "Analyzes screenshots, UI designs, and visual artifacts.",
        "tools": ["screenshot", "analyze_image"],
        "signals": ["screenshot", "image", "screen", "vision", "look at", "ui", "visual"],
    },
    "Email": {
        "description": "Reads, triages, drafts, and sends email messages.",
        "tools": ["email_read", "email_search", "email_unread", "email_send", "email_folders"],
        "signals": ["email", "inbox", "mail", "reply", "unread"],
    },
    "Calendar": {
        "description": "Manages schedules, appointments, tasks, and reminders.",
        "tools": ["calendar_today", "calendar_upcoming", "calendar_search", "calendar_events", "create_task", "update_task", "list_tasks", "set_reminder", "list_reminders"],
        "signals": ["calendar", "schedule", "meeting", "appointment", "task", "reminder", "deadline"],
    },
    "System": {
        "description": "Monitors and reports CPU, memory, process health, and device stats.",
        "tools": ["get_system_info", "get_monitor_stats", "get_uptime", "network_info", "list_processes", "get_disk_usage"],
        "signals": ["system", "cpu", "memory", "storage", "process", "status", "health", "uptime"],
    },
    "Analyst": {
        "description": "Aggregates data, computes metrics, and generates analytical reports.",
        "tools": ["search_knowledge", "file_read", "read_file"],
        "signals": ["analyze", "metrics", "trend", "chart", "statistic", "summary", "report", "data"],
    },
    "Security": {
        "description": "Audits permissions, credentials, security postures, and access rules.",
        "tools": ["privacy_scan", "guardian_activity", "file_read"],
        "signals": ["security", "audit", "permission", "auth", "vulnerability", "token", "policy", "privacy"],
    },
    "Communicator": {
        "description": "Coordinates multi-channel messaging via WhatsApp and email.",
        "tools": ["whatsapp_send", "email_send", "send_notification"],
        "signals": ["message", "whatsapp", "outreach", "broadcast", "notify", "send message"],
    },
}

DEFAULT_AGENTS = ["Researcher", "System"]


class SwarmBlackboard:
    """Shared memory buffer for agent swarm collaboration."""
    def __init__(self) -> None:
        self.findings: Dict[str, Any] = {}

    def publish(self, agent_name: str, finding: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.findings[agent_name] = {
            "finding": finding,
            "data": data or {},
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

    def summary(self) -> Dict[str, Any]:
        return dict(self.findings)


class AgentSwarm:
    def __init__(self, db, coordinator=None, user_id: str = "", is_admin: bool = False,
                 base_url: str = "", jwt_secret: str = "", db_session=None,
                 max_tool_rounds: int = 2) -> None:
        self.db = db
        self.coordinator = coordinator
        user_id = user_id or getattr(coordinator, "user_id", "") if coordinator else user_id
        self.user_id = user_id
        self.is_admin = is_admin
        self.base_url = base_url
        self.jwt_secret = jwt_secret
        self.db_session = db_session if db_session is not None else db
        self.max_tool_rounds = max_tool_rounds

    def decompose(self, goal: str) -> List[Dict[str, Any]]:
        """Choose specialized agents for a goal based on signals."""
        lowered = goal.lower()
        chosen: List[Dict[str, Any]] = []
        for name, spec in AGENT_SPECS.items():
            if any(sig in lowered for sig in spec["signals"]):
                chosen.append({"name": name, "description": spec["description"], "tools": spec["tools"]})
        for name in DEFAULT_AGENTS:
            if not any(a["name"] == name for a in chosen):
                spec = AGENT_SPECS[name]
                chosen.append({"name": name, "description": spec["description"], "tools": spec["tools"]})
        return chosen

    def create_run(self, user_id: str, goal: str, agents: List[Dict[str, Any]]) -> AgentRun:
        run = AgentRun(
            id=token_id(), user_id=user_id, kind="swarm",
            status="running",
            input_json=json.dumps({"goal": goal, "agents": [a["name"] for a in agents]}),
            created_at=utcnow(), updated_at=utcnow(),
        )
        self.db.add(run)
        self.db.flush()
        for i, agent in enumerate(agents, 1):
            self.db.add(AgentRunStep(
                id=token_id(), run_id=run.id, sequence=i,
                name=agent["name"], status="pending",
                detail_json=json.dumps({"description": agent["description"], "tools": agent["tools"]}),
                created_at=utcnow(),
            ))
        return run

    def _sub_tool_declarations(self, tools: List[str]) -> List[Dict[str, Any]]:
        """Slice the global TOOL_DEFINITIONS down to just this agent's allowed tools."""
        try:
            from .agent import TOOL_DEFINITIONS
        except Exception as e:
            log.warning("Could not import TOOL_DEFINITIONS: %s", e)
            return []
        allowed = set(tools)
        declarations = []
        for wrapper in TOOL_DEFINITIONS:
            for decl in wrapper.get("function_declarations", []):
                if decl.get("name") in allowed:
                    declarations.append(decl)
        return declarations

    async def _run_agent_step(self, run_id: str, agent: Dict[str, Any], goal: str, blackboard: SwarmBlackboard) -> Dict[str, Any]:
        """Execute an individual swarm agent: real tool calls via execute_tool, capped rounds."""
        agent_name = agent["name"]
        tools = agent["tools"]
        desc = agent["description"]
        log.info("Swarm agent %s starting for goal: %s", agent_name, goal[:40])

        executed: List[Dict[str, Any]] = []
        agent_text = ""
        gemini = None
        if self.coordinator and hasattr(self.coordinator, "gemini"):
            gemini = self.coordinator.gemini

        sub_decls = self._sub_tool_declarations(tools)
        if gemini and sub_decls:
            messages = [{"role": "system", "content": (
                f"You are the {agent_name} agent in the SALAR AI Swarm collaborating on: \"{goal}\". "
                f"Your specialty: {desc}. You may call ANY of your provided tools to gather real evidence "
                f"toward the goal. Call tools, read results, and summarize what you learned in plain language. "
                f"If a tool returns data, tell the user what it revealed. Keep summaries concise and factual."
            )}]
            try:
                from .agent import execute_tool
                for _round in range(self.max_tool_rounds):
                    result = await gemini.chat_with_tools(messages, [{"function_declarations": sub_decls}])
                    calls = result.get("function_calls", []) or []
                    if not calls:
                        agent_text = (result.get("text") or "").strip()
                        break
                    for fc in calls:
                        tool_name = fc.get("name", "")
                        tool_args = fc.get("args", {}) or {}
                        log.info("Swarm agent %s tool call: %s(%s)", agent_name, tool_name, json.dumps(tool_args)[:200])
                        try:
                            tool_result = await execute_tool(
                                tool_name, tool_args, self.user_id, self.db_session,
                                is_admin=self.is_admin, base_url=self.base_url, jwt_secret=self.jwt_secret,
                            )
                        except Exception as exc:
                            tool_result = {"error": str(exc)}
                        executed.append({"tool": tool_name, "args": tool_args, "result": tool_result})
                        messages.append({"role": "model", "content": [{"functionCall": fc}]})
                        messages.append({"role": "user", "content": [{"functionResponse": {"name": tool_name, "response": tool_result}}]})
                    t = (result.get("text") or "").strip()
                    if t:
                        agent_text = agent_text + ("\n" if agent_text else "") + t
            except Exception as e:
                log.warning("Swarm agent %s execution failed: %s", agent_name, e)
                agent_text = f"Agent {agent_name} could not execute tools: {e}"

        if not executed and not agent_text:
            finding_text = f"{agent_name} reviewed the goal '{goal[:60]}' ({desc}). No real tool calls were made."
        else:
            tool_notes = [f"{x['tool']}" for x in executed[:8]]
            evid = agent_text.strip()[:600]
            finding_text = evid or f"{agent_name} executed tools: {', '.join(tool_notes)}."
            if executed:
                finding_text = f"{agent_name} executed {len(executed)} tool call(s) [{' '.join(tool_notes)}]. " + (evid if evid else "")

        blackboard.publish(agent_name, finding_text, {
            "tools_used": [x["tool"] for x in executed] or tools[:2],
            "tool_calls": executed,
        })
        return {
            "name": agent_name,
            "status": "completed",
            "finding": finding_text,
            "tools": tools,
            "tool_calls": executed,
        }

    async def execute_swarm(self, run: AgentRun) -> Dict[str, Any]:
        """Execute all agents in parallel, collect findings, and produce master summary."""
        inp = json.loads(run.input_json or "{}")
        goal = inp.get("goal", "")
        agent_names = inp.get("agents", DEFAULT_AGENTS)

        agents = [{"name": n, "description": AGENT_SPECS.get(n, {}).get("description", ""), "tools": AGENT_SPECS.get(n, {}).get("tools", [])} for n in agent_names]
        blackboard = SwarmBlackboard()

        steps = self.db.query(AgentRunStep).filter(AgentRunStep.run_id == run.id).all()
        for step in steps:
            step.status = "running"
        self.db.commit()

        # Parallel execution across all agents
        tasks = [self._run_agent_step(run.id, a, goal, blackboard) for a in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        completed_count = 0
        for step, res in zip(steps, results):
            if isinstance(res, Exception):
                step.status = "failed"
                step.detail_json = json.dumps({"error": str(res)})
            else:
                step.status = "completed"
                step.detail_json = json.dumps({
                    "description": AGENT_SPECS.get(step.name, {}).get("description", ""),
                    "tools": AGENT_SPECS.get(step.name, {}).get("tools", []),
                    "finding": res.get("finding", ""),
                    "tool_calls": res.get("tool_calls", []),
                })
                completed_count += 1

        master_summary = {
            "goal": goal,
            "total_agents": len(agents),
            "completed_agents": completed_count,
            "blackboard": blackboard.summary(),
            "synthesized_at": datetime.now(timezone.utc).isoformat(),
        }

        run.status = "completed" if completed_count > 0 else "failed"
        run.output_json = json.dumps(master_summary)
        run.updated_at = utcnow()
        self.db.commit()

        return self.agent_summary(run)

    def agent_summary(self, run: AgentRun) -> Dict[str, Any]:
        steps = self.db.query(AgentRunStep).filter(AgentRunStep.run_id == run.id).order_by(AgentRunStep.sequence).all()
        return {
            "id": run.id,
            "kind": run.kind,
            "status": run.status,
            "input": json.loads(run.input_json or "{}"),
            "output": json.loads(run.output_json or "{}"),
            "agents": [
                {"name": s.name, "status": s.status, "detail": json.loads(s.detail_json or "{}")}
                for s in steps
            ],
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        }
