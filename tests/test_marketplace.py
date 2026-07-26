import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.generate import (
    ROOT,
    RUNTIME_ONLY_PATHS,
    check_generated,
    committed_generated_relative_paths,
    generate,
    parse_frontmatter,
    render_docs,
)
from tools.validate import validate_repo


class MarketplaceTests(unittest.TestCase):
    def copy_repository(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory(prefix="agents-test-")
        destination = Path(temporary.name) / "repo"
        shutil.copytree(
            ROOT,
            destination,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"),
        )
        return temporary, destination

    def test_source_repository_is_valid(self):
        findings = validate_repo(ROOT, require_generated=False)
        errors = [finding for finding in findings if finding.severity == "error"]
        self.assertEqual(errors, [], [f"{item.path}: {item.message}" for item in errors])

    def test_marketplace_points_to_the_feishu_plugin(self):
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual(marketplace["name"], "feishu-agents")
        self.assertEqual([entry["name"] for entry in marketplace["plugins"]], ["feishu-open-platform"])

    def test_skill_frontmatter_has_an_activation_description(self):
        content = (
            ROOT
            / "plugins"
            / "feishu-open-platform"
            / "skills"
            / "feishu-api-integration"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        fields, body = parse_frontmatter(content)
        self.assertIn("Use when", fields["description"])
        self.assertGreater(len(body), 100)

    def test_generated_opencode_agent_has_permissions(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        generate(repository, harness="opencode", docs=False)
        agents = list((repository / ".opencode" / "agents").glob("*.md"))
        self.assertTrue(agents)
        content = agents[0].read_text(encoding="utf-8")
        self.assertIn('mode: "subagent"', content)
        self.assertIn("permission:", content)

    def test_generated_codex_skills_fit_the_byte_cap(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        generate(repository, harness="codex", docs=False)
        skills = list((repository / ".codex" / "skills").glob("*/SKILL.md"))
        self.assertTrue(skills)
        self.assertTrue(all(len(path.read_bytes()) <= 8192 for path in skills))

    def test_generated_docs_match_the_source_renderer(self):
        for relative_path, expected in render_docs(ROOT).items():
            self.assertEqual((ROOT / relative_path).read_text(encoding="utf-8"), expected)

    def test_marketplace_versions_are_synced(self):
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        codex = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        source_versions = {entry["name"]: entry["version"] for entry in marketplace["plugins"]}
        codex_versions = {entry["name"]: entry["version"] for entry in codex["plugins"]}
        self.assertEqual(source_versions, codex_versions)
        for plugin_name, version in source_versions.items():
            manifest = json.loads(
                (ROOT / "plugins" / plugin_name / ".claude-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(version, manifest["version"])

    def test_check_generated_passes_for_clean_repository(self):
        self.assertEqual(check_generated(ROOT), 0)

    def test_check_generated_detects_stale_documentation(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / "docs" / "plugins.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nmanual edit\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_generated(repository), 1)

    def test_only_lightweight_generated_artifacts_are_committed(self):
        committed = committed_generated_relative_paths(ROOT, harness="all", docs=True)
        self.assertIn(".agents/plugins/marketplace.json", committed)
        self.assertIn(".cursor-plugin/marketplace.json", committed)
        self.assertIn("gemini-extension.json", committed)
        self.assertIn("docs/plugins.md", committed)
        for runtime_path in RUNTIME_ONLY_PATHS:
            prefix = runtime_path.rstrip("/") + "/"
            self.assertFalse(any(path == runtime_path or path.startswith(prefix) for path in committed))

    def test_clean_clone_can_generate_and_validate_runtime_artifacts(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        for relative in RUNTIME_ONLY_PATHS:
            path = repository / relative
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        self.assertEqual(check_generated(repository), 0)
        generate(repository, harness="all", docs=True)
        findings = validate_repo(repository, require_generated=True)
        self.assertEqual(
            [finding for finding in findings if finding.severity == "error"],
            [],
            [f"{finding.path}: {finding.message}" for finding in findings if finding.severity == "error"],
        )

    def test_multiple_plugins_are_generated_and_catalogued(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)

        source_plugin = repository / "plugins" / "feishu-open-platform"
        second_plugin = repository / "plugins" / "sample-plugin"
        shutil.copytree(source_plugin, second_plugin)

        manifest_path = second_plugin / ".claude-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update(
            {
                "name": "sample-plugin",
                "version": "0.1.1",
                "description": "用于测试自动发现的示例插件",
            }
        )
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        marketplace_path = repository / ".claude-plugin" / "marketplace.json"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        marketplace["plugins"].append(
            {
                "name": "sample-plugin",
                "source": "./plugins/sample-plugin",
                "description": manifest["description"],
                "version": manifest["version"],
                "author": manifest["author"],
                "homepage": manifest["homepage"],
                "license": manifest["license"],
                "category": "Coding",
            }
        )
        marketplace_path.write_text(
            json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        generate(repository, harness="all", docs=True)
        codex = json.loads(
            (repository / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual([entry["name"] for entry in codex["plugins"]], ["feishu-open-platform", "sample-plugin"])
        self.assertIn("sample-plugin", (repository / "docs" / "plugins.md").read_text(encoding="utf-8"))
        self.assertTrue((repository / ".codex" / "agents" / "sample-plugin__feishu-api-developer.toml").is_file())
        self.assertTrue((repository / ".cursor-plugin" / "plugins" / "sample-plugin.json").is_file())
        self.assertTrue((repository / ".copilot" / "agents" / "sample-plugin__feishu-api-developer.agent.md").is_file())
        self.assertTrue((repository / "agents" / "sample-plugin__feishu-api-developer.md").is_file())
        findings = validate_repo(repository, require_generated=True)
        self.assertEqual(
            [finding for finding in findings if finding.severity == "error"],
            [],
            [f"{finding.path}: {finding.message}" for finding in findings if finding.severity == "error"],
        )

        shutil.rmtree(repository / "plugins" / "sample-plugin")
        marketplace["plugins"] = [entry for entry in marketplace["plugins"] if entry["name"] != "sample-plugin"]
        marketplace_path.write_text(json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        generate(repository, harness="all", docs=True)
        self.assertFalse((repository / ".cursor-plugin" / "plugins" / "sample-plugin.json").exists())
        self.assertFalse((repository / ".copilot" / "agents" / "sample-plugin__feishu-api-developer.agent.md").exists())

    def test_version_mismatch_is_reported(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        marketplace_path = repository / ".claude-plugin" / "marketplace.json"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        marketplace["plugins"][0]["version"] = "9.9.9"
        marketplace_path.write_text(
            json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        findings = validate_repo(repository, require_generated=False)
        messages = [finding.message for finding in findings]
        self.assertTrue(any("marketplace version must match" in message for message in messages))

    def test_duplicate_marketplace_plugin_is_reported(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        marketplace_path = repository / ".claude-plugin" / "marketplace.json"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        marketplace["plugins"].append(dict(marketplace["plugins"][0]))
        marketplace_path.write_text(
            json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        findings = validate_repo(repository, require_generated=False)
        messages = [finding.message for finding in findings]
        self.assertTrue(any("globally unique" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
