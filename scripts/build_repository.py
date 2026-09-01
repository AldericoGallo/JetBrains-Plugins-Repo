#!/usr/bin/env python3
"""Build a static JetBrains plugin repository from distribution archives."""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse


@dataclass(frozen=True)
class PluginMetadata:
    plugin_id: str
    version: str
    name: str
    description: str
    change_notes: str
    vendor: str
    since_build: str
    until_build: str | None
    dependencies: tuple[str, ...]
    archive_path: Path
    sha256: str
    size: int


def _element_text(root: ET.Element, tag: str, *, required: bool = False) -> str:
    element = root.find(tag)
    value = "" if element is None else "".join(element.itertext()).strip()
    if required and not value:
        raise ValueError(f"plugin.xml is missing a non-empty <{tag}> element")
    return value


def _plugin_xml_from_archive(archive_path: Path) -> bytes:
    try:
        with zipfile.ZipFile(archive_path) as distribution:
            if "META-INF/plugin.xml" in distribution.namelist():
                return distribution.read("META-INF/plugin.xml")

            jar_names = sorted(
                name
                for name in distribution.namelist()
                if name.lower().endswith(".jar")
                and "searchableoptions" not in name.lower()
            )
            for jar_name in jar_names:
                try:
                    with zipfile.ZipFile(io.BytesIO(distribution.read(jar_name))) as jar:
                        if "META-INF/plugin.xml" in jar.namelist():
                            return jar.read("META-INF/plugin.xml")
                except zipfile.BadZipFile:
                    continue
    except zipfile.BadZipFile as error:
        raise ValueError(f"{archive_path} is not a valid ZIP/JAR archive") from error

    raise ValueError(f"could not find META-INF/plugin.xml inside {archive_path}")


def read_plugin_metadata(archive_path: Path) -> PluginMetadata:
    try:
        root = ET.fromstring(_plugin_xml_from_archive(archive_path))
    except ET.ParseError as error:
        raise ValueError(f"invalid plugin.xml inside {archive_path}: {error}") from error

    idea_version = root.find("idea-version")
    if idea_version is None or not idea_version.get("since-build"):
        raise ValueError(
            f"plugin.xml inside {archive_path} is missing idea-version@since-build"
        )

    plugin_id = _element_text(root, "id", required=True)
    version = _element_text(root, "version", required=True)
    name = _element_text(root, "name") or plugin_id
    dependencies = tuple(
        dependency.text.strip()
        for dependency in root.findall("depends")
        if dependency.text and dependency.text.strip()
    )

    digest = hashlib.sha256()
    with archive_path.open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(chunk)

    return PluginMetadata(
        plugin_id=plugin_id,
        version=version,
        name=name,
        description=_element_text(root, "description"),
        change_notes=_element_text(root, "change-notes"),
        vendor=_element_text(root, "vendor"),
        since_build=idea_version.get("since-build", ""),
        until_build=idea_version.get("until-build"),
        dependencies=dependencies,
        archive_path=archive_path,
        sha256=digest.hexdigest(),
        size=archive_path.stat().st_size,
    )


def _validate_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    parsed = urlparse(normalized)
    if not parsed.netloc or parsed.scheme not in {"http", "https"}:
        raise ValueError("base URL must be an absolute HTTP(S) URL")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("JetBrains download URLs must use HTTPS")
    return normalized


def _prepare_output(output_dir: Path, plugins_dir: Path) -> None:
    output = output_dir.resolve()
    workspace = Path.cwd().resolve()
    plugins = plugins_dir.resolve()
    if output == workspace or output == plugins or not output.is_relative_to(workspace):
        raise ValueError("output directory must be a dedicated directory inside the workspace")
    if output.exists():
        shutil.rmtree(output)
    (output / "plugins").mkdir(parents=True)


