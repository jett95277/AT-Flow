from __future__ import annotations

import re


def validate_artifact_contract(agent: str, output_contract: str, artifact: str) -> list[str]:
    del agent
    required = _required_sections(output_contract)
    present = {_normalize_heading(section) for section in _artifact_sections(artifact)}
    return [section for section in required if _normalize_heading(section) not in present]


def validate_runtime_artifact_language(artifact: str, runtime_language: str) -> list[str]:
    if runtime_language != "en":
        return []
    violations: list[str] = []
    in_fence = False
    for line_number, raw_line in enumerate(artifact.splitlines(), start=1):
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and any("\u3400" <= character <= "\u9fff" for character in line):
            violations.append(f"line {line_number} contains CJK narrative")
    return violations


def _required_sections(output_contract: str) -> list[str]:
    sections: list[str] = []
    collecting = False
    for raw_line in output_contract.splitlines():
        line = raw_line.strip()
        if "with these sections" in line.lower():
            collecting = True
            continue
        if not collecting:
            continue
        if line.startswith("- "):
            sections.append(line[2:].strip())
        elif sections and line:
            break
    return sections


def _artifact_sections(artifact: str) -> list[str]:
    sections: list[str] = []
    for raw_line in artifact.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", raw_line.strip())
        if match:
            sections.append(match.group(1).strip())
    return sections


def _normalize_heading(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
