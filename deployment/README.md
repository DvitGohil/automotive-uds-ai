# 🐳 Docker Deployment Guide

> **Zero existing files were modified.** This deployment layer is purely additive.

---

## Prerequisites

| Tool             | Minimum Version | Check Command           |
|------------------|-----------------|-------------------------|
| Docker Engine    | 20.10+          | `docker --version`      |
| Docker Compose   | 2.0+ (V2)      | `docker compose version`|

---

## Quick Start

```bash
# 1. Navigate to the project root
cd automotive_uds_ai_checkpoint_before_fixes

# 2. (Optional) Copy .dockerignore to project root for faster builds
copy deployment\.dockerignore .dockerignore

# 3. Build and start all services
docker compose -f deployment/docker-compose.yml up --build

# 4. Access the application
#    Frontend  → http://localhost:3000
#    Backend   → http://localhost:8000/api/v1/health
```

To run in the background:
```bash
docker compose -f deployment/docker-compose.yml up --build -d
```

---

## Folder Structure

```
deployment/
├── docker-compose.yml      # Orchestrates backend + frontend services
├── backend.Dockerfile      # Multi-stage Python build (FastAPI)
├── frontend.Dockerfile     # Multi-stage Node → Nginx build (React)
├── nginx.conf              # Nginx: SPA routing + API reverse proxy
├── .env.docker             # Environment variables template
├── .dockerignore           # Build context filter (copy to project root)
└── README.md               # This file
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Host Machine                      │
│                                                     │
│  ┌──────────────┐         ┌──────────────────────┐  │
│  │   Frontend    │  :3000  │      Backend         │  │
│  │  (Nginx +    │────────▶│  (FastAPI + Uvicorn)  │  │
│  │   React SPA) │  /api/* │       :8000           │  │
│  └──────────────┘         └──────────┬───────────┘  │
│                                      │              │
│                               ┌──────▼──────┐       │
│                               │  SQLite DB  │       │
│                               │  FAISS idx  │       │
│                               │  (Volume)   │       │
│                               └─────────────┘       │
└─────────────────────────────────────────────────────┘
```

---

## Environment Configuration

Edit `deployment/.env.docker` before starting:

| Variable           | Default             | Notes                                  |
|--------------------|---------------------|----------------------------------------|
| `BACKEND_PORT`     | `8000`              | Host port for the API                  |
| `FRONTEND_PORT`    | `3000`              | Host port for the UI                   |
| `LLM_PROVIDER`     | `mock`              | Set to `anthropic` for real AI         |
| `LLM_API_KEY`      | *(empty)*           | Required when LLM_PROVIDER=anthropic   |
| `JWT_SECRET`       | *(empty)*           | Set a random hex string for production |
| `API_KEY`          | *(empty)*           | Set to require X-API-Key header        |

---

## Common Commands

All commands run from the **project root**:

```bash
# Start (foreground, with build)
docker compose -f deployment/docker-compose.yml up --build

# Start (background)
docker compose -f deployment/docker-compose.yml up -d

# Stop all services
docker compose -f deployment/docker-compose.yml down

# Stop and remove volumes (⚠ deletes data)
docker compose -f deployment/docker-compose.yml down -v

# View logs
docker compose -f deployment/docker-compose.yml logs -f
docker compose -f deployment/docker-compose.yml logs -f backend

# Rebuild a single service
docker compose -f deployment/docker-compose.yml build backend

# Shell into a running container
docker compose -f deployment/docker-compose.yml exec backend bash

# Check service health
docker compose -f deployment/docker-compose.yml ps
```

**Shortcut** – run from inside the `deployment/` folder to skip `-f`:
```bash
cd deployment
docker compose up --build
```

---

## Data Persistence

The backend uses a named Docker volume (`backend_data`) at `/app/data`:
- SQLite database
- FAISS vector index
- Uploaded documents

> **Backup**: `docker compose -f deployment/docker-compose.yml cp backend:/app/data ./backup`

---

## Production Considerations

1. **Secrets**: Set `JWT_SECRET`, `API_KEY`, and `LLM_API_KEY` in `.env.docker`
2. **HTTPS**: Add a reverse proxy (Traefik, Caddy) or TLS at load balancer
3. **Database**: Switch `DATABASE_URL` to PostgreSQL for production scale
4. **Scaling**: Backend is stateless (except SQLite) — switch to PostgreSQL then `--scale backend=3`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port already in use | Change `BACKEND_PORT`/`FRONTEND_PORT` in `.env.docker` |
| Backend unhealthy | `docker compose -f deployment/docker-compose.yml logs backend` |
| Frontend blank page | Ensure backend is healthy; check browser console |
| Build context too large | Copy `.dockerignore` to project root |
