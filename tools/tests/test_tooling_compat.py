import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.adapters import CAPABILITIES, context_paragraph, load_plugin, token_estimate
from tools.adapters.codex import CodexAdapter
from tools.generate import ROOT, get_adapter
from tools.install_copilot import install as install_copilot
from tools.install_copilot import uninstall as uninstall_copilot
from tools.install_opencode import install as install_opencode
from tools.install_opencode import uninstall as uninstall_opencode


class ToolingCompatibilityTests(unittest.TestCase):
    def test_upstream_source_and_adapter_aliases(self):
        plugin = load_plugin("feishu-open-platform", ROOT)
        self.assertIsNotNone(plugin)
        assert plugin is not None
        self.assertEqual(plugin.dir, plugin.path)
        self.assertEqual(plugin.skills[0].dir, plugin.skills[0].path.parent)
        self.assertEqual(plugin.skills[0].body_bytes, len(plugin.skills[0].body.encode("utf-8")))
        self.assertGreater(token_estimate(plugin.skills[0].body), 0)
        self.assertTrue(context_paragraph("Heading\n\nA useful summary."))
        self.assertIn("codex", CAPABILITIES)

    def test_get_adapter_accepts_upstream_output_root_keyword(self):
        with tempfile.TemporaryDirectory(prefix="adapter-output-") as temporary:
            output_root = Path(temporary)
            adapter = get_adapter("codex", output_root)
            self.assertIsInstance(adapter, CodexAdapter)
            self.assertEqual(adapter.output_root, output_root)
            self.assertEqual(adapter.capabilities.harness_id, "codex")

    def test_adapter_refuses_path_escape(self):
        with tempfile.TemporaryDirectory(prefix="adapter-safe-") as temporary:
            adapter = CodexAdapter(output_root=Path(temporary))
            with self.assertRaises(ValueError):
                adapter.write("../escape.txt", "unsafe")

    def test_upstream_plugin_cli_and_output_root(self):
        with tempfile.TemporaryDirectory(prefix="generate-output-") as temporary:
            output_root = Path(temporary)
            completed = subprocess.run(
                [
                    "python3",
                    "tools/generate.py",
                    "--harness",
                    "gemini",
                    "--plugin",
                    "feishu-open-platform",
                    "--output-root",
                    str(output_root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output_root / "gemini-extension.json").is_file())
            self.assertTrue(
                (output_root / "agents/feishu-open-platform__feishu-api-developer.md").is_file()
            )

    def test_strict_generation_fails_on_warning(self):
        with tempfile.TemporaryDirectory(prefix="strict-output-") as temporary:
            completed = subprocess.run(
                [
                    "python3",
                    "tools/generate.py",
                    "--harness",
                    "codex",
                    "--plugin",
                    "feishu-open-platform",
                    "--strict",
                    "--output-root",
                    temporary,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn("[warning]", completed.stdout)

    def test_opencode_installer_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="opencode-install-") as temporary:
            base = Path(temporary)
            output_root = base / "repo"
            config_root = base / "config"
            get_adapter("opencode", output_root).emit_all([load_plugin("feishu-open-platform", ROOT)])
            installed = install_opencode(repo_root=output_root, config_dir=config_root)
            self.assertTrue(installed.ok)
            self.assertGreater(installed.linked, 0)
            repeated = install_opencode(repo_root=output_root, config_dir=config_root)
            self.assertEqual(repeated.linked, 0)
            self.assertGreater(repeated.unchanged, 0)
            removed = uninstall_opencode(repo_root=output_root, config_dir=config_root)
            self.assertEqual(removed.removed, installed.linked)

    def test_copilot_installer_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="copilot-install-") as temporary:
            base = Path(temporary)
            output_root = base / "repo"
            config_root = base / "config"
            get_adapter("copilot", output_root).emit_all([load_plugin("feishu-open-platform", ROOT)])
            installed = install_copilot(repo_root=output_root, config_dir=config_root)
            self.assertTrue(installed.ok)
            self.assertGreater(installed.linked, 0)
            removed = uninstall_copilot(repo_root=output_root, config_dir=config_root)
            self.assertEqual(removed.removed, installed.linked)


if __name__ == "__main__":
    unittest.main()
