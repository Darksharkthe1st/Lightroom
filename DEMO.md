# Lightroom — Hackathon Demo (2 min)

**Tagline:** Cursor agents analyze your GitHub repos and turn real code + commits into recruiter-ready resume bullets.

## Start (30 sec)

```bash
# Terminal 1 — backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open **http://localhost:5173** → **Authorize with GitHub** → **Load my repositories**.

## Demo flow (90 sec)

1. **Click `Darksharkthe1st/CodeRunner`** — this repo has pre-loaded scout + rabbit-hole analysis (ships in `backend/seed_data/`).
2. Show the **AI Analysis** summary — scout findings, tech stack, pipeline status (triage → scout → deep dives).
3. Click **Generate resume bullets** — instant bullets from rabbit-hole agents (evidence-backed, expandable).
4. Expand **Evidence** on a bullet — cite files, commits, signal deep dive.

## What powers it

| Phase | What | Output |
|-------|------|--------|
| 0 Triage | GitHub API heuristics | `triage.json` |
| 1 Scout | Cursor cloud agent | `findings.md`, `rabbit_holes.json` |
| 2 Rabbit holes | Parallel Cursor agents per signal | `signals/*.md` |
| 3 API | Loads artifacts → bullets | Frontend |

## One-liner for judges

> "We spawn Cursor agents per repository — a scout maps the stack, then specialist agents go down rabbit holes on Docker, LLM, and infra signals, mining commits and file evidence to produce resume bullets you can actually defend in an interview."

## Pre-loaded demo data

`backend/data/analysis/Darksharkthe1st/CodeRunner/` includes scout + docker execution queue deep dive. No live SDK run needed during the demo.
