from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import analyze, repository, search


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
    print(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    print(f"Response: {response.status_code}")
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
