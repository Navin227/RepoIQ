# RepoIQ Docker Development

Run these commands from `infrastructure/docker`.

## Start

Copy `.env.example` to `.env` and change local values as needed. API credentials remain in the existing backend `.env`; they are passed to the backend only when that file exists and are never stored in an image.

```powershell
docker compose up --build
```

The frontend is available at `http://localhost:3000`, the backend at `http://localhost:8000`, and the backend health check at `http://localhost:8000/health`.

## Lifecycle commands

```powershell
# Start in the background
docker compose up --build -d

# Stop and remove containers, preserving the database volume
docker compose down

# Rebuild images without using the build cache
docker compose build --no-cache

# Follow all logs, or one service
docker compose logs -f
docker compose logs -f backend

# List services and container status
docker compose ps
```

## PostgreSQL commands

```powershell
# Open a psql shell in the database container
docker compose exec postgres psql -U repoiq -d repoiq

# List databases
docker compose exec postgres psql -U repoiq -d repoiq -c '\l'

# List tables in the RepoIQ database
docker compose exec postgres psql -U repoiq -d repoiq -c '\dt'

# Remove containers but keep the named database volume
docker compose down

# Completely reset the database, including persistent data
docker compose down -v
```

## Development mounts and networking

The backend mounts `backend/app` into the container and runs Uvicorn with reload. The frontend mounts its source and Vite entry files and keeps `node_modules` inside the image. PostgreSQL data uses the named `repoiq_postgres_data` volume, never a host bind mount.

All services share the `repoiq` bridge network. Backend-to-PostgreSQL traffic uses the Compose service name `postgres`. Browser-to-backend traffic uses the host-published URL `http://localhost:8000`, injected into Vite as `VITE_API_BASE_URL`.