import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.doc_gardener import run_garden
from tools.generate import ROOT


class GardenTests(unittest.TestCase):
    def copy_repository(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory(prefix="garden-test-")
        destination = Path(temporary.name) / "repo"
        shutil.copytree(ROOT, destination, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        return temporary, destination

    def test_clean_repository_has_no_findings(self):
        self.assertEqual(run_garden(ROOT), [])

    def test_stale_generated_file_is_reported(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / ".cursor-plugin/marketplace.json"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        findings = run_garden(repository)
        self.assertTrue(any(finding.kind == "generated-drift" for finding in findings))

    def test_dead_link_is_reported_as_warning(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / "docs/broken.md"
        path.write_text("[missing](does-not-exist.md)\n", encoding="utf-8")
        findings = run_garden(repository)
        self.assertTrue(any(finding.kind == "dead-link" and finding.severity == "warning" for finding in findings))

    def test_oversized_context_is_reported(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / "AGENTS.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n" + ("extra\n" * 151), encoding="utf-8")
        findings = run_garden(repository)
        self.assertTrue(any(finding.kind == "context-size" for finding in findings))

    def test_marketplace_extra_entry_is_reported(self):
        temporary, repository = self.copy_repository()
        self.addCleanup(temporary.cleanup)
        path = repository / ".claude-plugin/marketplace.json"
        marketplace = json.loads(path.read_text(encoding="utf-8"))
        marketplace["plugins"].append({"name": "missing-plugin", "source": "./plugins/missing-plugin"})
        path.write_text(json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        findings = run_garden(repository)
        self.assertTrue(any(finding.kind == "marketplace-drift" for finding in findings))
