"""FastAPI-app: monterar routrarna och CORS.

Schema-migrationer hanteras av Alembic — appen skapar inte tabeller vid start.
Auth-routern (users/orgs/login) hör till en egen modul och monteras här när den
är på plats.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, board, generation, projects

app = FastAPI(title="AI Project Manager API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(generation.router)
app.include_router(board.router)


@app.get("/health", tags=["meta"])
async def healthcheck():
    return {"status": "ok"}
