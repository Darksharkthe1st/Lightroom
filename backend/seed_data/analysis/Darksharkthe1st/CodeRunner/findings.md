# Findings: Darksharkthe1st/CodeRunner

## Overview

CodeRunner is a full-stack, browser-based IDE that lets users write, compile, and execute code in Java, Python, and C inside isolated Docker containers. The frontend is deployed on Vercel (`https://code-runner-eta.vercel.app/`); the backend is exposed via Caddy at `api-coderunner.duckdns.org` and also configured for Fly.io deployment. The project targets developers and learners who want a LeetCode/HackerRank-style remote execution environment with an integrated AI debugging assistant.

The authenticated GitHub user **@Darksharkthe1st** is the sole contributor to this repository (116/116 commits). Commits appear under two author names—**Farhan Kittur** (104 commits) and **DarksharkThe1st** (12 commits)—both tied to `kitturfarhan@gmail.com`, indicating a single owner across local and GitHub identities.

## Stack

- **Java 21 + Spring Boot 4.0.1** — `pom.xml`, `src/main/java/com/cr/coderunner/`
- **React 19 + Vite 7** — `cr-frontend/package.json`, `cr-frontend/vite.config.js`, `cr-frontend/src/main.jsx`
- **Tailwind CSS 3** — `cr-frontend/tailwind.config.js`, `cr-frontend/postcss.config.js`
- **Monaco Editor** — `cr-frontend/src/components/CodeEditor.jsx`, `@monaco-editor/react` in `cr-frontend/package.json`
- **Docker / Docker-in-Docker** — `Dockerfile`, `docker-entrypoint.sh`, `docker/Dockerfile.gcc`, `CaddyDeployment/docker-compose.yml`
- **LangChain4j + Google Gemini 2.5 Flash** — `pom.xml` (langchain4j deps), `src/main/java/com/cr/coderunner/service/CodeHelperAssistant.java`, `LLMConfig.java`, `CodeExecutionTools.java`
- **Micrometer + Prometheus + Spring Actuator** — `pom.xml`, `src/main/java/com/cr/coderunner/CodeRunnerApplication.java` (`TimedAspect`), `@Timed` in `IDEController.java`, `configs/prometheus.yml`
- **Caddy reverse proxy** — `CaddyDeployment/Caddyfile`, `CaddyDeployment/docker-compose.yml`
- **Fly.io deployment** — `fly.toml`, `.github/workflows/fly-deploy.yml`
- **Maven** — `pom.xml`, `mvnw`
- **Python (benchmarking only)** — `metrics/benchmark.py`
- **Jenkins (minimal stub)** — `Jenkinsfile`
- **MongoDB (declared, not implemented)** — `pom.xml` includes `spring-boot-starter-data-mongodb`; `DataConfig.java` is fully commented out; README notes planned SQL migration

## Architecture

CodeRunner follows a **React SPA → Spring Boot REST API → Docker sandbox** pattern with an optional **LangChain4j agent** layer.

```
Browser (React/Vite on Vercel)
    │  POST /submit, POST /check (500ms polling)
    │  POST /llm/message (AI chat)
    ▼
Spring Boot API (Java 21, port 8080)
    ├── CodeExecutionService — 10-worker ExecutorService + ConcurrentHashMap UUID tracking
    ├── CodeSubmission — spawns per-language Docker containers (Python/Java/C)
    ├── CodeHelperAssistant (@AiService) — Gemini agent with system prompt
    └── CodeExecutionTools (@Tool) — agent can autonomously submit code to the same queue
    ▼
Docker-in-Docker (docker:24-dind)
    ├── python:3.12-alpine
    ├── eclipse-temurin:21-alpine
    └── coderunner-gcc:latest (custom image from docker/Dockerfile.gcc)
```

**Execution flow:** Frontend submits code → backend returns UUID immediately → frontend polls `/check` every 500ms → worker thread runs code in an isolated container → results returned as `RunResult` (RUNNING/FINISHED/NONEXISTENT). A `@Scheduled` task cleans stale executions every 30 seconds.

