from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

from xiaot_memory.memory import read_memory
from xiaot_memory.memory_policy import (
    MemoryPolicyError,
    request_promote,
    request_verify,
    write_entry,
)
from xiaot_memory.workspace import initialize_workspace


class PolicyRoot:
    """临时仓库根上下文管理器。"""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        initialize_workspace(self.root)

    def __enter__(self):
        return self.root

    def __exit__(self, *exc):
        self._tmp.cleanup()


class TestAdmissionPolicy(unittest.TestCase):
    # 场景 1：没有 task_id 的普通 short 写入失败
    def test_short_without_task_id_fails(self):
        with PolicyRoot() as root:
            with self.assertRaises(MemoryPolicyError) as ctx:
                write_entry(root, "memory://session/A/short", "no task")
            self.assertEqual(ctx.exception.code, "SHORT_REQUIRES_TASK")
            # 不产生半完成状态
            self.assertEqual(read_memory(root, "memory://session/A/short"), [])

    # 场景 2：普通技术事实直接写 long 失败
    def test_tech_fact_direct_long_fails(self):
        with PolicyRoot() as root:
            with self.assertRaises(MemoryPolicyError) as ctx:
                write_entry(
                    root, "memory://project/ASR/long", "beam < 2",
                    kind="conclusion", source={"project": "ASR"},
                )
            self.assertEqual(ctx.exception.code, "LONG_NO_DIRECT_TECH_FACT")

    # 场景 3：用户明确长期偏好可以写 global + long + active
    def test_user_preference_global_long_active_ok(self):
        with PolicyRoot() as root:
            item = write_entry(
                root, "memory://global/prefs/long",
                "以后所有回答都使用中文", kind="preference",
                status="active", confirmed=True,
            )
            self.assertEqual(item["tier"], "long")
            self.assertEqual(item["scope"], "global")
            self.assertEqual(item["status"], "active")
            self.assertEqual(item["validity"], "current")
            loaded = read_memory(root, "memory://global/prefs/long")[0]
            self.assertEqual(loaded["content"], "以后所有回答都使用中文")

    # 合法 short 写入：带 task_id
    def test_short_with_task_ok(self):
        with PolicyRoot() as root:
            item = write_entry(
                root, "memory://session/A/short", "finding",
                source={"task": "T1"}, kind="conclusion",
            )
            self.assertEqual(item["status"], "candidate")
            self.assertEqual(item["task_id"], "T1")

    # 任务定义可直接写 task/medium（创建专题入口）
    def test_task_definition_medium_allowed(self):
        with PolicyRoot() as root:
            item = write_entry(
                root, "memory://task/T1/medium",
                "目标：x｜范围：y｜验收：z", kind="conclusion",
                source={"task": "T1"},
            )
            self.assertEqual(item["tier"], "medium")
            self.assertEqual(item["scope"], "task")

    # 用户确认的项目级约束可直接写 project/medium
    def test_project_constraint_medium_ok(self):
        with PolicyRoot() as root:
            item = write_entry(
                root, "memory://project/ASR/medium",
                "保持 schema 不变", kind="constraint",
                confirmed=True, source={"project": "ASR"},
            )
            self.assertEqual(item["scope"], "project")
            self.assertEqual(item["kind"], "constraint")


