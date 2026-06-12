# Signal: Docker sandbox + async execution queue

## Summary

@Darksharkthe1st built CodeRunner’s core remote-execution engine: user code runs inside per-job Docker containers (Java, Python, C) while a Spring Boot async queue accepts submissions immediately and returns results via UUID polling. The system combines a 10-worker `ExecutorService`, `ConcurrentHashMap` job tracking, scheduled eviction, and a Docker-in-Docker production image with a Python benchmark suite to measure latency, concurrency speedup, queue saturation, and timeout enforcement on the live deployment.

## Technical depth

**Async submit + poll API.** `IDEController` exposes `POST /submit` (returns a UUID) and `POST /check` (returns `RunResult` with status `RUNNING`, `FINISHED`, or `NONEXISTENT`). A debug endpoint `GET /check_queue` lists in-flight jobs. Micrometer `@Timed` annotations instrument submit/check latency.

**Execution queue (`CodeExecutionService`).** A fixed 10-thread pool (`Executors.newFixedThreadPool(10)`) submits `CodeExecution` workers (which extend `Thread`). Each job gets a UUID stored in a `ConcurrentHashMap<String, CodeExecution>`. `checkExecution()` returns partial state while running and removes finished jobs on poll. `@Scheduled(fixedRate = 30_000)` runs `cleanExecutions()` to drop entries whose `completedAt` timestamp is older than 60 seconds. `@EnableScheduling` is wired in `CodeRunnerApplication`.

**Docker sandbox (`CodeSubmission`).** For each run, the service writes code and stdin to temp files under `.test/`, bind-mounts the directory into a named container (`docker run --name <dir> --rm -v <host>:/sandbox …`), and executes language-specific commands:
- **C:** `coderunner-gcc:latest` — compile with `gcc` and run `./sandbox/main`
- **Python:** `python:3.12-alpine` — `python3 sandbox/code.py < input`
- **Java:** `eclipse-temurin:21-alpine` — `java sandbox/code.java < input`

Safety controls include a 10-second process wait (`TIME_LIMIT_SECS = 10`), forced container removal via `docker rm -f`, concurrent stdout/stderr reader threads, and 1 MB output/error truncation. Temp directories are cleaned with `FileUtils.cleanDirectory()` after each run.

**Production Docker-in-Docker.** The root `Dockerfile` uses `docker:24-dind` in a multi-stage build (Maven compile + JRE runtime). `docker-entrypoint.sh` starts `dockerd`, waits up to 60 s for readiness, pre-pulls `eclipse-temurin:21-alpine`, `python:3.12-alpine`, and `alpine:latest`, then launches the Spring Boot JAR. A custom `docker/Dockerfile.gcc` pre-installs `gcc`/`musl-dev` so C runs skip per-container `apk add` overhead.

**Benchmarking (`metrics/benchmark.py`).** Five benchmarks against the live API (`https://api-coderunner.duckdns.org` by default): per-language Hello World latency (5 trials), 10-worker concurrent throughput vs sequential baseline, 15-job queue saturation (1.5× pool capacity), infinite-loop timeout enforcement (10 s limit), and Docker spin-up overhead (wall time minus server `runtime`). The script prints a resume-ready metrics summary when executed.

## Evidence

### Files

- `src/main/java/com/cr/coderunner/service/CodeExecutionService.java` — 10-worker `ExecutorService`, UUID assignment, `ConcurrentHashMap` result store, `checkExecution()` status machine, `@Scheduled` cleanup every 30 s
- `src/main/java/com/cr/coderunner/model/CodeSubmission.java` — Docker command builder for Java/Python/C, temp-file sandbox setup, 10 s timeout, async I/O capture, forced container teardown, 1 MB output caps (29 commits; primary sandbox engine)
- `src/main/java/com/cr/coderunner/model/CodeExecution.java` — `Thread` worker wrapping `CodeSubmission.run()`, `done`/`completedAt` flags, `isExpired()` for 60 s post-completion eviction
- `src/main/java/com/cr/coderunner/controller/IDEController.java` — `/submit`, `/check`, `/check_queue`, `/pull` endpoints wiring the queue and Docker image pre-pull
- `src/main/java/com/cr/coderunner/dto/RunResult.java` — DTO serializing `RUNNING` / `FINISHED` / `NONEXISTENT` poll responses
- `src/main/java/com/cr/coderunner/CodeRunnerApplication.java` — `@EnableScheduling` for queue cleanup
- `Dockerfile` — multi-stage `docker:24-dind` build embedding Java 21 Spring Boot app inside DinD runtime
- `docker-entrypoint.sh` — daemon startup, readiness polling, image pre-pull, JAR launch
- `docker/Dockerfile.gcc` — pre-baked Alpine GCC image (`coderunner-gcc:latest`) to reduce C execution cold-start
- `metrics/benchmark.py` — end-to-end benchmark suite for latency, concurrency speedup, queue saturation, timeout enforcement, and Docker overhead

