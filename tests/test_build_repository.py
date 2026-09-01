from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

from scripts.build_repository import build_repository, read_plugin_metadata


ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = ROOT / "plugins"


def published_plugins():
    archives = sorted(
        path
        for path in PLUGINS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".zip", ".jar"}
    )
    return [read_plugin_metadata(archive) for archive in archives]


def codexbar_plugin():
    for plugin in published_plugins():
        if plugin.plugin_id == "it.aldericogallo.codexbar-jetbrains":
            return plugin
    raise AssertionError("CodexBar archive is missing from plugins/")


class BuildRepositoryTests(unittest.TestCase):
    def test_reads_metadata_from_nested_plugin_jar(self) -> None:
        plugin = codexbar_plugin()

        self.assertEqual(plugin.plugin_id, "it.aldericogallo.codexbar-jetbrains")
        self.assertTrue(plugin.version)
        self.assertEqual(plugin.name, "CodexBar")
        self.assertTrue(plugin.since_build)

    def test_builds_pages_site_and_jetbrains_feed(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".test-build-", dir=ROOT) as temp:
            output = Path(temp) / "site"
            plugins = build_repository(
                PLUGINS_DIR, output, "https://example.github.io/plugin-repo"
            )

            feed = ET.parse(output / "updatePlugins.xml").getroot()
            entries = {entry.get("id"): entry for entry in feed.findall("plugin")}
            self.assertEqual(len(entries), len(plugins))

            for plugin in plugins:
                entry = entries[plugin.plugin_id]
                self.assertEqual(entry.get("version"), plugin.version)
                self.assertEqual(
                    entry.get("url"),
                    "https://example.github.io/plugin-repo/plugins/"
                    + quote(plugin.archive_path.name),
                )
                idea_version = entry.find("idea-version")
                self.assertIsNotNone(idea_version)
                assert idea_version is not None
                self.assertEqual(
                    idea_version.get("since-build"), plugin.since_build
                )
                self.assertTrue(
                    (output / "plugins" / plugin.archive_path.name).is_file()
                )

            self.assertTrue((output / ".nojekyll").is_file())
            self.assertIn(
                "https://example.github.io/plugin-repo/updatePlugins.xml",
                (output / "index.html").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
