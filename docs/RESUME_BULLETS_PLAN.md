# Resume Bullets Generator — Implementation Plan

Cursor SDK–powered pipeline that analyzes GitHub repositories and produces recruiter-quality resume bullets with traceable evidence.

## Goals

| Goal | Approach |
|------|----------|
| Recruiter-relevant tech recognition | Shared signal taxonomy + scout agent |
| Deep investigation when warranted | Rabbit-hole agents per high-confidence signal |
| Traceable bullets | Every bullet links to commits, files, and signal notes |
| Fits existing API | Same analysis endpoints; richer async job status over time |

## Architecture

```
Phase 0 (Triage)     →  triage.json          [Python heuristics, no SDK]
Phase 1 (Scout)      →  findings.md         [1 cloud SDK run / repo]
                       rabbit_holes.json
Phase 2 (Rabbit holes) → signals/*.md        [0–N parallel cloud SDK runs]
Phase 3 (Synthesizer)  → bullets.json        [1 cloud SDK run / repo]
```

```mermaid
flowchart TB
  subgraph triage [Phase 0 - Triage]
    GH[GitHub API] --> Tree[File tree + key files]
    GH --> Commits[User commits]
    Tree --> Signals[Signal detector]
  end

  subgraph scout [Phase 1 - Scout Agent]
    Signals --> Scout[Scout Agent - cloud]
    Commits --> Scout
    Scout --> Findings[findings.md]
    Scout --> RabbitPlan[rabbit_holes.json]
  end

  subgraph holes [Phase 2 - Rabbit-hole Agents]
    RabbitPlan --> R1[Per-signal agents]
    R1 --> S1[signals/*.md]
  end

  subgraph synth [Phase 3 - Synthesizer]
    Findings --> Synth[Synthesizer Agent]
    S1 --> Synth
    Commits --> Synth
    Synth --> Bullets[bullets.json]
  end

  Bullets --> API[FastAPI response]
```

**Runtime:** Cloud agents (`cursor-sdk`) clone repos on Cursor VMs. Phase 0 stays on the FastAPI server via GitHub API.

## Artifact layout (per repo)

```
backend/data/analysis/{owner}/{repo}/
  triage.json
  findings.md
  rabbit_holes.json
  signals/
  commits.json
  bullets.json
  runs/
    scout.json
    {signal_id}.json
    synthesizer.json
```

## Recruiter signal taxonomy

Signals are defined in `backend/app/services/analysis/taxonomy.yaml` (Milestone 2). Categories:

- **Languages** — Python, TypeScript, Go, Rust, Java
- **Frameworks** — React, Next.js, FastAPI, Django, Spring
- **Cloud & infra** — AWS, GCP, Docker, Kubernetes, Terraform
- **Data** — PostgreSQL, Redis, Kafka, Elasticsearch
- **Practices** — CI/CD, testing, observability, auth/OAuth
- **Architecture** — microservices, event-driven, caching, queues

Each signal has: `id`, `display_name`, `resume_keywords`, `file_patterns`, `config_markers`, `rabbit_hole_prompt_template`, `min_confidence_to_spawn`.

## Gating rules

| Condition | Action |
|-----------|--------|
| User has 0 commits in repo | Template bullet only, skip SDK |
| Fork with no user commits | Skip |
| < 3 signals above threshold AND < 5 commits | Scout only, no rabbit holes |
| Per repo | Max 3 rabbit-hole agents |
| Per user (analyze-all) | Max 5 repos in parallel (configurable) |

## SDK integration

- **Package:** `cursor-sdk` (Python)
- **Async:** `AsyncClient.launch_bridge` + `AsyncAgent`
- **Scout / holes / synth:** `Agent.create` + `send` + `wait` (artifacts + run metadata)
- **Runtime:** `CloudAgentOptions(repos=[CloudRepository(...)])`
- **Model:** `composer-2.5`
- **Auth:** `CURSOR_API_KEY` in `backend/.env`

### Error handling

- `CursorAgentError` → run never started (auth, config, network)
- `result.status == "error"` → run started but failed (inspect `run.id`, transcript)
- Log `agent_id` and `run.id` to `runs/*.json` immediately after `send()`

