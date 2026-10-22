"""FastAPI application entrypoint.

Serves the typed API and the built React frontend from a single process so a reviewer can run
one command and see the product.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.models.db import get_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static" / "app"

app = FastAPI(
    title="ResultRelay",
    version="0.1.0",
    description=(
        "Policy-governed clinical-result communication prototype. Synthetic data only. "
        "Not a clinical service; does not diagnose or advise treatment."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demonstration prototype; no credentials are used or issued
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def _startup() -> None:
    get_engine()


@app.get("/api")
def api_root() -> dict[str, str]:
    return {"service": "ResultRelay API", "docs": "/api/docs", "disclaimer": "synthetic data only"}


# Serve the built frontend when it exists; otherwise explain how to build it.
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
    # The exported evidence manifest is a static artefact, not an API response: a reviewer can
    # download it with curl and check the claims without the server being involved.
    if (STATIC_DIR / "data").exists():
        app.mount("/data", StaticFiles(directory=STATIC_DIR / "data"), name="data")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api"):
            return JSONResponse({"detail": "not found"}, status_code=404)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "frontend build missing"}, status_code=404)
else:

    @app.get("/")
    def no_frontend() -> JSONResponse:
        return JSONResponse(
            {
                "detail": "Frontend build not found.",
                "build": "cd frontend && npm install && npm run build",
                "api": "/api/docs",
            }
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=False)
