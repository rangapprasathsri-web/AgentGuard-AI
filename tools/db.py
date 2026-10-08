import os
import sqlite3


def init_tools_db(db_path: str = "tools.db") -> None:
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")

        # 1. customers_prod (50,000 rows)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers_prod (
                id INTEGER PRIMARY KEY,
                customer_name TEXT,
                email TEXT,
                national_id TEXT
            )
            """
        )
        cursor = conn.execute("SELECT COUNT(*) FROM customers_prod")
        if cursor.fetchone()[0] == 0:
            print("Seeding customers_prod (50,000 rows)...")
            batch = [
                (i, f"Customer_{i}", f"user_{i}@example.com", f"ID-{100000000000 + i}")
                for i in range(1, 50001)
            ]
            conn.executemany(
                "INSERT INTO customers_prod (id, customer_name, email, national_id) VALUES (?, ?, ?, ?)",
                batch,
            )

        # 2. customer_orders_db (2,000 rows)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_orders_db (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                amount INTEGER,
                order_date TEXT
            )
            """
        )
        cursor = conn.execute("SELECT COUNT(*) FROM customer_orders_db")
        if cursor.fetchone()[0] == 0:
            batch = [
                (i, (i % 1000) + 1, 100 + (i % 500), "2026-10-01")
                for i in range(1, 2001)
            ]
            conn.executemany(
                "INSERT INTO customer_orders_db (order_id, customer_id, amount, order_date) VALUES (?, ?, ?, ?)",
                batch,
            )

        # 3. staging_db (2,000 rows)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS staging_db (
                id INTEGER PRIMARY KEY,
                data TEXT,
                updated_at TEXT
            )
            """
        )
        cursor = conn.execute("SELECT COUNT(*) FROM staging_db")
        if cursor.fetchone()[0] == 0:
            batch = [(i, f"staging_data_{i}", "2026-10-01") for i in range(1, 2001)]
            conn.executemany(
                "INSERT INTO staging_db (id, data, updated_at) VALUES (?, ?, ?)",
                batch,
            )

        # 4. sales_db (1,000 rows)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sales_db (
                id INTEGER PRIMARY KEY,
                region TEXT,
                units_sold INTEGER,
                revenue INTEGER
            )
            """
        )
        cursor = conn.execute("SELECT COUNT(*) FROM sales_db")
        if cursor.fetchone()[0] == 0:
            batch = [
                (i, f"Region_{i % 5}", 10 + (i % 50), 1000 + (i * 10))
                for i in range(1, 1001)
            ]
            conn.executemany(
                "INSERT INTO sales_db (id, region, units_sold, revenue) VALUES (?, ?, ?, ?)",
                batch,
            )

        # 5. refunds table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refunds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT UNIQUE NOT NULL,
                customer_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # 6. deployments table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT NOT NULL,
                version TEXT NOT NULL,
                deployed_at TEXT NOT NULL
            )
            """
        )

        # 7. prod_database table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prod_database (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
            """
        )
        conn.execute("INSERT OR IGNORE INTO prod_database (id, name) VALUES (1, 'production_core')")

        conn.commit()
    finally:
        conn.close()


def reseed_tools_db(db_path: str = "tools.db") -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    init_tools_db(db_path)
