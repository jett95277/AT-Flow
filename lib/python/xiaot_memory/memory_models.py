"""三层记忆治理：枚举、字段校验与最小模型（纯数据层，不碰存储）。

- 定义 tier / scope / status / validity / kind 的允许值与枚举。
- 提供 uri 解析的权威实现（与 memory._parse_uri 逻辑一致）。
- 构造新格式 entry（make_entry）。
- 旧数据水合（hydrate_entry）：读取时补默认值副本，绝不改写原 dict、绝不写盘。
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from enum import Enum
from typing import Any

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_TIERS = ("short", "medium", "long")


class Tier(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class Scope(str, Enum):
    TASK = "task"
    PROJECT = "project"
    GLOBAL = "global"


class Status(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    VERIFIED = "verified"
    CONFLICTED = "conflicted"


class Validity(str, Enum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    DISCARDED = "discarded"


class Kind(str, Enum):
    CONCLUSION = "conclusion"
    CONSTRAINT = "constraint"
    UNRESOLVED = "unresolved"
    OBSERVATION = "observation"
    RISK = "risk"
    PROCESS = "process"
    PREFERENCE = "preference"
    RULE = "rule"
    FACT = "fact"


# 旧 status 到 validity 的映射：历史 archive/discard 置为 archived/discarded，
# 其余旧 status（candidate/active/verified）保留，validity 视为 current。
LEGACY_STATUS_TO_VALIDITY = {"archived": "archived", "deprecated": "discarded"}



def parse_uri(uri: str) -> tuple[str, str, str]:
    """解析 memory://<scope>/<name>/<tier> -> (scope, name, tier)。"""
    parts = uri.split("/")
    if len(parts) < 5:
        raise ValueError(f"invalid memory uri: {uri}")
    scope, name, tier = parts[2], parts[3], parts[4]
    if tier not in _TIERS:
        raise ValueError(f"unknown tier: {tier}")
    if not _SAFE_NAME.fullmatch(scope) or not _SAFE_NAME.fullmatch(name):
        raise ValueError(f"invalid memory uri: {uri}")
    return scope, name, tier


def derive_scope(uri: str, source: dict | None = None) -> str:
    """由 uri + source 推导作用域。

    session -> task（短期记忆归属当前 task）；task -> task；project -> project；
    global -> global。source 为空时 session 默认视为 task 作用域。
    """
    scope, _, _ = parse_uri(uri)
    if scope == "session":
        return "task"
    return scope


def derive_tier(uri: str) -> str:
    _, _, tier = parse_uri(uri)
    return tier


def new_entry_id() -> str:
    import uuid

    return f"mem-{uuid.uuid4().hex[:8]}"


def stable_id(uri: str, created_at: str, content: str) -> str:
    """旧条目水合时推导的稳定 id：同一条目多次水合 id 不变，事件可稳定关联。"""
    digest = hashlib.sha1(
        f"{uri}|{created_at}|{content}".encode("utf-8")
    ).hexdigest()[:8]
    return f"mem-{digest}"


def make_entry(
    uri: str,
    content: str,
    source: dict | None = None,
    *,
    status: str = "candidate",
    kind: str = "conclusion",
    constraints: list[str] | None = None,
    unresolved: list[str] | None = None,
    evidence: list[str] | None = None,
    task_id: str | None = None,
    supersedes_id: str | None = None,
) -> dict[str, Any]:
    """构造完整新格式 entry（新写入统一走这里，附加治理字段）。"""
    source = source or {}
    now = datetime.now(timezone.utc).isoformat()
    scope, _, tier = parse_uri(uri)
    # 旧 status（archived/deprecated）写入时同步 validity，其余新写默认 current。
    validity = LEGACY_STATUS_TO_VALIDITY.get(status, "current")
    return {
        "id": new_entry_id(),
        "uri": uri,
        "content": content,
        "constraints": list(constraints or []),
        "unresolved": list(unresolved or []),
        "kind": kind,
        "tier": tier,
        "scope": derive_scope(uri, source),
        "status": status,
        "validity": validity,
        "task_id": task_id or source.get("task"),
        "evidence": list(evidence or []),
        "supersedes_id": supersedes_id,
        "source": source,
        "created_at": now,
        "updated_at": now,
    }


def is_legacy(entry: dict[str, Any]) -> bool:
    """缺 tier/scope/validity/id 任一即视为历史数据（需水合补默认值）。"""
    return any(key not in entry for key in ("id", "tier", "scope", "validity"))


def hydrate_entry(entry: dict[str, Any], uri: str | None = None) -> dict[str, Any]:
    """返回带默认值的副本，绝不修改原 dict。旧数据在读取边界水合。"""
    out = dict(entry)
    uri = out.get("uri") or uri
    tier = out.get("tier")
    if not tier and uri:
        tier = derive_tier(uri)
    scope = out.get("scope")
    if not scope and uri:
        scope = derive_scope(uri, out.get("source"))
    status = out.get("status") or "candidate"
    validity = out.get("validity")
    if not validity:
        validity = LEGACY_STATUS_TO_VALIDITY.get(status, "current")
    created_at = out.get("created_at") or ""
    out.setdefault("id", stable_id(uri or "", created_at, out.get("content", "")))
    out.setdefault("content", "")
    out.setdefault("constraints", [])
    out.setdefault("unresolved", [])
    out.setdefault("kind", "conclusion")
    out["tier"] = tier or "short"
    out["scope"] = scope or "task"
    out["status"] = status
    out["validity"] = validity
    out.setdefault("task_id", (out.get("source") or {}).get("task"))
    out.setdefault("evidence", [])
    out.setdefault("supersedes_id", None)
    out.setdefault("source", {})
    out.setdefault("created_at", created_at or datetime.now(timezone.utc).isoformat())
    out.setdefault("updated_at", created_at)
    return out


