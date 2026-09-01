from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_repository import read_plugin_metadata  # noqa: E402
from publish_plugin import publish_plugin  # noqa: E402


PLUGINS_DIR = ROOT / "plugins"


def codexbar_archive() -> Path:
    archives = sorted(
        path
        for path in PLUGINS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".zip", ".jar"}
    )
    for archive in archives:
        if (
            read_plugin_metadata(archive).plugin_id
            == "it.aldericogallo.codexbar-jetbrains"
        ):
            return archive
    raise AssertionError("CodexBar archive is missing from plugins/")


class PublishPluginTests(unittest.TestCase):
    def test_replaces_archive_with_the_same_plugin_id(self) -> None:
        archive = codexbar_archive()
        metadata = read_plugin_metadata(archive)
        with tempfile.TemporaryDirectory(prefix=".test-publish-", dir=ROOT) as temp:
            plugins_dir = Path(temp) / "plugins"
            plugins_dir.mkdir()
            previous = plugins_dir / "codexbar-jetbrains-previous.zip"
            shutil.copy2(archive, previous)

            plugin, replaced = publish_plugin(
                archive,
                plugins_dir,
                expected_id=metadata.plugin_id,
                expected_version=metadata.version,
            )

            self.assertEqual(plugin.version, metadata.version)
            self.assertEqual(replaced, (previous,))
            self.assertFalse(previous.exists())
            self.assertTrue((plugins_dir / archive.name).is_file())

    def test_rejects_a_version_that_does_not_match_the_release(self) -> None:
        archive = codexbar_archive()
        with tempfile.TemporaryDirectory(prefix=".test-publish-", dir=ROOT) as temp:
            with self.assertRaisesRegex(ValueError, "expected plugin version"):
                publish_plugin(
                    archive,
                    Path(temp) / "plugins",
                    expected_version="definitely-not-the-published-version",
                )


if __name__ == "__main__":
    unittest.main()
