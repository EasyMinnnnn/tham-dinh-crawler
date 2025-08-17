import sqlite3
from contextlib import contextmanager

DB_PATH = "data.db"

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_schema():
    with get_conn() as conn:
        # Link đã crawl
        conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url   TEXT NOT NULL UNIQUE,
            bucket TEXT NOT NULL, -- 'personal' | 'company'
            year  INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        # Bảng cá nhân (theo số thẻ)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS personal_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_no TEXT NOT NULL UNIQUE,
            full_name TEXT,
            position TEXT,
            company  TEXT,
            valid_from TEXT,
            doc_no TEXT,      -- số hiệu văn bản (VD: 622/TB-BTC)
            signed_at TEXT,   -- ngày văn bản
            source_url TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        # Quyết định cho doanh nghiệp/công ty
        conn.execute("""
        CREATE TABLE IF NOT EXISTS company_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT,
            decision_no  TEXT,
            decision_type TEXT,  -- 'thu hồi' | 'đình chỉ' | ...
            effective_date TEXT,
            source_url TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
