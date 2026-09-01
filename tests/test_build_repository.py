from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.build_repository import build_repository, read_plugin_metadata


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "plugins" / "codexbar-jetbrains-0.0.2.zip"


class BuildRepositoryTests(unittest.TestCase):
    def test_reads_metadata_from_nested_plugin_jar(self) -> None:
        plugin = read_plugin_metadata(ARCHIVE)

        self.assertEqual(plugin.plugin_id, "it.aldericogallo.codexbar-jetbrains")
        self.assertEqual(plugin.version, "0.0.2")
        self.assertEqual(plugin.name, "CodexBar")
        self.assertEqual(plugin.since_build, "262")

    def test_builds_pages_site_and_jetbrains_feed(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".test-build-", dir=ROOT) as temp:
            output = Path(temp) / "site"
            plugins = build_repository(
                ROOT / "plugins", output, "https://example.github.io/plugin-repo"
            )

            feed = ET.parse(output / "updatePlugins.xml").getroot()
            entry = feed.find("plugin")
            self.assertEqual(len(plugins), 1)
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertEqual(entry.get("id"), "it.aldericogallo.codexbar-jetbrains")
            self.assertEqual(entry.get("version"), "0.0.2")
            self.assertEqual(
                entry.get("url"),
                "https://example.github.io/plugin-repo/plugins/codexbar-jetbrains-0.0.2.zip",
            )
            self.assertEqual(entry.find("idea-version").get("since-build"), "262")
            self.assertTrue((output / "plugins" / ARCHIVE.name).is_file())
            self.assertTrue((output / ".nojekyll").is_file())
            self.assertIn(
                "https://example.github.io/plugin-repo/updatePlugins.xml",
                (output / "index.html").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
