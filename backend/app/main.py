from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import __version__
from .api.auth import router as auth_router
from .api.chat import router as chat_router
from .api.memory import router as memory_router
from .api.projects import router as projects_router
from .api.documents import router as documents_router
from .api.devices import router as devices_router
from .config import Settings
from .database import Base, create_session_factory
from .models import User
from .security import hash_password
from .services.coordinator import AICoordinator
from .services.ollama import OllamaClient


def create_app(settings: Settings = None) -> FastAPI:
    active_settings = settings or Settings()
    engine, session_factory = create_session_factory(active_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_settings.storage_dir.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(engine)
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
        if not hasattr(app.state, "coordinator"):
            app.state.coordinator = AICoordinator(
                OllamaClient(active_settings.ollama_url, active_settings.ollama_model)
            )
        yield
        engine.dispose()

    app = FastAPI(title="SALAR API", version=__version__, lifespan=lifespan)
    app.state.settings = active_settings
    app.state.SessionLocal = session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "salar-backend", "version": __version__}

    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(memory_router)
    app.include_router(projects_router)
    app.include_router(documents_router)
    app.include_router(devices_router)
    return app


app = create_app()
