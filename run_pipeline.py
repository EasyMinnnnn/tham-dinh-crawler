import os
import sys
import sqlite3
import subprocess
from pathlib import Path
from typing import List, Tuple

# ========= CONFIG =========
CRAWL_YEAR = int(os.getenv("CRAWL_YEAR", "2025"))
PIPELINE_LIMIT = int(os.getenv("PIPELINE_LIMIT", "5"))

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data.db"
OUTPUT_DIR = ROOT / "outputs"

# Đường dẫn script
CRAWLER    = ROOT / "src" / "crawl_links_and_classify.py"  # trong src
DOWNLOADER = ROOT / "download_pdf.py"                       # ở root
EXTRACTOR  = ROOT / "src" / "extract_to_db.py"              # trong src

def run_cmd(script: Path | str, args: list[str] | None = None, env=None, title: str = ""):
    """Chạy 1 script Python với cùng interpreter, CWD=repo root; in log đầy đủ."""
    if title:
        print(title)
    cmd = [sys.executable, str(script)]
    if args:
        cmd.extend(args)
    proc = subprocess.run(
        cmd,
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
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return proc

def fetch_personal_links(year: int, limit: int) -> List[Tuple[str, str]]:
    """Lấy (title, url) của link 'personal' theo năm từ SQLite."""
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
    run_cmd(CRAWLER, title="🚀 Đang crawl link mới bằng Playwright (ghi vào SQLite)…")
except subprocess.CalledProcessError:
    print("⚠️ Crawler lỗi, tiếp tục pipeline…")

# 2) Lấy link personal năm 2025
links = fetch_personal_links(CRAWL_YEAR, PIPELINE_LIMIT)
print(f"🔗 Sẽ xử lý {len(links)} link 'Cá nhân' (năm {CRAWL_YEAR})")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 3) Download -> OCR + parse + upsert DB
for idx, (title, url) in enumerate(links, 1):
    print(f"\n🟡 [{idx}] {title}")
    try:
        # Tải PDF
        run_cmd(DOWNLOADER, [url], title="⬇️  Đang tải PDF…")

        # Truyền nguồn cho extractor để ghi vào DB
        env = os.environ.copy()
        env["CURRENT_SOURCE_URL"] = url

        # OCR + parse + ghi DB (Google Document AI được dùng trong extract_to_db.py)
        run_cmd(EXTRACTOR, env=env, title="🧠  OCR & parse & ghi DB…")

        # Dọn file PDF còn sót (extractor đã xóa khi thành công)
        for f in OUTPUT_DIR.glob("*.pdf"):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

        print("✅ Hoàn tất 1 link.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi xử lý: {e}")

print("\n🎉 Pipeline kết thúc.")