class TestTransitionMatrix(unittest.TestCase):
    def _verified_short(self, root, task="T1", content="beam threshold found"):
        """写一条已验证的 short（带证据）。"""
        write_entry(
            root, "memory://session/A/short", content,
            source={"task": task}, kind="conclusion",
        )
        request_verify(root, "memory://session/A/short", evidence=["test:beam<2"])
        return content

    # 场景 7：short -> medium 缺证据失败
    def test_promote_medium_missing_evidence_fails(self):
        with PolicyRoot() as root:
            # 普通 short（candidate、无证据），用户确认跳过 NOT_VERIFIED，证据仍缺失
            write_entry(
                root, "memory://session/A/short", "beam threshold found",
                source={"task": "T1"}, kind="conclusion",
            )
            with self.assertRaises(MemoryPolicyError) as ctx:
                request_promote(
                    root, "memory://session/A/short", "medium",
                    confirmed=True, distilled="提炼后：beam 阈值 2",
                )
            self.assertEqual(ctx.exception.code, "MEDIUM_REQUIRES_EVIDENCE")

    # 场景 8：short -> medium 未重新提炼失败（复制原文）
    def test_promote_medium_not_distilled_fails(self):
        with PolicyRoot() as root:
            content = self._verified_short(root)
            with self.assertRaises(MemoryPolicyError) as ctx:
                request_promote(
                    root, "memory://session/A/short", "medium",
                    confirmed=True, evidence=["test:beam<2"], distilled=content,
                )
            self.assertEqual(ctx.exception.code, "MEDIUM_REQUIRES_DISTILLED")
            # 空 distilled 也失败
            with self.assertRaises(MemoryPolicyError):
                request_promote(
                    root, "memory://session/A/short", "medium",
                    confirmed=True, evidence=["test:beam<2"], distilled=None,
                )

    # 场景 9：short -> medium 未确认失败
    def test_promote_medium_not_confirmed_fails(self):
        with PolicyRoot() as root:
            self._verified_short(root)
            with self.assertRaises(MemoryPolicyError) as ctx:
                request_promote(
                    root, "memory://session/A/short", "medium",
                    confirmed=False, evidence=["test:beam<2"],
                    distilled="提炼后：beam 阈值 2",
                )
            self.assertEqual(ctx.exception.code, "REQUIRES_CONFIRMATION")

    # 合法晋升：已验证 + 证据 + 提炼 + 确认
    def test_promote_medium_success(self):
        with PolicyRoot() as root:
            self._verified_short(root)
            result = request_promote(
                root, "memory://session/A/short", "medium",
                confirmed=True, evidence=["test:beam<2"],
                distilled="beam 阈值固定为 2",
            )
            self.assertEqual(result["uri"], "memory://task/T1/medium")
            self.assertEqual(result["content"], "beam 阈值固定为 2")
            self.assertIn("test:beam<2", result["evidence"])
            # 原文未复制，文件已迁移
            self.assertEqual(read_memory(root, "memory://session/A/short"), [])

    # medium -> long：需 verified + 证据 + 确认 + project 归属
    def test_promote_long_requires_verified_and_confirmed(self):
        with PolicyRoot() as root:
            self._verified_short(root, task="T1")
            # 补 project 归属（medium -> long 需要），重新写一条带 project 的 short
            write_entry(
                root, "memory://session/B/short", "beam threshold found",
                source={"task": "T1", "project": "P1"}, kind="conclusion",
            )
            request_verify(root, "memory://session/B/short", evidence=["test:beam<2"])
            request_promote(
                root, "memory://session/B/short", "medium",
                confirmed=True, evidence=["test:beam<2"],
                distilled="beam 阈值固定为 2",
            )
            # 晋升到 medium 后 status=active，需先 verify 再升 long
            request_verify(
                root, "memory://task/T1/medium", evidence=["test:beam<2"], confirmed=True,
            )
            # 未确认失败
            with self.assertRaises(MemoryPolicyError):
                request_promote(
                    root, "memory://task/T1/medium", "long",
                    confirmed=False, evidence=["test:beam<2"], distilled="beam 长期结论",
                )
            # 合法晋升
            result = request_promote(
                root, "memory://task/T1/medium", "long",
                confirmed=True, evidence=["test:beam<2"], distilled="beam 长期结论",
            )
            self.assertEqual(result["tier"], "long")
            self.assertEqual(result["status"], "verified")

    # 普通技术事实 long 晋升来源非 verified 时失败
    def test_promote_long_not_verified_fails(self):
        with PolicyRoot() as root:
            write_entry(
                root, "memory://task/T1/medium", "目标：x",
                kind="conclusion", source={"task": "T1"},
            )
            with self.assertRaises(MemoryPolicyError) as ctx:
                request_promote(
                    root, "memory://task/T1/medium", "long",
                    confirmed=True, evidence=["e1"], distilled="d",
                )
            self.assertEqual(ctx.exception.code, "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
