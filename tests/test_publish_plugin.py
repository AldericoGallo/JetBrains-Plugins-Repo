from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from publish_plugin import publish_plugin  # noqa: E402


ARCHIVE = ROOT / "plugins" / "codexbar-jetbrains-0.0.2.zip"


class PublishPluginTests(unittest.TestCase):
    def test_replaces_archive_with_the_same_plugin_id(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".test-publish-", dir=ROOT) as temp:
            plugins_dir = Path(temp) / "plugins"
            plugins_dir.mkdir()
            previous = plugins_dir / "codexbar-jetbrains-previous.zip"
            shutil.copy2(ARCHIVE, previous)

            plugin, replaced = publish_plugin(
                ARCHIVE,
                plugins_dir,
                expected_id="it.aldericogallo.codexbar-jetbrains",
                expected_version="0.0.2",
            )

            self.assertEqual(plugin.version, "0.0.2")
            self.assertEqual(replaced, (previous,))
            self.assertFalse(previous.exists())
            self.assertTrue((plugins_dir / ARCHIVE.name).is_file())

    def test_rejects_a_version_that_does_not_match_the_release(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".test-publish-", dir=ROOT) as temp:
            with self.assertRaisesRegex(ValueError, "expected plugin version"):
                publish_plugin(
                    ARCHIVE,
                    Path(temp) / "plugins",
                    expected_version="9.9.9",
                )


if __name__ == "__main__":
    unittest.main()
