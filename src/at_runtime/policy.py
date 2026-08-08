from __future__ import annotations

from typing import Any


def can_read(policies: dict[str, Any], role: str, resource: str) -> bool:
    return resource in policies.get("roles", {}).get(role, {}).get("read", [])


def can_write(policies: dict[str, Any], role: str, resource: str) -> bool:
    return resource in policies.get("roles", {}).get(role, {}).get("write", [])