## Cost & safety controls

- Per repo: scout + ≤3 rabbit holes + synthesizer = **max 5 SDK runs**
- Per-user analyze-all: cap at **5 repos** initially
- Timeout: **10 min** per SDK run
- Every prompt: **no fabrication** — bullets require file or commit evidence

## Open decisions

| # | Question | Current default |
|---|----------|-----------------|
| 1 | Private repo cloud clone auth | Pass GitHub token via `env_vars` if needed; fallback to local clone |
| 2 | Analyze-all vs selective | Start with single-repo SDK analysis |
| 3 | Sync vs async API | Blocking for single-repo MVP; `202 + job_id` before analyze-all |
| 4 | Bullet tone | Third-person resume fragments (no "I") |

---

## Milestones (checkpoints)

### Milestone 1 — SDK plumbing

- [x] Add `cursor-sdk` to `backend/requirements.txt`
- [x] Add `CURSOR_API_KEY` to config and `.env.example`
- [x] Create `backend/app/services/analysis/cursor_agents/` module
  - [x] `client.py` — async cloud agent helpers
  - [x] `errors.py` — `CursorAgentError` vs run failure handling
  - [x] `prompts.py` — prompt templates
- [ ] Smoke test: one cloud `Agent.prompt` against a public repo
- [x] CLI: `backend/scripts/run_scout.py` entry point

**Done when:** `python scripts/run_scout.py --repo owner/name` connects to Cursor cloud and returns a run result.

---

### Milestone 2 — Taxonomy + triage

- [ ] `taxonomy.yaml` with ~20 high-value recruiter signals
- [ ] `signal_detector.py` producing `triage.json`
- [ ] Gating logic (`worth_deep_analysis`, rabbit-hole eligibility)
- [ ] Unit tests for signal detection from file trees

**Done when:** Triage runs without SDK and writes `triage.json` for any accessible repo.

---

### Milestone 3 — Scout agent

- [x] Scout prompt: confirm signals, write `findings.md`, plan `rabbit_holes.json`
- [x] `scout.py` — orchestrates cloud agent, persists artifacts locally
- [x] `runs/scout.json` — agent_id, run_id, status, duration
- [ ] Manual validation on **Darksharkthe1st/CodeRunner**

**Done when:** Scout produces `findings.md` and `rabbit_holes.json` with recruiter-relevant signals and evidence-backed rabbit-hole recommendations.

---

### Milestone 4 — Rabbit-hole agents

- [ ] Per-signal prompt templates from taxonomy
- [ ] `rabbit_hole.py` — parallel runner with semaphore (max 3)
- [ ] Failure isolation per signal
- [ ] `signals/{signal_id}.md` artifacts

**Done when:** At least one rabbit hole on CodeRunner produces a signal note with file/commit evidence.

---

### Milestone 5 — Synthesizer + API

- [ ] `synthesizer.py` — merge findings + signals + commits → `bullets.json`
- [ ] Map `bullets.json` → `ResumeBullet` models (extend with `signals`, `confidence`)
- [ ] Wire into `AnalysisOrchestrator`
- [ ] Optional: `POST /analysis/resume` → `202` + `job_id` polling

**Done when:** `POST /api/analysis/resume/Darksharkthe1st/CodeRunner` returns SDK-generated bullets with evidence.

---

### Milestone 6 — Frontend polish

- [ ] Progress states (triage → scout → rabbit holes → synthesizing)
- [ ] Expandable evidence per bullet
- [ ] Signal tags on bullets

**Done when:** UI shows live analysis progress and evidence for each bullet.

---

## Implementation order (recommended)

1. **Milestones 1 + 3** on CodeRunner — validate SDK auth, cloud clone, scout prompt quality
2. **Milestone 2** — formalize triage before automating rabbit holes
3. **Milestone 4** — rabbit holes on signals scout recommends
4. **Milestones 5 + 6** — end-to-end API and UI

## What we keep from MVP

- GitHub OAuth + repo listing
- `findings.md` as scout's durable artifact
- `ResumeBullet` schema (extended later)
- Orchestrator parallel-per-repo pattern
