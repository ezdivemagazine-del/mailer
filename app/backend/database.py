import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "../../data/mailer.db"))


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT NOT NULL UNIQUE,
            password   TEXT NOT NULL,
            role       TEXT NOT NULL DEFAULT 'member',
            active     INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS smtp_accounts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            label        TEXT NOT NULL,
            host         TEXT NOT NULL DEFAULT '',
            port         INTEGER NOT NULL DEFAULT 465,
            username     TEXT NOT NULL,
            password     TEXT NOT NULL,
            channel_type TEXT NOT NULL DEFAULT 'smtp',
            verified     INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS send_jobs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            subject        TEXT NOT NULL,
            body           TEXT NOT NULL,
            send_mode      TEXT NOT NULL DEFAULT 'individual',
            smtp_id        INTEGER REFERENCES smtp_accounts(id),
            throttle_min   INTEGER DEFAULT 5,
            throttle_count INTEGER DEFAULT 50,
            status         TEXT DEFAULT 'pending',
            total          INTEGER DEFAULT 0,
            sent           INTEGER DEFAULT 0,
            failed         INTEGER DEFAULT 0,
            created_by     INTEGER REFERENCES users(id),
            created_at     TEXT DEFAULT (datetime('now')),
            updated_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS send_recipients (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id  INTEGER REFERENCES send_jobs(id),
            email   TEXT NOT NULL,
            status  TEXT DEFAULT 'pending',
            error   TEXT,
            sent_at TEXT
        );

        CREATE TABLE IF NOT EXISTS user_smtp (
            user_id  INTEGER REFERENCES users(id),
            smtp_id  INTEGER REFERENCES smtp_accounts(id),
            PRIMARY KEY (user_id, smtp_id)
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            subject        TEXT NOT NULL,
            body           TEXT NOT NULL,
            recipients     TEXT NOT NULL,
            send_mode      TEXT DEFAULT 'individual',
            smtp_id        INTEGER REFERENCES smtp_accounts(id),
            throttle_min   INTEGER DEFAULT 5,
            throttle_count INTEGER DEFAULT 50,
            interval_days  INTEGER NOT NULL,
            next_run       TEXT NOT NULL,
            active         INTEGER DEFAULT 1,
            created_by     INTEGER REFERENCES users(id),
            created_at     TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # 建立預設 admin 帳號（若不存在或密碼欄位為空）
    from .auth import hash_password, verify_password
    existing = conn.execute("SELECT id, password FROM users WHERE username='admin'").fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, 'admin')",
            ("admin", hash_password("admin1234"))
        )
        conn.commit()
    elif not existing["password"] or len(existing["password"]) < 20:
        conn.execute("UPDATE users SET password=? WHERE username='admin'", (hash_password("admin1234"),))
        conn.commit()

    conn.close()
