import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from . import __version__
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.memory import router as memory_router
from .api.projects import router as projects_router
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
from .api.billing import router as billing_router
from .api.intel import router as intel_router
from .api.missions import router as missions_router
from .api.models import router as models_router
from .api.permissions import router as permissions_router
from .api.thought_stream import router as thought_stream_router
from .api.action_log import router as action_log_router
from .api.guardian import router as guardian_router
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


def create_app(settings: Settings = None) -> FastAPI:
    active_settings = settings or Settings()
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
                app.state.coordinator = AICoordinator(gemini)
                log.info("SALAR ready — Gemini model: %s", active_settings.gemini_model)
            except Exception as e:
                log.error("Gemini client init failed: %s", e)
                raise

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
    app.include_router(chat_router)
    app.include_router(memory_router)
    app.include_router(projects_router)
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
    app.include_router(billing_router)
    app.include_router(intel_router)
    app.include_router(missions_router)
    app.include_router(models_router)
    app.include_router(permissions_router)
    app.include_router(thought_stream_router)
    app.include_router(action_log_router)
    app.include_router(guardian_router)
    return app


app = create_app()
