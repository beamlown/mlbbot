"""python -m dugout_dash.run — start the live dashboard."""
from __future__ import annotations
import logging
from dugout_dash import create_app
from dugout_dash.config import HOST, PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DUGOUT] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    app = create_app()
    app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
