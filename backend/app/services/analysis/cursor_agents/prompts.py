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
    for item in commits[:50]:
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

## Required final response format

After writing the files, your **last message** must include both delimiter blocks below (copy the full file contents verbatim). This is mandatory for downstream parsing.

<<<LIGHTROOM_FINDINGS_MD>>>
(paste the complete contents of `.lightroom/findings.md` here)
<<<END_LIGHTROOM_FINDINGS_MD>>>

<<<LIGHTROOM_RABBIT_HOLES_JSON>>>
(paste the complete JSON array from `.lightroom/rabbit_holes.json` here)
<<<END_LIGHTROOM_RABBIT_HOLES_JSON>>>
"""


def build_rabbit_hole_prompt(
    *,
    owner: str,
    repo: str,
    username: str,
    branch: str,
    hole: dict[str, Any],
    findings_excerpt: str,
    commits: list[dict[str, Any]],
) -> str:
    signal_id = hole.get("signal_id", "unknown")
    display_name = hole.get("display_name", signal_id)
    rationale = hole.get("rationale", "")
    search_paths = hole.get("search_paths") or []
    confidence = hole.get("confidence", 0.0)

    paths_block = "\n".join(f"- `{p}`" for p in search_paths) or "- (none specified)"
    commit_lines = []
    for item in commits[:20]:
        sha = item.get("sha", "")[:7]
        msg = item.get("commit", {}).get("message", "").splitlines()[0]
        commit_lines.append(f"- {sha}: {msg}")
    commits_block = "\n".join(commit_lines) if commit_lines else "- (no matching commits)"

    return f"""You are a technical recruiter's research assistant doing a **deep dive** on one signal in `{owner}/{repo}`.

The authenticated user is **@{username}**. Your job is to gather file and commit evidence for a single recruiter-relevant technology area so we can write a strong resume bullet later.

## Branch
`{branch}`

## Signal under investigation
- **ID:** `{signal_id}`
- **Name:** {display_name}
- **Scout confidence:** {confidence}
- **Why investigate:** {rationale}

## Where to look (start here)
{paths_block}

## Scout findings (context)
{findings_excerpt}

## Relevant commits by @{username}
{commits_block}

## Your tasks

1. **Focus on the search paths above** — read the key files and trace how @{username} contributed.
2. **Cross-reference commits** — only attribute work supported by @{username}'s commits.
3. **Write one output file** at `.lightroom/signals/{signal_id}.md` (create directories as needed).

Use this structure:
```markdown
# Signal: {display_name}

## Summary
(2-3 sentences: what @{username} built, why it matters to recruiters)

## Technical depth
(architecture, patterns, scale — cite specific classes, functions, configs)

## Evidence

### Files
- `path/to/file` — what it shows

### Commits
- `abc1234`: commit message — what it demonstrates

## Resume bullet candidates
1. (third-person fragment, no "I", max 2 lines)
2. (optional second variant)

## Confidence
0.0-1.0 — how strong the evidence is for a resume bullet

## Gaps
(anything weak, stub-only, or not attributable to @{username})
```

## Rules
- Do **not** invent work not supported by files or commits.
- Cite **file paths** and **commit SHAs** as evidence.
- Stay within this signal — do not re-survey the entire repository.
- Do not open pull requests or modify application code — only create `.lightroom/signals/{signal_id}.md`.

## Required final response format

After writing the file, your **last message** must include the delimiter block below (copy the full file contents verbatim). This is mandatory for downstream parsing.

<<<LIGHTROOM_SIGNAL_MD>>>
(paste the complete contents of `.lightroom/signals/{signal_id}.md` here)
<<<END_LIGHTROOM_SIGNAL_MD>>>
"""
