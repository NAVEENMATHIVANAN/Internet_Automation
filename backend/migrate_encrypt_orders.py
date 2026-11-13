import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.database import engine
from app.services.encrypted_json_service import (
    PREFIX,
    encrypt_json,
)

COLUMNS = (
    "customer_data",
    "service_address",
    "order_data",
    "qualification",
    "installation",
    "disclosures",
)


def main():
    db_path = Path(engine.url.database).resolve()

    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found: {db_path}"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(
        f"{db_path.stem}_backup_{timestamp}.db"
    )

    connection = sqlite3.connect(str(db_path))

    try:
        # SQLite's backup API creates a consistent backup.
        with sqlite3.connect(str(backup_path)) as backup:
            connection.backup(backup)

        print(f"Backup created: {backup_path}")

        # Acquire the write lock before checking and updating rows.
        connection.execute("BEGIN IMMEDIATE")

        rows = connection.execute(
            "SELECT id, " + ", ".join(COLUMNS) + " FROM orders"
        ).fetchall()

        migrated = 0

        for row in rows:
            order_id = row[0]
            updates = {}

            for column, value in zip(COLUMNS, row[1:]):
                if value is None:
                    raise ValueError(
                        f"Order {order_id}: {column} is NULL"
                    )

                if isinstance(value, str) and value.startswith(PREFIX):
                    continue

                # Validate existing JSON before encrypting.
                parsed = json.loads(value)

                updates[column] = encrypt_json(parsed)

            if not updates:
                continue

            assignments = ", ".join(
                f"{column} = ?" for column in updates
            )

            connection.execute(
                f"UPDATE orders SET {assignments} WHERE id = ?",
                (*updates.values(), order_id),
            )

            migrated += 1

        connection.commit()

        print(f"Migration successful: {migrated} orders updated")
        print(f"Total orders examined: {len(rows)}")

    except Exception:
        connection.rollback()
        print("Migration failed. Changes rolled back.")
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()