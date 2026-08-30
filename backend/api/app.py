from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.shadow_routes import router as shadow_router

from backend.bootstrap import create_system, start_system, shutdown_system
import os
from datetime import datetime, timezone


app = FastAPI(
    title="Hagmartk API",
    description="Plataforma Profissional de Inteligência para Mercados Financeiros",
    version="0.1.0",
)

# Permite que o frontend React acesse a API durante o desenvolvimento.
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
_extra_origins = [
    origin.strip()
    for origin in os.environ.get("HAGMARTK_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_default_origins, *_extra_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(shadow_router)


@app.get("/")
def home():
    return {
        "software": "Hagmartk",
        "status": "online",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


@app.on_event("startup")
def _startup_system():
    """Create the system components and optionally start the kernel.

    Controlled by the `HAGMARTK_AUTOSTART` environment variable. Default
    is to create components but not start them to keep test imports side-effect
    free.
    """
    adapter_mode = os.environ.get("HAGMARTK_MARKET_ADAPTER")
    system = create_system(adapter_mode=adapter_mode)
    app.state.system = system
    app.state.started_at = None

    autostart = os.environ.get("HAGMARTK_AUTOSTART", "1") == "1"
    if autostart:
        start_system(system)
        app.state.started_at = datetime.now(timezone.utc)


@app.on_event("shutdown")
def _shutdown_system():
    system = getattr(app.state, "system", None)
    if system is not None:
        shutdown_system(system)