def _write_plugins_xml(
    plugins: list[PluginMetadata], output_dir: Path, base_url: str
) -> None:
    root = ET.Element("plugins")
    for plugin in plugins:
        filename = quote(plugin.archive_path.name)
        entry = ET.SubElement(
            root,
            "plugin",
            {
                "id": plugin.plugin_id,
                "url": f"{base_url}/plugins/{filename}",
                "version": plugin.version,
            },
        )
        idea_attributes = {"since-build": plugin.since_build}
        if plugin.until_build:
            idea_attributes["until-build"] = plugin.until_build
        ET.SubElement(entry, "idea-version", idea_attributes)
        ET.SubElement(entry, "name").text = plugin.name
        if plugin.description:
            ET.SubElement(entry, "description").text = plugin.description
        if plugin.change_notes:
            ET.SubElement(entry, "change-notes").text = plugin.change_notes
        for dependency in plugin.dependencies:
            ET.SubElement(entry, "depends").text = dependency

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(
        output_dir / "updatePlugins.xml",
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def _plugin_cards(plugins: list[PluginMetadata], base_url: str) -> str:
    cards: list[str] = []
    for plugin in plugins:
        name = html.escape(plugin.name)
        version = html.escape(plugin.version)
        plugin_id = html.escape(plugin.plugin_id)
        description = html.escape(plugin.description or "No description provided.")
        vendor = html.escape(plugin.vendor or "Unknown vendor")
        since = html.escape(plugin.since_build)
        compatibility = f"JetBrains build {since}+"
        if plugin.until_build:
            compatibility += f" through {html.escape(plugin.until_build)}"
        download_url = f"{base_url}/plugins/{quote(plugin.archive_path.name)}"
        cards.append(
            f"""
            <article class="plugin-card">
              <div class="plugin-heading">
                <div>
                  <p class="eyebrow">{vendor}</p>
                  <h3>{name}</h3>
                </div>
                <span class="version">v{version}</span>
              </div>
              <p>{description}</p>
              <dl>
                <div><dt>Plugin ID</dt><dd><code>{plugin_id}</code></dd></div>
                <div><dt>Compatibility</dt><dd>{compatibility}</dd></div>
                <div><dt>Archive</dt><dd>{_human_size(plugin.size)}</dd></div>
              </dl>
              <details>
                <summary>SHA-256 checksum</summary>
                <code class="checksum">{plugin.sha256}</code>
              </details>
              <a class="download" href="{html.escape(download_url)}">Download archive</a>
            </article>"""
        )
    return "\n".join(cards)


def _write_index(plugins: list[PluginMetadata], output_dir: Path, base_url: str) -> None:
    repository_url = f"{base_url}/updatePlugins.xml"
    page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Custom JetBrains plugin repository">
  <title>JetBrains Plugin Repository</title>
  <style>
    :root { color-scheme: dark; --ink: #f7f7f2; --muted: #a7a8b2; --line: #30323c; --panel: #181920; --accent: #9dff63; --purple: #a58cff; }
    * { box-sizing: border-box; }
    body { margin: 0; color: var(--ink); background: radial-gradient(circle at 15% 0, #30245b 0, transparent 28rem), #0d0e12; font: 16px/1.6 Inter, ui-sans-serif, system-ui, sans-serif; }
    main { width: min(1080px, calc(100% - 2rem)); margin: 0 auto; padding: 5rem 0; }
    .hero { max-width: 820px; margin-bottom: 4rem; }
    .eyebrow { margin: 0 0 .4rem; color: var(--accent); font-size: .76rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
    h1 { margin: 0; font-size: clamp(2.7rem, 8vw, 5.8rem); line-height: .98; letter-spacing: -.06em; }
    h2 { margin: 0 0 1.4rem; font-size: 1.7rem; }
    h3 { margin: 0; font-size: 1.45rem; }
    .lede { max-width: 680px; margin: 1.5rem 0 2rem; color: #cfd0d7; font-size: 1.12rem; }
    .repo-box { display: flex; gap: .7rem; padding: .65rem; border: 1px solid var(--line); border-radius: 14px; background: rgba(24, 25, 32, .9); }
    .repo-box code { min-width: 0; flex: 1; padding: .55rem .7rem; overflow-x: auto; white-space: nowrap; }
    button, .download { border: 0; border-radius: 9px; background: var(--accent); color: #11150e; font: inherit; font-weight: 800; cursor: pointer; text-decoration: none; }
    button { padding: .5rem 1rem; }
    section { margin-top: 4rem; }
    .steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; padding: 0; list-style: none; counter-reset: step; }
    .steps li { position: relative; padding: 3rem 1.25rem 1.25rem; border: 1px solid var(--line); border-radius: 15px; background: var(--panel); counter-increment: step; }
    .steps li::before { position: absolute; top: 1rem; content: "0" counter(step); color: var(--purple); font-weight: 900; }
    .plugins { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 1rem; }
    .plugin-card { display: flex; flex-direction: column; gap: 1rem; padding: 1.4rem; border: 1px solid var(--line); border-radius: 18px; background: linear-gradient(145deg, #1c1d25, #14151a); }
    .plugin-card > p { margin: 0; color: #c5c6ce; }
    .plugin-heading { display: flex; justify-content: space-between; gap: 1rem; }
    .version { align-self: start; padding: .2rem .55rem; border: 1px solid #555167; border-radius: 99px; color: #d9d0ff; font-size: .8rem; }
    dl { display: grid; gap: .45rem; margin: 0; }
    dl div { display: grid; grid-template-columns: 7.5rem 1fr; gap: .5rem; }
    dt { color: var(--muted); }
    dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }
    details { color: var(--muted); font-size: .82rem; }
    .checksum { display: block; margin-top: .4rem; overflow-wrap: anywhere; color: #d8d9df; }
    .download { align-self: start; margin-top: auto; padding: .55rem .85rem; }
    footer { margin-top: 5rem; padding-top: 1.5rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .9rem; }
    @media (max-width: 760px) { main { padding-top: 3rem; } .steps { grid-template-columns: 1fr 1fr; } .repo-box { align-items: stretch; flex-direction: column; } }
    @media (max-width: 480px) { .steps { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <header class="hero">
      <p class="eyebrow">Custom repository</p>
      <h1>JetBrains plugins,<br>served directly.</h1>
      <p class="lede">Add the repository URL to any compatible JetBrains IDE to install the plugins below and receive future updates.</p>
      <div class="repo-box">
        <code>%%REPOSITORY_URL%%</code>
        <button type="button" data-url="%%REPOSITORY_URL%%">Copy URL</button>
      </div>
    </header>

    <section aria-labelledby="install-title">
      <h2 id="install-title">Install in your IDE</h2>
      <ol class="steps">
        <li>Open <strong>Settings → Plugins</strong>.</li>
        <li>Open the gear menu and choose <strong>Manage Plugin Repositories</strong>.</li>
        <li>Add the repository URL shown above.</li>
        <li>Find the plugin on the Marketplace tab and install it.</li>
      </ol>
    </section>

    <section aria-labelledby="plugins-title">
      <h2 id="plugins-title">Available plugins</h2>
      <div class="plugins">%%PLUGIN_CARDS%%</div>
    </section>

    <footer>The repository index is generated from the metadata embedded in each published plugin archive.</footer>
  </main>
  <script>
    const button = document.querySelector('[data-url]');
    button.addEventListener('click', async () => {
      await navigator.clipboard.writeText(button.dataset.url);
      button.textContent = 'Copied';
      window.setTimeout(() => { button.textContent = 'Copy URL'; }, 1800);
    });
  </script>
</body>
</html>
"""
    page = page.replace("%%REPOSITORY_URL%%", html.escape(repository_url))
    page = page.replace("%%PLUGIN_CARDS%%", _plugin_cards(plugins, base_url))
    (output_dir / "index.html").write_text(page, encoding="utf-8")


def build_repository(plugins_dir: Path, output_dir: Path, base_url: str) -> list[PluginMetadata]:
    base_url = _validate_base_url(base_url)
    archives = sorted(
        path
        for path in plugins_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".zip", ".jar"}
    )
    if not archives:
        raise ValueError(f"no ZIP or JAR plugin archives found in {plugins_dir}")

    plugins = sorted(
        (read_plugin_metadata(archive) for archive in archives),
        key=lambda plugin: (plugin.name.casefold(), plugin.plugin_id),
    )
    seen: set[str] = set()
    for plugin in plugins:
        if plugin.plugin_id in seen:
            raise ValueError(
                f"plugin ID {plugin.plugin_id!r} appears more than once; keep only its latest archive"
            )
        seen.add(plugin.plugin_id)

    _prepare_output(output_dir, plugins_dir)
    for plugin in plugins:
        shutil.copy2(plugin.archive_path, output_dir / "plugins" / plugin.archive_path.name)
    _write_plugins_xml(plugins, output_dir, base_url)
    _write_index(plugins, output_dir, base_url)
    (output_dir / ".nojekyll").touch()
    return plugins


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="public URL of the Pages site")
    parser.add_argument("--plugins-dir", type=Path, default=Path("plugins"))
    parser.add_argument("--output-dir", type=Path, default=Path("_site"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        plugins = build_repository(args.plugins_dir, args.output_dir, args.base_url)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Built repository with {len(plugins)} plugin(s) in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
