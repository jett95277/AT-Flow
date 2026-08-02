from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from at_flow import setup as at_setup
from at_flow.setup import (
    CheckResult,
    _port_open,
    backend_command,
    environment_report,
    frontend_command,
    merge_opencode_config,
    opencode_config_path,
    provider_commands_fixed,
    resolve_npm,
)


class SetupCheckTests(unittest.TestCase):
    def test_opencode_config_path_uses_home_config_dir(self):
        self.assertEqual(
            opencode_config_path(Path("C:/Users/test")),
            Path("C:/Users/test/.config/opencode/opencode.jsonc"),
        )

    def test_environment_report_flags_missing_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            report = environment_report(Path(directory))
            workspace_check = next(item for item in report if item.name == "at_workspace")
            self.assertEqual(workspace_check.status, "MISSING")

    def test_environment_report_reports_ok_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "at.config.json").write_text("{}", encoding="utf-8")
            report = environment_report(root)
            workspace_check = next(item for item in report if item.name == "at_workspace")
            self.assertEqual(workspace_check.status, "OK")

    def test_environment_report_flags_trigger_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "at.config.json").write_text("{}", encoding="utf-8")
            report = environment_report(root)
            trigger_check = next(item for item in report if item.name == "codex_trigger")
            self.assertEqual(trigger_check.status, "MISSING")

    def test_environment_report_reports_corrupt_config_as_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "at.config.json").write_text("{not json", encoding="utf-8")
            report = environment_report(root)
            check = next(item for item in report if item.name == "provider_commands")
            self.assertEqual(check.status, "ERROR")

    def test_opencode_check_handles_non_object_permission(self):
        import json as json_module

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = Path(directory) / "opencode.jsonc"
            config.write_text(json_module.dumps({"permission": "ask"}), encoding="utf-8")
            original = at_setup.opencode_config_path
            at_setup.opencode_config_path = lambda home=None: config
            try:
                report = environment_report(root)
            finally:
                at_setup.opencode_config_path = original
            check = next(item for item in report if item.name == "opencode_global_config")
            self.assertEqual(check.status, "ERROR")

    def test_opencode_check_flags_missing_sessions_rule(self):
        import json as json_module

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = Path(directory) / "opencode.jsonc"
            config.write_text(
                json_module.dumps(
                    {
                        "provider": {"deepseek": {"models": {"deepseek-v4-flash": {}}}},
                        "permission": {"external_directory": {f"{root.as_posix()}/.at/shared/**": "allow"}},
                    }
                ),
                encoding="utf-8",
            )
            original = at_setup.opencode_config_path
            at_setup.opencode_config_path = lambda home=None: config
            try:
                report = environment_report(root)
            finally:
                at_setup.opencode_config_path = original
            check = next(item for item in report if item.name == "opencode_global_config")
            self.assertEqual(check.status, "FIXABLE")


class SetupInstallLogicTests(unittest.TestCase):
    def test_provider_commands_fixed_adds_codex_exec_and_opencode_run(self):
        config = {
            "providers": {
                "codex": {"command": ["codex"]},
                "opencode": {"command": ["opencode"]},
            }
        }
        fixed, changes = provider_commands_fixed(config)
        self.assertIn("exec", fixed["providers"]["codex"]["command"])
        self.assertEqual(fixed["providers"]["opencode"]["command"], ["opencode", "run"])
        self.assertEqual(len(changes), 2)

    def test_provider_commands_fixed_keeps_custom_executable(self):
        config = {"providers": {"codex": {"command": ["my-codex"]}}}
        fixed, _ = provider_commands_fixed(config)
        self.assertEqual(fixed["providers"]["codex"]["command"][0], "my-codex")
        self.assertIn("exec", fixed["providers"]["codex"]["command"])

    def test_provider_commands_fixed_keeps_existing_non_interactive(self):
        config = {
            "providers": {
                "codex": {"command": ["codex", "exec", "--ephemeral", "-"]},
                "opencode": {"command": ["opencode", "run"]},
            }
        }
        fixed, changes = provider_commands_fixed(config)
        self.assertEqual(changes, [])
        self.assertEqual(fixed["providers"]["opencode"]["command"], ["opencode", "run"])

    def test_merge_opencode_config_creates_template(self):
        merged = merge_opencode_config(None, Path("E:/AT FLOW"))
        self.assertEqual(merged["model"], "deepseek/deepseek-v4-flash")
        self.assertIn("E:/AT FLOW/.at/shared/**", merged["permission"]["external_directory"])

    def test_merge_opencode_config_preserves_existing_keys(self):
        existing = {"model": "anthropic/claude-sonnet", "permission": {"bash": "allow"}}
        merged = merge_opencode_config(existing, Path("E:/AT FLOW"))
        self.assertEqual(merged["model"], "anthropic/claude-sonnet")
        self.assertEqual(merged["permission"]["bash"], "allow")
        self.assertIn("E:/AT FLOW/.at/shared/**", merged["permission"]["external_directory"])

    def test_merge_opencode_config_adds_missing_deepseek_model(self):
        existing = {"permission": {"external_directory": {"C:/other/**": "allow"}}}
        merged = merge_opencode_config(existing, Path("E:/AT FLOW"))
        self.assertEqual(merged["provider"]["deepseek"]["models"]["deepseek-v4-flash"]["name"], "DeepSeek V4 Flash")
        self.assertIn("C:/other/**", merged["permission"]["external_directory"])


class SetupStartTests(unittest.TestCase):
    def test_backend_command_contains_web_module_and_root(self):
        cmd = backend_command(Path("E:/AT FLOW"), 8123)
        self.assertIn("-m", cmd)
        self.assertIn("at_flow.web", cmd)
        self.assertIn("--port", cmd)
        self.assertEqual(cmd[cmd.index("--port") + 1], "8123")
        self.assertEqual(Path(cmd[cmd.index("--root") + 1]), Path("E:/AT FLOW"))

    def test_frontend_command_runs_dev_server(self):
        cmd = frontend_command(3123)
        self.assertEqual(cmd[0], resolve_npm())
        self.assertIn("dev", cmd)
        self.assertEqual(cmd[cmd.index("--port") + 1], "3123")

    def test_port_open_false_for_unused_port(self):
        self.assertFalse(_port_open("127.0.0.1", 1))


class SetupDoctorTests(unittest.TestCase):
    def test_print_ready_guide_lists_both_entries(self):
        import builtins

        lines: list[str] = []

        def fake_print(*args, **kwargs):
            lines.append(" ".join(str(item) for item in args))

        original = builtins.print
        at_setup.print = fake_print
        try:
            at_setup.print_ready_guide(Path("E:/AT FLOW"), 8000, 3000)
        finally:
            at_setup.print = original
        joined = "\n".join(lines)
        self.assertIn("Codex", joined)
        self.assertIn("http://127.0.0.1:3000/runtime", joined)


class SetupScriptTests(unittest.TestCase):
    def test_scripts_setup_exposes_main(self):
        import runpy

        namespace = runpy.run_path(str(ROOT / "scripts" / "setup.py"))
        self.assertTrue(callable(namespace["main"]))

    def test_scripts_setup_help_exits_zero(self):
        import runpy

        namespace = runpy.run_path(str(ROOT / "scripts" / "setup.py"))
        with self.assertRaises(SystemExit) as ctx:
            namespace["main"](["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
