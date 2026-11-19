"""Run optional headless checks against isolated, disposable local data."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fitworld import create_app
from fitworld.catalog import seed_catalog
from fitworld.db import get_db, migrate


def main():
    with tempfile.TemporaryDirectory(prefix="fitworld-browser-") as folder:
        app = create_app(
            {"TESTING": True, "SESSION_COOKIE_NAME": "fitworld_browser_test"},
            instance_path=folder,
        )
        with app.app_context():
            migrate()
            seed_catalog(get_db())
        app.run(host="127.0.0.1", port=5057, debug=False)


if __name__ == "__main__":
    main()
