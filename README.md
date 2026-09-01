# JetBrains Plugin Repository

A static custom JetBrains plugin repository designed for GitHub Pages. The deployment workflow reads each plugin's embedded `plugin.xml`, builds the required `updatePlugins.xml` feed, copies the distributions, and publishes an installation page.

The repository currently publishes CodexBar 0.0.2 (`it.aldericogallo.codexbar-jetbrains`) for JetBrains platform build 262 and later.

## Publish on GitHub Pages

1. Create a GitHub repository and push these files to its `main` branch.
2. Open **Settings → Pages** in GitHub.
3. Under **Build and deployment**, select **GitHub Actions** as the source.
4. Run the **Deploy plugin repository** workflow, or push another commit to `main`.

After deployment, the repository URL shown on the published landing page will normally be:

```text
https://<owner>.github.io/<repository>/updatePlugins.xml
```

For a repository named `<owner>.github.io`, it will instead be at the account-site root. Custom domains are also handled automatically.

## Install a plugin

1. In a JetBrains IDE, open **Settings → Plugins**.
2. Open the gear menu and select **Manage Plugin Repositories**.
3. Add the full `updatePlugins.xml` URL from the published site.
4. Return to the Marketplace tab, find the plugin, and install it.

## Publish another plugin

Add its ZIP or JAR distribution to [`plugins/`](plugins/) and push to `main`. Metadata is taken directly from `META-INF/plugin.xml`; there is no separate catalog to edit.

Each plugin ID can appear only once in the generated feed. When publishing a new version, replace the older archive for that plugin ID. Different plugins can be published together.

The `scripts/publish_plugin.py` helper performs that replacement safely by reading the incoming and existing archives' embedded plugin IDs. A plugin source repository can use it after checking out this repository:

```bash
python3 scripts/publish_plugin.py \
  --archive /path/to/new-plugin.zip \
  --expected-id com.example.plugin \
  --expected-version 1.2.3
```

CodexBar's tag-release workflow uses this mechanism to commit new distributions automatically. The commit then triggers the Pages deployment workflow.

## Build locally

The builder has no third-party dependencies and supports Python 3.9 or later:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_repository.py --base-url http://localhost:8000
python3 -m http.server --directory _site 8000
```

Then open <http://localhost:8000>. Production repository and download URLs are required to use HTTPS.
