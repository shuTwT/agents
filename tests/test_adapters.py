import contextlib
import io
import json
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

from tools.adapters.base import load_plugins, parse_frontmatter, rewrite_tool_references
from tools.adapters.capabilities import CAPABILITIES, MODEL_ALIASES, TOOL_NAME_MAPS, resolve_model, supported_harnesses
from tools.generate import ROOT, generate


class AdapterTests(unittest.TestCase):
    def copy_repository(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory(prefix="adapter-test-")
        destination = Path(temporary.name) / "repo"
        shutil.copytree(ROOT, destination, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        return temporary, destination

    def test_registry_and_capability_matrix_are_complete(self):
        self.assertEqual(set(supported_harnesses()), set(MODEL_ALIASES) - {"claude-code"})
        self.assertTrue(set(supported_harnesses()).issubset(CAPABILITIES))
        for harness in supported_harnesses():
            self.assertTrue(TOOL_NAME_MAPS[harness])
            self.assertIn("inherit", MODEL_ALIASES[harness])

    def test_all_harness_outputs_exist_and_parse(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        generate(repository, harness="all", docs=True)
        expected = [
            repository / ".agents/plugins/marketplace.json",
            repository / ".cursor-plugin/marketplace.json",
            repository / "gemini-extension.json",
            repository / ".copilot/agents/feishu-open-platform__feishu-api-developer.agent.md",
            repository / "agents/feishu-open-platform__feishu-api-developer.md",
            repository / "skills/feishu-open-platform__feishu-api-integration/SKILL.md",
            repository / "commands/feishu-open-platform/api-integration.toml",
        ]
        for path in expected:
            self.assertTrue(path.is_file(), path)

        json.loads((repository / ".cursor-plugin/marketplace.json").read_text(encoding="utf-8"))
        json.loads((repository / "gemini-extension.json").read_text(encoding="utf-8"))
        tomllib.loads((repository / "commands/feishu-open-platform/api-integration.toml").read_text(encoding="utf-8"))

        agent_fields, _ = parse_frontmatter(
            (repository / ".copilot/agents/feishu-open-platform__feishu-api-developer.agent.md").read_text(encoding="utf-8")
        )
        self.assertEqual(agent_fields["name"], "feishu-open-platform__feishu-api-developer")

    def test_model_and_tool_mappings_are_target_specific(self):
        self.assertEqual(resolve_model("codex", "opus")[0], "gpt-5.5")
        self.assertEqual(resolve_model("gemini", "haiku")[0], "gemini-2.5-flash")
        self.assertEqual(resolve_model("cursor", "opus")[0], "inherit")
        self.assertIn("read_file", rewrite_tool_references("Use the `Read` tool.", "gemini"))
        self.assertIn("open the file", rewrite_tool_references("Use the `Read` tool.", "codex"))

    def test_gemini_large_command_uses_source_injection(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        command = repository / "plugins/feishu-open-platform/commands/api-integration.md"
        command.write_text(command.read_text(encoding="utf-8") + "\n" + ("large protocol " * 400), encoding="utf-8")
        generate(repository, harness="gemini", docs=False)
        generated = tomllib.loads((repository / "commands/feishu-open-platform/api-integration.toml").read_text(encoding="utf-8"))
        self.assertIn("@{plugins/feishu-open-platform/commands/api-integration.md}", generated["prompt"])

    def test_unknown_model_emits_warning_and_falls_back(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        agent = repository / "plugins/feishu-open-platform/agents/feishu-api-developer.md"
        agent.write_text(agent.read_text(encoding="utf-8").replace("model: inherit", "model: future-model"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            generate(repository, harness="gemini", docs=False)
        self.assertIn("unknown model alias", output.getvalue())
        fields, _ = parse_frontmatter((repository / "agents/feishu-open-platform__feishu-api-developer.md").read_text(encoding="utf-8"))
        self.assertEqual(fields["model"], "gemini-2.5-pro")

    def test_copilot_command_is_manual_skill(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        generate(repository, harness="copilot", docs=False)
        fields, _ = parse_frontmatter((repository / ".copilot/skills/feishu-open-platform-api-integration/SKILL.md").read_text(encoding="utf-8"))
        self.assertTrue(fields["user-invocable"])
        self.assertTrue(fields["disable-model-invocation"])

    def test_load_plugins_keeps_same_component_names_namespaced(self):
        plugins = load_plugins(ROOT)
        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0].agents[0].name, "feishu-api-developer")
        self.assertEqual(plugins[0].skills[0].name, "feishu-api-integration")
