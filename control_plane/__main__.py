"""python -m control_plane — launch the dashboard."""
from __future__ import annotations

from .app import app
from .config import SETTINGS


def main() -> None:
    print(
        f"[control_plane] serving on http://{SETTINGS.host}:{SETTINGS.port}\n"
        f"               repo_root  = {SETTINGS.repo_root}\n"
        f"               bridge     = {SETTINGS.bridge_root}\n"
        f"               db         = {SETTINGS.db_path}"
    )
    app.run(host=SETTINGS.host, port=SETTINGS.port, debug=SETTINGS.debug, use_reloader=False)


if __name__ == "__main__":
    main()
