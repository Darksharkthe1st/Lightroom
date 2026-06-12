# Lightroom

GitHub-powered repository explorer that analyzes your code and commits to generate resume bullets.

## Architecture

```
┌─────────────┐     OAuth      ┌──────────────┐     GitHub API    ┌────────┐
│ Vite React  │ ◄────────────► │ FastAPI      │ ◄───────────────► │ GitHub │
│  Frontend   │   REST + cookie│   Backend    │                   └────────┘
└─────────────┘                └──────┬───────┘
                                      │
                              Per-repo agents
                              (browse → findings.md
                               → commits → bullets)
```

### Components

| Layer | Responsibility |
|-------|----------------|
| **Frontend** (`frontend/`) | GitHub OAuth via backend, list repos, view template summaries, trigger analysis, display resume bullets |
| **Backend** (`backend/`) | FastAPI app wiring auth, repos, and analysis routers |
| **GitHub service** | OAuth flow, list all accessible repos, fetch trees/files/commits |
| **Repo agents** | One agent per repository: browse code → `findings.md` → mine user commits → resume bullets |
| **Orchestrator** | Runs agents in parallel, aggregates bullets per user |

## Quick start

### 1. Create a GitHub OAuth App

1. Go to [GitHub Developer Settings → OAuth Apps](https://github.com/settings/developers)
2. New OAuth App:
   - **Homepage URL**: `http://localhost:5173`
   - **Authorization callback URL**: `http://localhost:8000/api/auth/github/callback`
3. Copy Client ID and generate a Client Secret

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GitHub credentials
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5173, authorize with GitHub, load repositories, click one for a template summary, then run analysis for resume bullets.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Check if user is authenticated |
| GET | `/api/auth/github/login` | Start GitHub OAuth |
| GET | `/api/auth/github/callback` | OAuth callback (redirects to frontend) |
| POST | `/api/auth/logout` | Clear session |
| GET | `/api/repos` | List all accessible repositories |
| GET | `/api/repos/{owner}/{repo}` | Template repository summary |
| GET | `/api/analysis/resume` | Get analysis status / bullets |
| POST | `/api/analysis/resume` | Analyze all repos for current user |
| POST | `/api/analysis/resume/{owner}/{repo}` | Analyze a single repo |

## Analysis pipeline

See **[docs/RESUME_BULLETS_PLAN.md](docs/RESUME_BULLETS_PLAN.md)** for the full Cursor SDK roadmap and milestone checkpoints.

**Current state:** Scout agent (Milestones 1 + 3) uses `cursor-sdk` cloud agents. Heuristic triage runs locally; scout runs on Cursor's cloud against the cloned repo.

### Run scout on a repo (CLI)

Add to `backend/.env`:

```bash
CURSOR_API_KEY=cursor_...          # Cursor Dashboard → Integrations
GITHUB_TOKEN=ghp_...               # PAT with repo scope (for triage + commits)
```

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt

# SDK smoke test (uses a repo connected in Cursor Dashboard → Integrations)
python scripts/run_scout.py --smoke

# Scout CodeRunner
python scripts/run_scout.py --owner Darksharkthe1st --repo CodeRunner
```

Outputs land in `backend/data/analysis/{owner}/{repo}/`:

- `triage.json` — heuristic signals (Phase 0)
- `findings.md` — scout analysis
- `rabbit_holes.json` — recommended deep dives
- `runs/scout.json` — agent/run IDs for debugging

## Environment variables

**Backend** (`backend/.env`):

- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`
- `GITHUB_REDIRECT_URI` (default: `http://localhost:8000/api/auth/github/callback`)
- `FRONTEND_URL` (default: `http://localhost:5173`)
- `SESSION_SECRET`

**Frontend** (`frontend/.env`):

- `VITE_API_URL` (default: `http://localhost:8000`)
