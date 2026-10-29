"""Request-scoped SQLite connections and forward-only schema migrations."""

import sqlite3
from pathlib import Path

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def migrate():
    connection = get_db()
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    connection.commit()
    applied = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations")}
    for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
        if path.name not in applied:
            # Files are trusted repository SQL; changes and version record commit together.
            script = path.read_text()
            version = path.name.replace("'", "''")
            try:
                connection.executescript(
                    f"BEGIN IMMEDIATE;\n{script}\n"
                    f"INSERT INTO schema_migrations (version) VALUES ('{version}');\nCOMMIT;"
                )
            except sqlite3.Error:
                connection.rollback()
                raise


@click.command("init-db")
def init_db_command():
    """Apply pending migrations without deleting existing data."""
    migrate()
    from .catalog import seed_catalog
    seed_catalog(get_db())
    click.echo("Database is up to date. Missing starter catalog entries have been added.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