**AI flow:** User sends chat + code context → `LLMController` → `GeminiService` → `CodeHelperAssistant.chat()` → agent may invoke `CodeExecutionTools.executeCode()` to test hypotheses → markdown response rendered via `react-markdown` in `ChatInterface.jsx`.

**Deployment:** Production uses Docker-in-Docker with Caddy TLS termination (`CaddyDeployment/`). GitHub Actions deploys to Fly.io on push to `main`. Frontend hosted separately on Vercel with CORS configured in `WebConfig.java`.

## User contributions (@Darksharkthe1st)

@Darksharkthe1st authored **all 116 commits** and appears to be the project's sole developer (Farhan Kittur / DarksharkThe1st, same email). Major ownership areas:

| Area | Evidence | Key commits |
|------|----------|-------------|
| **Async execution queue** | `CodeExecutionService.java` (5 commits), `IDEController.java` | "Create CodeExecutionService class", "Switch from submit directly to submit + polling strategy", "Add working timeouts to execution queue", "Clean up code, add hashmap concurrency" |
| **Docker sandbox engine** | `CodeSubmission.java` (29 commits), `Dockerfile`, `docker-entrypoint.sh` | "Refactor docker cmds for use in newer machine", "Returned to Docker-in-Docker", "Update benchmarks, speed up gcc docker image" |
| **AI / LLM integration** | `ChatInterface.jsx`, `GeminiService.java`, `CodeHelperAssistant.java`, `CodeExecutionTools.java` | "Add gemini API code", "Connect basic Gemini backend to frontend", "Add agent tooling, fix throw catching errors, add LLM context limits", "Implement multi-message chats, code/err/result contexts" |
| **React frontend** | `App.jsx` (25 commits), UI components | "Add CodeHelper tab", "Make I/O windows draggable", "Hoist chatMessages to App", "Use react-markdown to display LLM markdown output" |
| **Observability & metering** | `pom.xml` (micrometer), `@Timed` annotations, `configs/prometheus.yml` | "Add micrometer and spring-aop dependencies", "Fix dependency issues, add Timed monitors", "Edit configs for prometheus on ubuntu" |
| **Deployment & infra** | `CaddyDeployment/`, `fly.toml`, `.github/workflows/fly-deploy.yml` | "Add Caddy configuration files for deployment", "Update README with live access link" |
| **Safety & abuse protection** | Output truncation in `CodeSubmission.java`, `Terminal.jsx` | "Add massive outputs protections and fix error handling bugs" |
| **Benchmarking** | `metrics/benchmark.py` | "Update benchmarks, speed up gcc docker image" |
| **CORS & API wiring** | `WebConfig.java` | "Fix CORS Policy for Server", "Modify properties and webconfig to avoid duplicate CORS policy", "successfully connected backend to frontend!" |

**Commit themes:** Full-stack ownership from initial Docker wiring through production deployment, a major architectural pivot from synchronous to async queue-based execution, end-to-end LLM agent integration with tool calling, and operational hardening (timeouts, output limits, observability, benchmarks).

## Recruiter signals

