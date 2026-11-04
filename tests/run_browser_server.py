import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fitworld import create_app
from fitworld.db import migrate, get_db
from fitworld.catalog import seed_catalog
folder = tempfile.TemporaryDirectory()
app = create_app({'TESTING': True, 'SECRET_KEY': 'preview-only', 'DATABASE': str(Path(folder.name) / 'preview.sqlite3')})
with app.app_context():
    migrate()
    seed_catalog(get_db())
app.run(port=5057, debug=False)
