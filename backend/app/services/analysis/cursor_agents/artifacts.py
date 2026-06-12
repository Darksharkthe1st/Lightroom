"""Parse scout output from SDK artifacts, delimiters, and fallback heuristics."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any

FINDINGS_DELIM_START = "<<<LIGHTROOM_FINDINGS_MD>>>"
FINDINGS_DELIM_END = "<<<END_LIGHTROOM_FINDINGS_MD>>>"
RABBIT_DELIM_START = "<<<LIGHTROOM_RABBIT_HOLES_JSON>>>"
RABBIT_DELIM_END = "<<<END_LIGHTROOM_RABBIT_HOLES_JSON>>>"


def parse_scout_output(
    text: str,
    artifacts: dict[str, str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    artifacts = artifacts or {}

    findings = (
        _from_delimiter(text, FINDINGS_DELIM_START, FINDINGS_DELIM_END)
        or _artifact_by_basename(artifacts, "findings.md")
        or _extract_legacy_artifact(text, "findings.md")
        or _extract_markdown_block(text)
    )

    rabbit_raw = (
        _from_delimiter(text, RABBIT_DELIM_START, RABBIT_DELIM_END)
        or _artifact_by_basename(artifacts, "rabbit_holes.json")
        or _extract_legacy_artifact(text, "rabbit_holes.json")
    )

    if not findings:
        findings = _strip_delimiters(text).strip()

    rabbit_holes = _parse_rabbit_holes(rabbit_raw, text)
    return findings.strip(), rabbit_holes


def _parse_rabbit_holes(rabbit_raw: str | None, text: str) -> list[dict[str, Any]]:
    if rabbit_raw:
        parsed = _loads_json_array(rabbit_raw.strip())
        if parsed:
            return parsed
    return _extract_json_array(text)


def _from_delimiter(text: str, start: str, end: str) -> str | None:
    if start not in text or end not in text:
        return None
    begin = text.index(start) + len(start)
    stop = text.index(end, begin)
    content = text[begin:stop].strip()
    return content or None


def _artifact_by_basename(artifacts: dict[str, str], basename: str) -> str | None:
    for path, content in artifacts.items():
        if PurePosixPath(path).name == basename and content.strip():
            return content.strip()
    return None


def _extract_legacy_artifact(text: str, filename: str) -> str | None:
    pattern = rf"--- artifact:.*?{re.escape(filename)}.*?---\n(.*?)(?=\n--- artifact:|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_markdown_block(text: str) -> str | None:
    if "# Findings:" not in text:
        return None
    start = text.index("# Findings:")
    chunk = text[start:].split("--- artifact:")[0]
    chunk = chunk.split(FINDINGS_DELIM_START)[0]
    return chunk.strip() or None


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    if RABBIT_DELIM_START in text:
        text = text.split(RABBIT_DELIM_START, 1)[0]
    match = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if not match:
        return []
    return _loads_json_array(match.group(0)) or []


def _loads_json_array(raw: str) -> list[dict[str, Any]] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return None


def _strip_delimiters(text: str) -> str:
    for marker in (
        FINDINGS_DELIM_START,
        FINDINGS_DELIM_END,
        RABBIT_DELIM_START,
        RABBIT_DELIM_END,
    ):
        text = text.replace(marker, "")
    return text
