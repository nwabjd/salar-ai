import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, select, text

from . import __version__
from .api.core import router as core_router
from .api.world import router as world_router
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.memory import router as memory_router
from .api.memory_graph import router as memory_graph_router
from .api.projects import router as projects_router
from .api.attachments import router as attachments_router
from .api.documents import router as documents_router
from .api.devices import router as devices_router
from .api.tts import router as tts_router
from .api.stt import router as stt_router
from .api.agent import router as agent_router
from .api.whatsapp import router as whatsapp_router
from .api.email import router as email_router
from .api.monitor import router as monitor_router
from .api.calendar import router as calendar_router
from .api.alerts import router as alerts_router
from .api.files import router as files_router
from .api.code_interpreter import router as code_router
from .api.workspaces import router as workspaces_router
from .api.tasks import router as tasks_router
from .api.reminders import router as reminders_router
from .api.knowledge import router as knowledge_router
from .api.workflows import router as workflows_router
from .api.live import router as live_router
from .api.ollama import router as ollama_router
from .api.nim import router as nim_router
from .api.billing import router as billing_router
from .api.intel import router as intel_router
from .api.missions import router as missions_router
from .api.models import router as models_router
from .api.permissions import router as permissions_router
from .api.search import router as search_router
from .api.command_center import router as command_center_router
from .api.thought_stream import router as thought_stream_router
from .api.action_log import router as action_log_router
from .api.guardian import router as guardian_router
from .api.swarm import router as swarm_router
from .api.deep_research import router as deep_research_router
from .api.proactive import router as proactive_router
from .api.eod import router as eod_router
from .api.predictive import router as predictive_router
from .api.decision_simulator import router as decision_simulator_router
from .api.contacts import router as contacts_router
from .api.vision import router as vision_router
from .api.clipboard import router as clipboard_router
from .api.browser_intel import router as browser_intel_router
from .api.ui_analyzer import router as ui_analyzer_router
from .api.voice import router as voice_router
from .api.bookmarks import router as bookmarks_router
from .api.dynamic_memory import router as dynamic_memory_router
from .api.knowledge_viz import router as knowledge_viz_router
from .api.insights import router as insights_router
from .api.email_classifier import router as email_classifier_router
from .api.notifications import router as notifications_router
from .api.automation import router as automation_router
from .api.file_assistant import router as file_assistant_router
from .api.file_organizer import router as file_organizer_router
from .api.app_launcher import router as app_launcher_router
from .api.media_controller import router as media_controller_router
from .api.audio_intel import router as audio_intel_router
from .api.perf_dashboard import router as perf_dashboard_router
from .api.network_intel import router as network_intel_router
from .api.device_automation import router as device_automation_router
from .api.consent import router as consent_router
from .api.vault import router as vault_router
from .api.privacy_scan import router as privacy_scan_router
from .api.privacy_prefs import router as privacy_prefs_router
from .api.dev_docs import router as dev_docs_router
from .api.multi_device import router as multi_device_router
from .api.plugins import router as plugins_router
from .api.image_gen import router as image_gen_router
from .api.media_memory import router as media_memory_router
from .api.creative_templates import router as creative_templates_router
from .api.presentation import router as presentation_router
from .api.widgets import router as widgets_router
from .api.retrieval import router as retrieval_router
from .api.users import router as users_router
from .api.ar_status import router as ar_status_router
from .api.wallpapers import router as wallpapers_router
from .services.whatsapp import WhatsAppClient
from .config import Settings
from .database import Base, create_session_factory
from .models import User
from .security import hash_password
from .services.agents import AgentOrchestrator
from .services.coordinator import AICoordinator
from .services.gemini import GeminiClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _apply_inline_migrations(engine) -> None:
    """Additive, idempotent column migrations for existing SQLite databases."""
    try:
        inspector = inspect(engine)
        if not inspector.has_table("memories"):
            return
        existing = {c["name"] for c in inspector.get_columns("memories")}
        with engine.begin() as conn:
            for name, ddl in {
                "strength": "ALTER TABLE memories ADD COLUMN strength FLOAT DEFAULT 1.0",
                "expired": "ALTER TABLE memories ADD COLUMN expired BOOLEAN DEFAULT 0",
                "encrypted": "ALTER TABLE memories ADD COLUMN encrypted BOOLEAN DEFAULT 0",
                "expires_at": "ALTER TABLE memories ADD COLUMN expires_at DATETIME",
            }.items():
                if name not in existing:
                    conn.execute(text(ddl))
        existing_p = {c["name"] for c in inspector.get_columns("projects")}
        with engine.begin() as conn:
            for name, ddl in {
                "status": "ALTER TABLE projects ADD COLUMN status VARCHAR(32) DEFAULT 'active'",
                "goals_json": "ALTER TABLE projects ADD COLUMN goals_json TEXT DEFAULT '[]'",
                "deadline": "ALTER TABLE projects ADD COLUMN deadline DATETIME",
                "updated_at": "ALTER TABLE projects ADD COLUMN updated_at DATETIME",
            }.items():
                if name not in existing_p:
                    conn.execute(text(ddl))
    except Exception:
        log.warning("Inline schema migration skipped", exc_info=True)


