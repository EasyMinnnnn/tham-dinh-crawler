import os
import sys
import sqlite3
import subprocess
from pathlib import Path
from typing import List, Tuple

CRAWL_YEAR = int(os.getenv("CRAWL_YEAR", "2025"))
OUTPUT_DIR = "outputs"
PIPELINE_LIMIT = int(os.getenv("PIPELINE_LIMIT", "5"))

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data.db"

DOWNLOADER = ROOT / "download_pdf.py"  # ở root

def run_cmd(args: list[str], env=None, title=""):
    """Run command using this interpreter, show full logs on error."""
    if title:
        print(title)
    proc = subprocess.run(
        [sys.executable] + args,
        cwd=str(ROOT),
        env=env or os.environ.copy(),
        text=True,
        capture_output=True,
    )
    if proc.stdout:
        print(proc.stdout)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr)
        raise subprocess.CalledProcessError(proc.returncode, args)
    return proc

def fetch_personal_links(year: int, limit: int) -> List[Tuple[str, str]]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT title, url
            FROM links
            WHERE year = ? AND bucket = 'personal'
            ORDER BY id DESC
            LIMIT ?
            """,
            (year, limit),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]
    finally:
        conn.close()

# 1) Crawl -> ghi SQLite
try:
    run_cmd(["-m", "src.crawl_links_and_classify"], title="🚀 Đang crawl link mới bằng Playwright (ghi vào SQLite)…")
except subprocess.CalledProcessError:
    print("⚠️ Crawler lỗi, tiếp tục pipeline…")

# 2) Lấy link personal năm 2025
links = fetch_personal_links(CRAWL_YEAR, PIPELINE_LIMIT)
print(f"🔗 Sẽ xử lý {len(links)} link 'Cá nhân' (năm {CRAWL_YEAR})")
os.makedirs(ROOT / OUTPUT_DIR, exist_ok=True)

# 3) Download -> OCR+parse+upsert DB
for idx, (title, url) in enumerate(links, 1):
    print(f"\n🟡 [{idx}] {title}")
    try:
        run_cmd([str(DOWNLOADER), url], title="⬇️  Đang tải PDF…")

        env = os.environ.copy()
        env["CURRENT_SOURCE_URL"] = url
        run_cmd(["-m", "src.extract_to_db"], env=env, title="🧠  OCR & parse & ghi DB…")

        # dọn pdf thừa
        for f in (ROOT / OUTPUT_DIR).glob("*.pdf"):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

        print("✅ Hoàn tất 1 link.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi xử lý: {e}")

print("\n🎉 Pipeline kết thúc.")
