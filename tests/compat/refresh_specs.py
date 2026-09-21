"""Re-vendor the server OpenAPI specs at the SHAs pinned in manifest.json.
Usage: `python tests/compat/refresh_specs.py` (needs `gh` auth for the source repo)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

_DIR = Path(__file__).parent / "server_specs"


def main() -> None:
    manifest = json.loads((_DIR / "manifest.json").read_text())
    repo, path = manifest["source_repo"], manifest["source_path"]
    for entry in manifest["specs"]:
        content = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/contents/{path}?ref={entry['sha']}",
                "-H",
                "Accept: application/vnd.github.raw",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        (_DIR / entry["file"]).write_text(content)
        print(f"wrote {entry['file']} from {repo}@{entry['sha'][:12]}")


if __name__ == "__main__":
    main()
