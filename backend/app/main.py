from contextlib import asynccontextmanager
import logging
import re
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import analyze, repository, search
from app.services.analysis_diagnostics import emit, run_context

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RepoIQ Backend",
    description="API for discovering and analyzing GitHub repositories.",
    version="0.1.0",
    lifespan=lifespan,
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    if not request.url.path.startswith("/analyze"):
        return await call_next(request)
    candidate = request.headers.get("x-analysis-run-id", "")
    run_id = candidate if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", candidate) else ""
    started = time.perf_counter()
    with run_context(run_id):
        emit(logger, "http_request_received", stage="http", method=request.method, path=request.url.path)
        try:
            response = await call_next(request)
        except Exception as exc:
            emit(logger, "http_request_failed", level=logging.ERROR, stage="http", method=request.method,
                 path=request.url.path, exception_type=type(exc).__name__, reason=str(exc), exc_info=True)
            raise
        emit(logger, "http_response_sent", stage="http", method=request.method, path=request.url.path,
             status_code=response.status_code, duration_ms=round((time.perf_counter() - started) * 1000))
        return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://main.d20r18yhh140ff.amplifyapp.com",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
app.include_router(repository.router, prefix="/api/repositories", tags=["repositories"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