### Commits

- `e5ab497`: Begin basic code running with Docker and gcc, not functional yet — first Docker-based execution path in `CodeSubmission.java`
- `42ac490`: Add waiting for docker closure, switch from blanket throws to try-catches — reliable container teardown and error handling in sandbox runs
- `767e93a`: Add multi-language docker support (python added) — extended sandbox to Python alongside C/Java
- `2432e04`: Rewrote docker entrypoint and docker file to switch to simple docker out of docker implementation — initial DinD/DoD containerization of the backend
- `09f68bb`: Returned to Docker-in-Docker to fix mounting issues — reverted to full DinD after volume-mount failures on newer hosts
- `ba54064`: add pull api, switch to alpine images, try fly.io implementation — Alpine language images, `/pull` endpoint, production container hardening
- `5bc3d9c`: Refactor docker cmds for use in newer machine — Docker command updates for deployment target compatibility
- `7459751`: Add problems API/controller, make code/input files temporary — temp-file execution model foundation
- `0a3c494`: Create CodeExecutionService class — introduced async queue service with 10-thread pool and UUID map
- `62d57db`: Switch from submit directly to submit + polling strategy — `/submit` + `/check` polling API and `RunResult` status field
- `d5d9e62`: Add working timeouts to execution queue — `RunResult` status codes, `@Scheduled` cleanup, `isExpired()` lifecycle, `/check_queue`
- `046281d`: Clean up code, add hashmap concurrency — migrated result store from `HashMap` to `ConcurrentHashMap` for thread-safe polling
- `e712156`: Add massive outputs protections and fix error handling bugs — 1 MB stdout/stderr truncation and run lifecycle hardening
- `2093e8e`: Update benchmarks, speed up gcc docker image — added `metrics/benchmark.py`, `docker/Dockerfile.gcc`, switched C runs to pre-built `coderunner-gcc:latest`, aligned process timeout to 10 s constant

## Resume bullet candidates

1. Built a Docker-sandboxed remote code runner (Java/Python/C) with per-job container isolation, 10 s execution limits, and a Spring Boot async queue using a 10-worker thread pool, UUID polling, and scheduled cleanup—validated by a Python benchmark suite measuring latency, concurrency speedup, and queue saturation on production.

2. Designed and deployed a Docker-in-Docker execution backend: multi-stage `docker:24-dind` image, daemon bootstrap with image pre-pull, custom GCC sandbox image, and submit/poll REST API backed by `ConcurrentHashMap` job tracking for concurrent browser IDE workloads.

## Confidence

0.94 — Strong, multi-file evidence across 29 `CodeSubmission.java` commits, 5 `CodeExecutionService.java` commits, DinD production artifacts, and a dedicated benchmark script. Slightly below 0.95 because live benchmark numbers are produced at runtime and are not checked into the repo, and Docker resource limits (`--memory`, `--cpus`) exist in history but are commented out in current code.

## Gaps

- **No committed benchmark output:** `metrics/benchmark.py` defines and prints metrics, but actual latency/speedup numbers require running against the live API; none are stored in the repository.
- **Resource limits disabled:** `--pids-limit`, `--memory=256m`, and `--cpus=0.5` appear in commit history (`4150794`) but are commented out in the current `getCommandByFiles()` implementation.
- **Early Docker work was incremental:** commit `e5ab497` explicitly notes Docker+gcc was “not functional yet”; the full sandbox/queue story matured across many follow-up commits through Feb–May 2026.
- **README drift:** README Docker examples still show inline `apk add gcc` for C, while production code uses the pre-built `coderunner-gcc:latest` image from `2093e8e`.