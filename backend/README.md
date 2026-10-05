# RepoIQ Backend

FastAPI backend for discovering, analyzing, and understanding GitHub repositories.

This is intentionally MVP-focused. It supports repository search, URL analysis, stack detection, overview generation, module breakdowns, architecture summaries, and similar repository recommendations.

It does not include RAG, vector databases, LangChain, multi-agent systems, learning roadmaps, course generation, or interview preparation features.

## Folder Structure

```text
backend/
├── app/
│   ├── routes/
│   │   ├── search.py
│   │   ├── analyze.py
│   │   └── repository.py
│   ├── services/
│   │   ├── github_service.py
│   │   ├── analysis_service.py
│   │   ├── stack_detector.py
│   │   ├── llm_service.py
│   │   └── similar_repo_service.py
│   ├── models/
│   │   ├── repository.py
│   │   ├── analysis_result.py
│   │   └── analysis_job.py
│   ├── schemas/
│   │   ├── search.py
│   │   ├── analysis.py
│   │   └── repository.py
│   ├── utils/
│   │   ├── git_utils.py
│   │   ├── file_parser.py
│   │   └── repo_scanner.py
│   ├── config.py
│   ├── database.py
│   └── main.py
├── tests/
│   └── test_health.py
├── requirements.txt
├── .env.example
└── README.md
```

## File Responsibilities

`app/main.py` creates the FastAPI app, registers route modules, and exposes `/health`.

`app/config.py` loads environment variables for PostgreSQL, GitHub, OpenAI/Gemini, local clone storage, and future async job mode.

`app/database.py` owns the SQLAlchemy engine, base model, and request-scoped database session dependency.

`app/routes/search.py` exposes repository search. It receives an idea query and delegates GitHub API work to `GitHubService`.

`app/routes/analyze.py` exposes repository analysis. It receives a GitHub URL and delegates the full workflow to `AnalysisService`.

`app/routes/repository.py` fetches a stored repository analysis by ID.

`app/services/github_service.py` searches GitHub repositories, fetches repository metadata, and clones repositories.

`app/services/analysis_service.py` is the main orchestrator. It creates an analysis job, fetches metadata, clones the repo, scans files, detects stack, asks the LLM service for summaries, finds similar repos, and persists results.

`app/services/stack_detector.py` detects frontend, backend, database, and infrastructure stack from files and dependency manifests.

`app/services/llm_service.py` generates repository overview, module breakdown, and architecture summary. The current implementation is a safe MVP placeholder where OpenAI or Gemini calls can be added.

`app/services/similar_repo_service.py` recommends similar repositories using GitHub search based on repository name, language, and detected stack.

`app/models/repository.py` stores GitHub repository identity and basic metadata.

`app/models/analysis_result.py` stores the generated stack, overview, modules, architecture summary, and similar repositories.

`app/models/analysis_job.py` tracks analysis state: queued, running, completed, or failed.

`app/schemas/search.py` defines API response shapes for search results.

`app/schemas/analysis.py` defines the analyze request and response contracts.

`app/schemas/repository.py` defines the stored repository analysis response.

`app/utils/git_utils.py` contains small helpers for normalizing GitHub URLs and generating repo slugs.

`app/utils/file_parser.py` parses dependency files and reads bounded text previews.

`app/utils/repo_scanner.py` walks a cloned repository, skips noisy folders, collects files, dependencies, README text, and top-level modules.

`tests/test_health.py` verifies the API can boot and respond to `/health`.

## Route Layer Design

Routes should stay thin:

- Validate request data with Pydantic schemas.
- Inject dependencies such as database sessions and services.
- Call one service method.
- Return a schema response.

Route modules:

- `search.py`: `GET /search?q=idea`
- `analyze.py`: `POST /api/analyze`
- `repository.py`: `GET /api/repositories/{repository_id}`

## Service Layer Design

`AnalysisService` is the only high-level workflow owner.

Call relationships:

- `search.py` calls `GitHubService.search_repositories`.
- `analyze.py` calls `AnalysisService.analyze_repository`.
- `AnalysisService` calls `GitHubService.fetch_metadata`.
- `AnalysisService` calls `GitHubService.clone_repository`.
- `AnalysisService` calls `RepoScanner.scan`.
- `AnalysisService` calls `StackDetector.detect`.
- `AnalysisService` calls `LLMService.generate_overview`.
- `AnalysisService` calls `LLMService.generate_modules`.
- `AnalysisService` calls `LLMService.generate_architecture_summary`.
- `AnalysisService` calls `SimilarRepoService.find_similar_repositories`.
- `SimilarRepoService` calls `GitHubService.search_repositories`.
- `repository.py` reads stored `Repository` and nested `AnalysisResult` from PostgreSQL.

## Database Models

`Repository`

- `id`
- `github_url`
- `full_name`
- `description`
- `stars`
- `primary_language`
- `created_at`

`AnalysisResult`

- `id`
- `repository_id`
- `stack`
- `overview`
- `modules`
- `architecture_summary`
- `similar_repositories`
- `created_at`

`AnalysisJob`

- `id`
- `repo_url`
- `status`
- `repository_id`
- `created_at`
- `updated_at`

## End-to-End Analyze Flow

1. User clicks "Analyze Repository" in the frontend.
2. Frontend sends `POST /api/analyze` with `{ "repo_url": "https://github.com/owner/repo" }`.
3. `routes/analyze.py` validates the request with `AnalyzeRequest`.
4. `routes/analyze.py` calls `AnalysisService.analyze_repository`.
5. `AnalysisService` creates an `AnalysisJob` with status `running`.
6. `GitHubService.fetch_metadata` fetches repository metadata from the GitHub API.
7. `GitHubService.clone_repository` clones the repository into `CLONE_BASE_DIR`.
8. `RepoScanner.scan` extracts file paths, dependencies, README preview, and top-level folders.
9. `StackDetector.detect` returns frontend, backend, database, and infrastructure stack.
10. `LLMService` generates overview, module breakdown, and architecture summary.
11. `SimilarRepoService` searches GitHub for related repositories.
12. `AnalysisService` stores `Repository` and `AnalysisResult` in PostgreSQL.
13. `AnalysisService` marks the `AnalysisJob` as `completed`.
14. API returns `AnalyzeResponse` with `job_id`, `repository_id`, status, and message.
15. Frontend can fetch stored analysis with `GET /api/repositories/{repository_id}`.

## Future SQS Worker Integration Points

The current MVP can run analysis synchronously. For larger repositories, use the existing `AnalysisJob` model and `AnalysisService.enqueue_analysis`.

Future flow:

1. `routes/analyze.py` creates an `AnalysisJob` with status `queued`.
2. API publishes `{ "job_id": 123, "repo_url": "..." }` to SQS.
3. A worker consumes the SQS message.
4. The worker calls the same `AnalysisService.analyze_repository` workflow or a job-specific variant.
5. Worker updates `AnalysisJob.status` to `completed` or `failed`.
6. Frontend polls `GET /api/repositories/{repository_id}` or a future `GET /api/analyze/jobs/{job_id}` endpoint.

This keeps the route layer unchanged and moves long-running work out of the web request when needed.

## Local Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

On Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```