| Signal | Confidence | Verdict | Evidence paths |
|--------|------------|---------|----------------|
| React | 0.95 | **Confirmed** | `cr-frontend/`, `cr-frontend/package.json`, `cr-frontend/src/App.jsx`, `cr-frontend/src/components/*.jsx` |
| Spring Boot | 0.95 | **Confirmed** | `pom.xml`, `src/main/java/com/cr/coderunner/CodeRunnerApplication.java` |
| Docker | 0.95 | **Confirmed** | `Dockerfile`, `docker-entrypoint.sh`, `docker/Dockerfile.gcc`, `src/main/java/com/cr/coderunner/model/CodeSubmission.java` |
| Java | 0.95 | **Confirmed** | `pom.xml` (`java.version=21`), `src/main/java/**/*.java` |
| Observability | 0.85 | **Confirmed** | `pom.xml` (micrometer-registry-prometheus), `configs/prometheus.yml`, `@Timed` in `IDEController.java`, `CodeRunnerApplication.java` (`TimedAspect`) |
| CI/CD | 0.70 | **Confirmed (lightweight)** | `.github/workflows/fly-deploy.yml`, `Jenkinsfile` (build-only stub), `fly.toml` |
| Testing | 0.45 | **Partial — stubs only** | `src/test/java/com/cr/coderunner/` — `CodeRunnerApplicationTests.java` (context load only), `ProblemControllerTest.java` (empty test body) |
| Python | 0.55 | **Confirmed (benchmarking only)** | `metrics/benchmark.py` — not used in application runtime |
| AI / LLM | 0.90 | **Confirmed** | `CodeHelperAssistant.java`, `CodeExecutionTools.java`, `LLMConfig.java`, `LLMController.java`, `cr-frontend/src/components/ChatInterface.jsx` |
| API design | 0.85 | **Confirmed** | `IDEController.java`, `LLMController.java`, `ProblemController.java`, `HealthController.java` |
| LangChain4j agents | 0.90 | **Additional — strong** | `@AiService` in `CodeHelperAssistant.java`, `@Tool` in `CodeExecutionTools.java`, `pom.xml` |
| Concurrency / async patterns | 0.90 | **Additional — strong** | `CodeExecutionService.java` (ExecutorService, ConcurrentHashMap, `@Scheduled` cleanup) |
| Monaco Editor | 0.85 | **Additional** | `cr-frontend/src/components/CodeEditor.jsx`, `cr-frontend/src/themes/monacoTheme.js` |
| Tailwind CSS | 0.85 | **Additional** | `cr-frontend/tailwind.config.js`, utility classes throughout components |
| Docker-in-Docker | 0.85 | **Additional** | `Dockerfile` (`FROM docker:24-dind`), `CaddyDeployment/docker-compose.yml` (`privileged: true`) |
| Reverse proxy / TLS | 0.80 | **Additional** | `CaddyDeployment/Caddyfile`, `CaddyDeployment/docker-compose.yml` |
| Cloud deployment (Fly.io, Vercel) | 0.80 | **Additional** | `fly.toml`, `.github/workflows/fly-deploy.yml`, `WebConfig.java` (Vercel origin), `README.md` |
| Security / sandboxing | 0.80 | **Additional** | Docker isolation in `CodeSubmission.java`, 10s timeout (`TIME_LIMIT_SECS`), 1MB output cap, frontend 500KB cap in `Terminal.jsx` |
| MongoDB | 0.20 | **Rejected (dependency only)** | `pom.xml` declares it; no active repository/entity usage; `DataConfig.java` commented out |
| Jenkins CI | 0.30 | **Rejected (stub)** | `Jenkinsfile` — single `mvn --version` stage only |

## Notes

- **Resume-ready metrics exist:** `metrics/benchmark.py` produces quantified latency, concurrency speedup, queue saturation throughput, timeout enforcement, and Docker overhead numbers against the live deployment — strong material for impact-oriented bullets.
- **Sole ownership:** 116/116 commits from one developer demonstrates end-to-end full-stack capability (frontend, backend, infra, AI, DevOps).
- **Architectural evolution:** README documents a deliberate migration from synchronous blocking execution to an async UUID-polling queue with a 10-worker thread pool — shows systems design thinking.
- **AI agent with tool use:** The LangChain4j `@Tool` integration letting Gemini autonomously execute test code is a differentiator beyond basic chatbot wrappers.
- **Production deployment:** Live frontend (Vercel) + backend (DuckDNS/Caddy) with documented benchmark targets indicates the project ships, not just prototypes.
- **Gaps to acknowledge:** Test coverage is minimal (stub tests), MongoDB is declared but unused, and Jenkins CI is a placeholder. These are honest limits, not strengths.