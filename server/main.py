import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.auth import router as auth_router
from server.routes.admin import router as admin_router
from server.routes.optimizer import router as optimizer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.environ.get("DATA_DIR", "data"), exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)

# CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth_router)
app.include_router(optimizer_router)
app.include_router(admin_router)

# Static files (production: serve Vite build output)
dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dist")
if os.path.isdir(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

    @app.get("/{path:path}")
    async def spa_fallback(request: Request, path: str):
        file_path = os.path.realpath(os.path.join(dist_dir, path))
        if not file_path.startswith(os.path.realpath(dist_dir)):
            return FileResponse(os.path.join(dist_dir, "index.html"))
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))
