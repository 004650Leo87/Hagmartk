from fastapi import FastAPI

from backend.api.routes import router

app = FastAPI(
    title="Hagmartk API",
    description="Plataforma Profissional de Inteligência para Mercados Financeiros",
    version="0.1.0"
)

app.include_router(router)


@app.get("/")
def home():

    return {
        "software": "Hagmartk",
        "status": "online",
        "version": "0.1.0"
    }


@app.get("/health")
def health():

    return {
        "status": "ok"
    }