"""三层记忆治理：准入、准出与状态转换规则（纯代码 + 受信写入 facade）。

- check_* 为纯函数：只吃 dict 和参数，不读不写存储，非法即抛 MemoryPolicyError。
- request_* 为受信写入：校验后回调 memory.py 机械函数落盘，并记录审计事件。
- 任何 Skill / Agent 都不得直接绕过本模块修改正式记忆。

错误码（稳定）：
  SHORT_REQUIRES_TASK / SHORT_KIND_NOT_ALLOWED / MEDIUM_REQUIRES_SHORT /
  LONG_NO_DIRECT_TECH_FACT / NOT_VERIFIED / NOT_CURRENT / NOT_VERIFIABLE /
  MEDIUM_REQUIRES_EVIDENCE / MEDIUM_REQUIRES_DISTILLED / LONG_REQUIRES_EVIDENCE /
  VERIFY_REQUIRES_EVIDENCE / REQUIRES_CONFIRMATION / SUPERSEDE_SCOPE_MISMATCH
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xiaot_memory.memory import (
    _resolve_index,
    _save_entries,
    archive_memory,
    discard_memory,
    mark_conflicted,
    memory_path,
    promote_memory,
    read_memory,
    supersede_memory,
    verify_memory,
    write_memory,
)
from xiaot_memory.memory_events import log_action
from xiaot_memory.memory_models import (
    derive_scope,
    is_legacy,
    make_entry,
    parse_uri,
    stable_id,
)

_SHORT_KINDS = {"conclusion", "observation", "risk", "unresolved"}
_LONG_PREFERENCE_KINDS = {"preference", "rule"}


class MemoryPolicyError(ValueError):
    """记忆治理拒绝结果：稳定错误码 + 人类可读原因（子类 ValueError，CLI 可复用现有处理）。"""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"[{code}] {reason}")
        self.code = code
        self.reason = reason


def check_admission(
    uri: str,
    content: str,
    source: dict | None = None,
    *,
    kind: str = "conclusion",
    status: str = "candidate",
    task_id: str | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    """校验直接写入的准入条件（create 路径）。返回规范化字段或抛 MemoryPolicyError。"""
    source = source or {}
    scope_name, _, tier = parse_uri(uri)
    scope = derive_scope(uri, source)
    if tier == "short":
        tid = task_id or source.get("task")
        if not tid:
            raise MemoryPolicyError(
                "SHORT_REQUIRES_TASK", "short 记忆必须绑定 task_id（--task）"
            )
        if kind not in _SHORT_KINDS:
            raise MemoryPolicyError(
                "SHORT_KIND_NOT_ALLOWED",
                f"short 允许 kind 为 {sorted(_SHORT_KINDS)}，收到 {kind!r}",
            )
    elif tier == "medium":
        # 直接写 medium 的三个例外；普通记忆必须来自 short（走 promote）。
        if scope == "task" and kind == "conclusion":
            pass  # 任务定义入口（目标/范围/验收），用户发起即视为已确认
        elif scope == "project" and kind == "constraint" and confirmed:
            pass  # 用户明确声明的项目级约束
        elif scope == "global" and kind == "preference" and status == "candidate":
            pass  # Agent 推断的长期偏好，待用户确认
        else:
            raise MemoryPolicyError(
                "MEDIUM_REQUIRES_SHORT",
                "普通 medium 记忆必须来自 short 晋升（或项目约束/长期偏好例外）",
            )
    elif tier == "long":
        # 唯一直接写入例外：用户明确表达的长期偏好/规则。
        if scope == "global" and kind in _LONG_PREFERENCE_KINDS and confirmed:
            pass
        else:
            raise MemoryPolicyError(
                "LONG_NO_DIRECT_TECH_FACT",
                "普通技术事实不能直接写 long（需从 verified medium 晋升）",
            )
    return {
        "tier": tier,
        "scope": scope,
        "kind": kind,
        "status": status,
        "validity": "current",
        "task_id": task_id or source.get("task"),
    }


def _combined_evidence(entry: dict[str, Any], evidence: list[str] | None) -> list[str]:
    """合并「本次传入证据 + 条目已存证据」，供晋升/验证校验。"""
    stored = [e for e in (entry.get("evidence") or []) if e]
    return list(dict.fromkeys(list(evidence or []) + stored))


def check_transition(
    entry: dict[str, Any],
    action: str,
    *,
    confirmed: bool = False,
    evidence: list[str] | None = None,
    distilled: str | None = None,
) -> None:
    """校验状态转换（entry 为原始条目，未水合）。不通过抛 MemoryPolicyError。"""
    legacy = is_legacy(entry)
    content = entry.get("content") or ""
    if action == "verify":
        if entry.get("status") not in ("candidate", "active"):
            raise MemoryPolicyError(
                "NOT_VERIFIABLE", f"status={entry.get('status')!r} 不可 verify"
            )
        if not evidence and not confirmed and not legacy:
            raise MemoryPolicyError(
                "VERIFY_REQUIRES_EVIDENCE", "verify 需证据或用户确认"
            )
        return
    if action == "promote_medium":
        if entry.get("status") not in ("verified",) and not confirmed:
            raise MemoryPolicyError("NOT_VERIFIED", "medium 晋升需 status=verified 或用户确认")
        if legacy:
            if not confirmed:
                raise MemoryPolicyError(
                    "REQUIRES_CONFIRMATION", "legacy 条目晋升需用户确认补证"
                )
        elif not _combined_evidence(entry, evidence):
            raise MemoryPolicyError("MEDIUM_REQUIRES_EVIDENCE", "medium 晋升至少需要一种证据")
        if not distilled:
            raise MemoryPolicyError("MEDIUM_REQUIRES_DISTILLED", "medium 晋升必须重新提炼（distilled）")
        if distilled.strip() == content.strip():
            raise MemoryPolicyError(
                "MEDIUM_REQUIRES_DISTILLED", "禁止复制 short 原文，必须重新提炼"
            )
        if not confirmed:
            raise MemoryPolicyError("REQUIRES_CONFIRMATION", "medium 晋升需用户确认")
        return
    if action == "promote_long":
        if entry.get("status") != "verified":
            raise MemoryPolicyError("NOT_VERIFIED", "long 晋升需来源 status=verified")
        if entry.get("validity") not in (None, "current"):
            raise MemoryPolicyError("NOT_CURRENT", "long 晋升需 validity=current")
        if not confirmed:
            raise MemoryPolicyError("REQUIRES_CONFIRMATION", "long 晋升需用户确认")
        if not legacy and not _combined_evidence(entry, evidence):
            raise MemoryPolicyError("LONG_REQUIRES_EVIDENCE", "long 晋升需证据")
        return
    if action == "archive":
        if entry.get("validity") == "discarded":
            raise MemoryPolicyError("ALREADY_DISCARDED", "discarded 记录不可再归档")
        return
    if action == "discard":
        if not confirmed:
            raise MemoryPolicyError("REQUIRES_CONFIRMATION", "discard 必须用户确认")
        return
    if action == "conflict":
        if not confirmed:
            raise MemoryPolicyError("REQUIRES_CONFIRMATION", "标记 conflicted 必须用户确认")
        return
    if action == "supersede":
        if not confirmed:
            raise MemoryPolicyError("REQUIRES_CONFIRMATION", "supersede 必须用户确认")
        return
    raise MemoryPolicyError("UNKNOWN_ACTION", f"unknown action: {action!r}")


def _rewrite_promoted(root: Path, promoted: dict[str, Any], distilled: str | None,
                      evidence: list[str] | None) -> dict[str, Any]:
    """晋升后将提炼文本与证据写回目标条目（promote_memory 机械移动后补写）。"""
    if not distilled and not evidence:
        return promoted
    uri = promoted["uri"]
    path = memory_path(root, uri)
    if not path.exists():
        return promoted
    entries = _load_raw(root, uri)
    for e in entries:
        if e.get("created_at") == promoted.get("created_at"):
            if distilled:
                e["content"] = distilled
            if evidence:
                e["evidence"] = list(evidence)
            e["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_entries(path, entries)
            return e
    return promoted


def _load_raw(root: Path, uri: str) -> list[dict[str, Any]]:
    return read_memory(root, uri)


def write_entry(
    root: Path,
    uri: str,
    content: str,
    source: dict | None = None,
    *,
    kind: str = "conclusion",
    status: str = "candidate",
    task_id: str | None = None,
    evidence: list[str] | None = None,
    confirmed: bool = False,
    supersedes_uri: str | None = None,
    supersedes_index: int = -1,
    constraints: list[str] | None = None,
    unresolved: list[str] | None = None,
    actor: str = "user",
    reason: str = "",
) -> dict[str, Any]:
    """受信写入（create 路径）：check_admission → 落盘 → 审计事件。

    提供 supersedes_uri 时，先写新条目（记录 supersedes_id），再置旧条目为 superseded。
    """
    normalized = check_admission(
        uri, content, source, kind=kind, status=status,
        task_id=task_id, confirmed=confirmed,
    )
    source = source or {}
    supersedes_id = None
    if supersedes_uri:
        old = read_memory(root, supersedes_uri)
        if not old:
            raise FileNotFoundError(f"unknown supersedes target: {supersedes_uri}")
        old_entry = old[_resolve_index(old, supersedes_index)]
        supersedes_id = old_entry.get("id") or stable_id(
            supersedes_uri, old_entry.get("created_at", ""), old_entry.get("content", "")
        )
        check_transition(old_entry, "supersede", confirmed=True)
    item = make_entry(
        uri, content, source, status=status, kind=normalized["kind"],
        evidence=evidence, task_id=task_id or source.get("task"),
        supersedes_id=supersedes_id,
        constraints=constraints, unresolved=unresolved,
    )
    path = memory_path(root, uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = _load_raw(root, uri)
    entries.append(item)
    _save_entries(path, entries)
    log_action(root, "create", item["id"], from_tier=None, to_tier=item["tier"],
               actor=actor, reason=reason or "admitted", data={"uri": uri})
    if supersedes_uri:
        supersede_memory(root, supersedes_uri, index=supersedes_index,
                         supersedes_id=item["id"], confirmed=True)
        log_action(root, "supersede", supersedes_id, actor=actor,
                   reason=f"replaced by {item['id']}", data={"uri": supersedes_uri})
    return item


def request_verify(
    root: Path, uri: str, *, index: int = -1, evidence: list[str] | None = None,
    confirmed: bool = False, actor: str = "user", reason: str = "",
) -> dict[str, Any]:
    entries = _load_raw(root, uri)
    if not entries:
        raise FileNotFoundError(f"unknown memory: {uri}")
    entry = entries[_resolve_index(entries, index)]
    check_transition(entry, "verify", confirmed=confirmed, evidence=evidence)
    result = verify_memory(root, uri, index=index, evidence=evidence)
    log_action(root, "verify", result.get("id"), from_tier=result.get("tier"),
               actor=actor, reason=reason or "verified", data={"uri": uri})
    return result


def request_promote(
    root: Path, uri: str, to_tier: str, *, index: int = -1, all_: bool = False,
    confirmed: bool = False, evidence: list[str] | None = None,
    distilled: str | None = None, actor: str = "user", reason: str = "",
) -> dict[str, Any]:
    if to_tier not in ("medium", "long"):
        raise MemoryPolicyError("UNKNOWN_TIER", f"unknown promote target: {to_tier!r}")
    entries = _load_raw(root, uri)
    if not entries:
        raise FileNotFoundError(f"unknown memory: {uri}")
    targets = entries if all_ else [entries[_resolve_index(entries, index)]]
    action = f"promote_{to_tier}"
    for entry in targets:
        check_transition(entry, action, confirmed=confirmed,
                         evidence=evidence, distilled=distilled)
    result = promote_memory(root, uri, to_tier=to_tier, index=index, all_=all_)
    combined = _combined_evidence(targets[-1], evidence)
    promoted = _rewrite_promoted(root, result, distilled, combined)
    log_action(root, "promote", promoted.get("id"), from_tier="short" if to_tier == "medium" else "medium",
               to_tier=to_tier, actor=actor, reason=reason or "promoted",
               data={"uri": uri, "target_uri": promoted.get("uri")})
    return promoted


def request_supersede(
    root: Path, uri: str, index: int = -1, *, replaces_uri: str,
    replaces_index: int = -1, confirmed: bool = False,
    actor: str = "user", reason: str = "",
) -> dict[str, Any]:
    if not confirmed:
        raise MemoryPolicyError("REQUIRES_CONFIRMATION", "supersede 必须用户确认")
    src_scope, _, src_tier = parse_uri(uri)
    dst_scope, _, dst_tier = parse_uri(replaces_uri)
    if src_scope != dst_scope or src_tier != dst_tier:
        raise MemoryPolicyError(
            "SUPERSEDE_SCOPE_MISMATCH",
            f"supersede 需同 scope 同 tier：{uri} vs {replaces_uri}",
        )
    old = _load_raw(root, replaces_uri)
    if not old:
        raise FileNotFoundError(f"unknown supersedes target: {replaces_uri}")
    old_entry = old[_resolve_index(old, replaces_index)]
    supersedes_id = old_entry.get("id") or stable_id(
        replaces_uri, old_entry.get("created_at", ""), old_entry.get("content", "")
    )
    result = supersede_memory(root, uri, index=index,
                              supersedes_id=supersedes_id, confirmed=True)
    log_action(root, "supersede", result.get("id"), actor=actor,
               reason=reason or f"replaced by {supersedes_id}", data={"uri": uri})
    return result


def request_conflict(
    root: Path, uri: str, *, index: int = -1, confirmed: bool = False,
    actor: str = "user", reason: str = "",
) -> dict[str, Any]:
    if not confirmed:
        raise MemoryPolicyError("REQUIRES_CONFIRMATION", "conflict 必须用户确认")
    entries = _load_raw(root, uri)
    if not entries:
        raise FileNotFoundError(f"unknown memory: {uri}")
    check_transition(entries[_resolve_index(entries, index)], "conflict", confirmed=True)
    result = mark_conflicted(root, uri, index=index, confirmed=True)
    log_action(root, "conflict", result.get("id"), actor=actor,
               reason=reason or "conflicted", data={"uri": uri})
    return result


def request_discard(
    root: Path, uri: str, *, index: int = -1, all_: bool = False,
    confirmed: bool = False, actor: str = "user", reason: str = "",
) -> dict[str, Any]:
    entries = _load_raw(root, uri)
    if not entries:
        raise FileNotFoundError(f"unknown memory: {uri}")
    targets = entries if all_ else [entries[_resolve_index(entries, index)]]
    for entry in targets:
        check_transition(entry, "discard", confirmed=confirmed)
    result = discard_memory(root, uri, index=index, all_=all_)
    log_action(root, "discard", result.get("id"), actor=actor,
               reason=reason or "discarded", data={"uri": uri})
    return result


def request_archive(
    root: Path, uri: str, *, index: int = -1, all_: bool = False,
    actor: str = "user", reason: str = "",
) -> dict[str, Any]:
    entries = _load_raw(root, uri)
    if not entries:
        raise FileNotFoundError(f"unknown memory: {uri}")
    targets = entries if all_ else [entries[_resolve_index(entries, index)]]
    for entry in targets:
        check_transition(entry, "archive")
    result = archive_memory(root, uri, index=index, all_=all_)
    log_action(root, "archive", result.get("id"), actor=actor,
               reason=reason or "archived", data={"uri": uri})
    return result


def reason_for(entry: dict[str, Any]) -> list[str]:
    """供 settle / CLI 展示"为什么保留/为什么可归档/为什么建议提升"。"""
    reasons: list[str] = []
    status = entry.get("status")
    validity = entry.get("validity")
    if validity in ("superseded", "archived", "discarded"):
        reasons.append(f"已{validity}，不注入上下文")
    if status == "conflicted":
        reasons.append("存在冲突，等待确认")
    unresolved = entry.get("unresolved") or []
    if unresolved:
        reasons.append(f"有 {len(unresolved)} 个未决项，保留 short")
    evidence = entry.get("evidence") or []
    if status == "verified" and evidence:
        reasons.append("已验证且有证据，可考虑提升 medium")
    if not evidence and validity == "current":
        reasons.append("无证据，未验证")
    return reasons
