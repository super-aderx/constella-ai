"""Creates the tables the API writes to: `make migrate`.

It runs every file in app/infra/sql/schema in name order, in one transaction, so a statement
that fails leaves nothing half made. Each file creates only what is missing, so it is safe to
run again.
"""

import os

import psycopg

from app.infra.data import SQL


def main() -> None:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.transaction():
        for path in sorted((SQL / "schema").glob("*.sql")):
            # No parameters, so a file may hold several statements.
            conn.execute(path.read_text())
            print(f"Applied {path.name}")


if __name__ == "__main__":
    main()
