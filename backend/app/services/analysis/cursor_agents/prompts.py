from __future__ import annotations

import json
from typing import Any


def build_scout_prompt(
    *,
    owner: str,
    repo: str,
    username: str,
    branch: str,
    triage: dict[str, Any],
    commits: list[dict[str, Any]],
) -> str:
    commit_lines = []
    for item in commits[:30]:
        sha = item.get("sha", "")[:7]
        msg = item.get("commit", {}).get("message", "").splitlines()[0]
        commit_lines.append(f"- {sha}: {msg}")
    commits_block = "\n".join(commit_lines) if commit_lines else "- (no commits by this user)"

    triage_json = json.dumps(triage, indent=2)

    return f"""You are a technical recruiter's research assistant analyzing the GitHub repository `{owner}/{repo}`.

The authenticated user is **@{username}**. Analyze what they contributed and what technologies would impress a software engineering recruiter.

## Branch
`{branch}`

## Pre-triage signals (heuristic — confirm or reject with evidence)
```json
{triage_json}
```

## Recent commits by @{username}
{commits_block}

## Your tasks

1. **Browse the repository** — understand purpose, architecture, and stack.
2. **Confirm or reject** each triage signal with file-path evidence.
3. **Identify additional recruiter-relevant signals** (languages, frameworks, cloud/infra, data stores, CI/CD, testing, security, scale patterns).
4. **Assess @{username}'s contributions** — what areas did their commits touch?
5. **Write two output files** in a `.lightroom/` directory at the repo root (create the directory):

### `.lightroom/findings.md`
Use this structure:
```markdown
# Findings: {owner}/{repo}

## Overview
(1-2 paragraphs: what the project does, who it serves)

## Stack
(bullet list of technologies with evidence paths)

## Architecture
(how components fit together)

## User contributions (@{username})
(what they built, themes from commits, areas of ownership)

## Recruiter signals
(table or bullets: signal | confidence 0-1 | evidence paths)

## Notes
(anything else resume-worthy)
```

### `.lightroom/rabbit_holes.json`
JSON array of deep-dive recommendations. Only include signals where there is **enough code and/or commits** to produce a strong resume bullet.

```json
[
  {{
    "signal_id": "docker",
    "display_name": "Docker / containerization",
    "rationale": "why this is worth a deep dive",
    "search_paths": ["docker/", "Dockerfile"],
    "priority": 1,
    "confidence": 0.85
  }}
]
```

`priority` is 1 (highest) to 5 (lowest). Max 5 rabbit holes.

## Rules
- Do **not** invent work not supported by the repository or commits.
- Cite **file paths** as evidence.
- Focus on what SWE recruiters scan for: languages, frameworks, cloud, data, CI/CD, testing, system design.
- Do not open pull requests or modify application code — only create `.lightroom/findings.md` and `.lightroom/rabbit_holes.json`.
"""
