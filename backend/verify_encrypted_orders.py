import sqlite3

from app.database import engine
from app.services.encrypted_json_service import PREFIX

COLUMNS = (
    "customer_data",
    "service_address",
    "order_data",
    "qualification",
    "installation",
    "disclosures",
)

db_path = engine.url.database

with sqlite3.connect(db_path) as connection:
    rows = connection.execute(
        "SELECT " + ", ".join(COLUMNS) + " FROM orders"
    ).fetchall()

    for row in rows:
        for value in row:
            assert isinstance(value, str)
            assert value.startswith(PREFIX)

print(f"PASS: All six JSON fields encrypted in {len(rows)} orders")