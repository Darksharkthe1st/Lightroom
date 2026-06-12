# Lightroom

GitHub-powered repository explorer that analyzes your code and commits to generate resume bullets.

## Architecture

Lightroom currently has **two analysis paths**:

```
┌─────────────┐     OAuth      ┌──────────────┐     GitHub API    ┌────────┐
│ Vite React  │ ◄────────────► │ FastAPI      │ ◄───────────────► │ GitHub │
│  Frontend   │   REST + cookie│   Backend    │                   └────────┘
└─────────────┘                └──────┬───────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
            POST /api/analysis/*                 CLI: run_scout.py
            (heuristic RepoAgent)                (Cursor SDK cloud agents)
                    │                                   │
                    ▼                                   ▼
            template bullets                   triage → scout → (rabbit holes → synthesizer)
```

| Path | Entry point | Engine | Status |
|------|-------------|--------|--------|
| **Web API** | `POST /api/analysis/resume` | Heuristic `RepoAgent` (file tree + commits) | MVP — wired to frontend |
| **CLI / SDK** | `run_scout.py`, `run_rabbit_holes.py` | Cursor cloud agents via `cursor-sdk` | Scout + rabbit holes (M1–4) |

The SDK pipeline (scout → rabbit holes → synthesizer) is the target architecture. See **[docs/RESUME_BULLETS_PLAN.md](docs/RESUME_BULLETS_PLAN.md)** for milestones and checkpoints.

### Components

| Layer | Responsibility |
|-------|----------------|
| **Frontend** (`frontend/`) | GitHub OAuth via backend, list repos, view template summaries, trigger analysis, display resume bullets |
| **Backend** (`backend/`) | FastAPI app wiring auth, repos, and analysis routers |
| **GitHub service** | OAuth flow, list accessible repos, fetch trees/files/commits (paginated) |
| **Triage** (`triage.py`) | Phase 0 heuristics — file-tree signals, commit count, `triage.json` |
| **Scout** (`cursor_agents/scout.py`) | Phase 1 Cursor cloud agent — `findings.md`, `rabbit_holes.json` |
| **Rabbit holes** (`cursor_agents/rabbit_hole.py`) | Phase 2 parallel deep dives — `signals/{signal_id}.md` |
| **RepoAgent** (`repo_agent.py`) | Legacy heuristic agent — still used by `AnalysisOrchestrator` for API routes |
| **Orchestrator** (`orchestrator.py`) | Runs per-repo agents in parallel, aggregates bullets (API path today) |

## Quick start

### 1. Create a GitHub OAuth App

1. Go to [GitHub Developer Settings → OAuth Apps](https://github.com/settings/developers)
2. New OAuth App:
   - **Homepage URL**: `http://localhost:5173`
   - **Authorization callback URL**: `http://localhost:8000/api/auth/github/callback`
3. Copy Client ID and generate a Client Secret

### 2. Connect GitHub to Cursor (for SDK scout)

Cloud agent runs require the target repo to be **connected in [Cursor Dashboard → Integrations](https://cursor.com/dashboard)**. The smoke test and scout CLI verify this before launching agents.

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — see Environment variables below
uvicorn app.main:app --reload --port 8000
```

On Python 3.14+, if `pydantic-core` fails to build:

```bash
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 pip install -r requirements.txt
```

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5173, authorize with GitHub, load repositories, click one for a template summary, then run analysis for resume bullets (uses the heuristic API path today).

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
| POST | `/api/analysis/resume` | Analyze all repos (heuristic `RepoAgent`) |
| POST | `/api/analysis/resume/{owner}/{repo}` | Analyze a single repo (heuristic `RepoAgent`) |

## Analysis pipeline (Cursor SDK — CLI)

Phase 0 triage runs locally via GitHub API. Phase 1 scout runs on Cursor's cloud VM against a cloned repo.

### Prerequisites

- `CURSOR_API_KEY` in `backend/.env`
- `GITHUB_TOKEN` — PAT with `repo` scope (triage + commit fetch for the CLI)
- Target repo connected in Cursor Dashboard → Integrations

### Run scout

```bash
cd backend
source .venv/bin/activate

# SDK connectivity check (uses a Cursor-connected repo)
python scripts/run_scout.py --smoke

# Scout a specific repo
python scripts/run_scout.py --owner Darksharkthe1st --repo CodeRunner

# Rabbit-hole deep dives (requires scout output first)
python scripts/run_rabbit_holes.py --owner Darksharkthe1st --repo CodeRunner
python scripts/run_rabbit_holes.py --signal-id docker_execution_queue  # single signal
python scripts/run_rabbit_holes.py --dry-run  # preview selected holes
```

### Output files

Artifacts land in `backend/data/analysis/{owner}/{repo}/`:

| File | Phase | Description |
|------|-------|-------------|
| `triage.json` | 0 | Heuristic signals, commit count, `worth_deep_analysis` flag |
| `commits.json` | 0 | Paginated user commits (up to 500) |
| `findings.md` | 1 | Scout analysis (stack, architecture, recruiter signals) |
| `rabbit_holes.json` | 1 | Prioritized deep-dive recommendations |
| `runs/scout.json` | 1 | `agent_id`, `run_id`, status, duration |
| `runs/scout_response.txt` | 1 | Raw agent response (debug) |
| `runs/scout_artifacts.json` | 1 | SDK artifact manifest (often empty on cloud) |
| `signals/{signal_id}.md` | 2 | Per-signal deep dive with file/commit evidence |
| `runs/{signal_id}.json` | 2 | Per-hole run metadata |
| `signals/*.md` | 2 | Per-signal rabbit-hole notes *(not yet implemented)* |
| `bullets.json` | 3 | Final resume bullets *(not yet implemented)* |

Scout output is parsed from **delimiter blocks** in the agent's final message (`<<<LIGHTROOM_FINDINGS_MD>>>`, `<<<LIGHTROOM_RABBIT_HOLES_JSON>>>`). Cloud SDK `list_artifacts()` currently returns empty for scout runs; see `cursor_agents/artifacts.py`.

## Environment variables

**Backend** (`backend/.env`):

| Variable | Required for | Description |
|----------|--------------|-------------|
| `GITHUB_CLIENT_ID` | Web app | OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | Web app | OAuth app client secret |
| `GITHUB_REDIRECT_URI` | Web app | Default: `http://localhost:8000/api/auth/github/callback` |
| `FRONTEND_URL` | Web app | Default: `http://localhost:5173` |
| `SESSION_SECRET` | Web app | Cookie signing secret |
| `CURSOR_API_KEY` | Scout CLI | [Cursor Dashboard → Integrations](https://cursor.com/dashboard) |
| `CURSOR_MODEL` | Scout CLI | Default: `composer-2.5` |
| `GITHUB_TOKEN` | Scout CLI | PAT with `repo` scope (or pass `--token`) |

**Frontend** (`frontend/.env`):

- `VITE_API_URL` (default: `http://localhost:8000`)
