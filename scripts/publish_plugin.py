#!/usr/bin/env python3
"""Replace a plugin's published archive using its embedded plugin ID."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from build_repository import PluginMetadata, read_plugin_metadata


def publish_plugin(
    archive_path: Path,
    plugins_dir: Path,
    *,
    expected_id: str | None = None,
    expected_version: str | None = None,
) -> tuple[PluginMetadata, tuple[Path, ...]]:
    if not archive_path.is_file() or archive_path.suffix.lower() not in {".zip", ".jar"}:
        raise ValueError(f"plugin archive does not exist or is not a ZIP/JAR: {archive_path}")

    incoming = read_plugin_metadata(archive_path)
    if expected_id and incoming.plugin_id != expected_id:
        raise ValueError(
            f"expected plugin ID {expected_id!r}, found {incoming.plugin_id!r}"
        )
    if expected_version and incoming.version != expected_version:
        raise ValueError(
            f"expected plugin version {expected_version!r}, found {incoming.version!r}"
        )

    plugins_dir.mkdir(parents=True, exist_ok=True)
    existing_archives = sorted(
        path
        for path in plugins_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".zip", ".jar"}
    )
    replaced: list[Path] = []
    for existing_archive in existing_archives:
        existing = read_plugin_metadata(existing_archive)
        if existing.plugin_id == incoming.plugin_id:
            replaced.append(existing_archive)

    destination = plugins_dir / archive_path.name
    if destination.exists() and destination not in replaced:
        raise ValueError(
            f"cannot overwrite {destination}: it belongs to a different plugin ID"
        )

    temporary = plugins_dir / f".{archive_path.name}.tmp"
    shutil.copy2(archive_path, temporary)
    for old_archive in replaced:
        if old_archive != destination:
            old_archive.unlink()
    temporary.replace(destination)

    return incoming, tuple(replaced)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--plugins-dir", type=Path, default=Path("plugins"))
    parser.add_argument("--expected-id")
    parser.add_argument("--expected-version")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        plugin, replaced = publish_plugin(
            args.archive,
            args.plugins_dir,
            expected_id=args.expected_id,
            expected_version=args.expected_version,
        )
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    previous = ", ".join(path.name for path in replaced) or "none"
    print(
        f"Published {plugin.name} {plugin.version} ({plugin.plugin_id}); "
        f"replaced: {previous}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