def create_app(settings: Settings = None) -> FastAPI:
    active_settings = settings or Settings()
    if active_settings.environment == "production":
        if active_settings.jwt_secret in {"", "change-this-development-secret-before-deployment"}:
            raise RuntimeError(
                "Refusing to start in production: SALAR_JWT_SECRET is unset or the insecure default."
            )
        if active_settings.bootstrap_password == "ChangeMeImmediately!" and not active_settings.supabase_url:
            raise RuntimeError(
                "Refusing to start in production: SALAR_BOOTSTRAP_PASSWORD is the insecure default "
                "and no Supabase auth is configured."
            )
    engine, session_factory = create_session_factory(active_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("SALAR backend starting...")
        active_settings.storage_dir.mkdir(parents=True, exist_ok=True)

        from .services.file_manager import DEFAULT_ROOT
        DEFAULT_ROOT = active_settings.storage_dir / "users"
        DEFAULT_ROOT.mkdir(parents=True, exist_ok=True)

        try:
            Base.metadata.create_all(engine)
            _apply_inline_migrations(engine)
            log.info("Database ready")
        except Exception as e:
            log.error("Database init failed: %s", e)
            raise

        if active_settings.environment != "production":
            try:
                with session_factory() as db:
                    email = active_settings.bootstrap_email.lower()
                    existing = db.scalar(select(User).where(User.email == email))
                    if existing is None:
                        db.add(
                            User(
                                email=email,
                                password_hash=hash_password(active_settings.bootstrap_password),
                                is_admin=True,
                            )
                        )
                        db.commit()
                        log.info("Bootstrap user created: %s", email)
                    else:
                        log.info("Bootstrap user exists: %s", email)
            except Exception as e:
                log.error("Bootstrap user setup failed: %s", e)

        if not hasattr(app.state, "coordinator"):
            try:
                gemini = GeminiClient(active_settings.gemini_api_key, active_settings.gemini_model)
                nim = None
                if getattr(active_settings, "nim_api_key", None):
                    from .services.nim import NIMProvider
                    nim = NIMProvider(active_settings.nim_api_key, active_settings.nim_base_url)
                    log.info("NIM provider ready — base: %s", active_settings.nim_base_url)
                app.state.coordinator = AICoordinator(gemini)
                app.state.nim = nim  # NIMProvider or None
                log.info("SALAR ready — Gemini model: %s", active_settings.gemini_model)
            except Exception as e:
                log.error("Gemini client init failed: %s", e)
                raise

        from .services.core.events import CoreBus
        from .services.core.verification import VerificationEngine
        from .services.core.confidence import ConfidenceSystem
        from .services.core.toolspec import ToolRegistry
        from .services.core.correction import SelfCorrectionLoop
        from .services.core.brain import CoreBrain
        from .services.core.runtime import AgentRuntime
        from .services.core.supervisor import Supervisor
        from .services.core.pipeline import CorePipeline

        app.state.core_bus = CoreBus(db_factory=session_factory)

        from .services.world_model import WorldGraph, WorldIngestor

        def _world_graph():
            return WorldGraph(session_factory())

        app.state.world_graph_factory = _world_graph
        app.state.world_graph = None  # lazily created per request via api/world.py
        app.state.world_ingestor_factory = lambda: WorldIngestor(_world_graph())

        from .services.core.events import TOOL_RESULT, TASK_COMPLETED, TASK_FAILED, TASK_STARTED, VERIFICATION_FAILED

        def _world_core_observer(event):
            """Ingest core pipeline events into the world graph."""
            payload = event.payload or {}
            user_id = payload.get("user_id")
            if not user_id:
                return
            try:
                with session_factory() as db:
                    graph = WorldGraph(db)
                    ingestor = WorldIngestor(graph)
                    if event.type == TOOL_RESULT:
                        ingestor.ingest_tool(user_id, {
                            "tool": payload.get("tool") or payload.get("name"),
                            "args": payload.get("args") or {},
                            "result": payload.get("result") or {},
                        }, source="core")
                    else:
                        ingestor.ingest_core_event(user_id, {**payload, "type": event.type})
                    graph.journal(user_id, source="core", event_type=event.type, payload=payload)
                    db.commit()
            except Exception:
                log.exception("world ingest failed for %s", event.type)

        app.state.core_bus.subscribe(TOOL_RESULT, _world_core_observer)
        app.state.core_bus.subscribe(TASK_COMPLETED, _world_core_observer)
        app.state.core_bus.subscribe(TASK_FAILED, _world_core_observer)
        app.state.core_bus.subscribe(TASK_STARTED, _world_core_observer)
        app.state.core_bus.subscribe(VERIFICATION_FAILED, _world_core_observer)
        app.state.core_verifier = VerificationEngine()
        app.state.core_confidence = ConfidenceSystem()
        app.state.core_registry = ToolRegistry()
        app.state.core_correction = SelfCorrectionLoop(
            registry=app.state.core_registry,
            verifier=app.state.core_verifier,
            confidence=app.state.core_confidence,
            bus=app.state.core_bus
        )
        app.state.core_brain = CoreBrain(registry=app.state.core_registry)
        app.state.core_runtime = AgentRuntime(
            bus=app.state.core_bus,
            correction=app.state.core_correction,
            confidence=app.state.core_confidence
        )
        app.state.core_supervisor = Supervisor(bus=app.state.core_bus, registry=app.state.core_registry)
        app.state.core_pipeline = CorePipeline(
            brain=app.state.core_brain,
            runtime=app.state.core_runtime,
            bus=app.state.core_bus,
            supervisor=app.state.core_supervisor,
            db_factory=session_factory,
            confidence=app.state.core_confidence
        )
        app.state.core_bus.subscribe("SUPERVISOR_ALERT", app.state.core_supervisor.watch)
        log.info("Core intelligence runtime wired")

        if not hasattr(app.state, "agent_orchestrator"):
            app.state.agent_orchestrator = AgentOrchestrator()
            log.info("Hidden agent orchestrator initialized")


        app.state.whatsapp = WhatsAppClient(
            bridge_url=active_settings.bridge_url
        )
        log.info("WhatsApp bridge client initialized")

        from .api.alerts import get_engine
        alert_engine = get_engine()
        await alert_engine.start(interval=60)
        log.info("Alert engine started")

        from .services.reminder_engine import get_engine as get_reminder_engine
        reminder_engine = get_reminder_engine()
        reminder_engine.configure(engine, session_factory)
        await reminder_engine.start(interval=30)
        log.info("Reminder engine started")

        from .services.jobs.contracts import JobRegistry
        from .services.jobs import handlers as job_handlers
        from .services.jobs.worker import JobWorker
        from .services.jobs.scheduler import IntelScheduler
        job_registry = JobRegistry()
        job_handlers.register_all(job_registry)
        app.state.job_registry = job_registry

        if active_settings.environment != "test":
            app.state.job_worker = JobWorker(
                session_factory=session_factory,
                settings=active_settings,
                registry=job_registry,
            )
            await app.state.job_worker.start()
            log.info("Job worker started (kinds: %s)", ", ".join(job_registry.kinds()))

            app.state.intel_scheduler = IntelScheduler(
                session_factory=session_factory,
                email_watch_interval_seconds=int(getattr(active_settings, "intel_email_watch_interval_seconds", 900)),
                morning_brief_hour=int(getattr(active_settings, "intel_morning_brief_hour", 7)),
            )
            await app.state.intel_scheduler.start()
            log.info("Intel scheduler started")

            from .services.missions.runner import MissionRunner
            from .services.agent import execute_tool as _execute_tool
            app.state.mission_runner = MissionRunner(
                session_factory=session_factory,
                gemini=app.state.coordinator.gemini,
                execute_tool_fn=_execute_tool,
            )
            await app.state.mission_runner.start()
            log.info("Mission runner started")

        yield

        log.info("SALAR backend shutting down...")
        if hasattr(app.state, "coordinator") and hasattr(app.state.coordinator, "gemini"):
            try:
                await app.state.coordinator.gemini.close()
            except Exception:
                pass
        if hasattr(app.state, "whatsapp"):
            try:
                await app.state.whatsapp.close()
            except Exception:
                pass
        if hasattr(app.state, "intel_scheduler"):
            try:
                await app.state.intel_scheduler.stop()
            except Exception:
                pass
        if hasattr(app.state, "job_worker"):
            try:
                await app.state.job_worker.stop()
            except Exception:
                pass
        if hasattr(app.state, "mission_runner"):
            try:
                await app.state.mission_runner.stop()
            except Exception:
                pass
        engine.dispose()

    app = FastAPI(title="SALAR API", version=__version__, lifespan=lifespan)
    app.state.settings = active_settings
    app.state.SessionLocal = session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.allowed_origins,
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        log.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "salar-backend", "version": __version__}

    app.include_router(auth_router)
    from .api.auth_relay import router as auth_relay_router
    app.include_router(auth_relay_router)
    app.include_router(world_router)
    app.include_router(chat_router)
    app.include_router(memory_router)
    app.include_router(projects_router)
    app.include_router(attachments_router)
    app.include_router(documents_router)
    app.include_router(devices_router)
    app.include_router(tts_router)
    app.include_router(stt_router)
    app.include_router(agent_router)
    app.include_router(whatsapp_router)
    app.include_router(email_router)
    app.include_router(monitor_router)
    app.include_router(calendar_router)
    app.include_router(alerts_router)
    app.include_router(files_router)
    app.include_router(code_router)
    app.include_router(workspaces_router)
    app.include_router(tasks_router)
    app.include_router(reminders_router)
    app.include_router(knowledge_router)
    app.include_router(workflows_router)
    app.include_router(live_router)
    app.include_router(ollama_router)
    app.include_router(nim_router)
    app.include_router(billing_router)
    app.include_router(intel_router)
    app.include_router(missions_router)
    app.include_router(models_router)
    app.include_router(permissions_router)
    app.include_router(thought_stream_router)
    app.include_router(memory_graph_router)
    app.include_router(search_router)
    app.include_router(command_center_router)
    app.include_router(action_log_router)
    app.include_router(guardian_router)
    app.include_router(swarm_router)
    app.include_router(deep_research_router)
    app.include_router(proactive_router)
    app.include_router(eod_router)
    app.include_router(predictive_router)
    app.include_router(decision_simulator_router)
    app.include_router(contacts_router)
    app.include_router(vision_router)
    app.include_router(clipboard_router)
    app.include_router(browser_intel_router)
    app.include_router(ui_analyzer_router)
    app.include_router(voice_router)
    app.include_router(bookmarks_router)
    app.include_router(dynamic_memory_router)
    app.include_router(knowledge_viz_router)
    app.include_router(insights_router)
    app.include_router(email_classifier_router)
    app.include_router(notifications_router)
    app.include_router(automation_router)
    app.include_router(file_assistant_router)
    app.include_router(file_organizer_router)
    app.include_router(app_launcher_router)
    app.include_router(media_controller_router)
    app.include_router(audio_intel_router)
    app.include_router(perf_dashboard_router)
    app.include_router(network_intel_router)
    app.include_router(device_automation_router)
    app.include_router(consent_router)
    app.include_router(vault_router)
    app.include_router(privacy_scan_router)
    app.include_router(privacy_prefs_router)
    app.include_router(dev_docs_router)
    app.include_router(multi_device_router)
    app.include_router(plugins_router)
    app.include_router(image_gen_router)
    app.include_router(media_memory_router)
    app.include_router(creative_templates_router)
    app.include_router(presentation_router)
    app.include_router(widgets_router)
    app.include_router(ar_status_router)
    app.include_router(wallpapers_router)
    app.include_router(retrieval_router)
    app.include_router(users_router)
    app.include_router(core_router)
    return app


app = create_app()
