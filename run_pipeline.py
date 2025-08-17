import os
import sys
import sqlite3
import subprocess
from pathlib import Path
from typing import List, Tuple

# ======== CONFIG ========
CRAWL_YEAR = int(os.getenv("CRAWL_YEAR", "2025"))
OUTPUT_DIR = "outputs"
PIPELINE_LIMIT = int(os.getenv("PIPELINE_LIMIT", "5"))

# Paths
ROOT = Path(__file__).resolve().parent                       # repo root
DB_PATH = ROOT / "data.db"
CRAWLER = ROOT / "src" / "crawl_links_and_classify.py"       # trong src
DOWNLOADER = ROOT / "download_pdf.py"                         # ở THƯ MỤC GỐC
EXTRACTOR = ROOT / "src" / "extract_to_db.py"                 # trong src

def run_cmd(args: list[str], env=None) -> subprocess.CompletedProcess:
    """Run a command using the same Python interpreter + repo root cwd."""
    return subprocess.run([sys.executable] + [str(a) for a in args],
                          cwd=str(ROOT),
                          env=env or os.environ.copy(),
                          text=True,
                          capture_output=False,
                          check=True)

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
        rows = cur.fetchall()
        return [(r[0], r[1]) for r in rows]
    finally:
        conn.close()

# ======== 1) RUN CRAWLER ========
print("🚀 Đang crawl link mới bằng Playwright (ghi vào SQLite)…")
try:
    run_cmd([CRAWLER])
except subprocess.CalledProcessError as e:
    print(f"⚠️ Crawler lỗi (tiếp tục pipeline): {e}")

# ======== 2) LẤY LINK 'CÁ NHÂN' NĂM 2025 TỪ DB ========
links = fetch_personal_links(CRAWL_YEAR, PIPELINE_LIMIT)
print(f"🔗 Sẽ xử lý {len(links)} link 'Cá nhân' (năm {CRAWL_YEAR})")

os.makedirs(ROOT / OUTPUT_DIR, exist_ok=True)

# ======== 3) VÒNG LẶP: DOWNLOAD → OCR+PARSE+UPSERT DB ========
for idx, (title, url) in enumerate(links, 1):
    print(f"\n🟡 [{idx}] {title}")
    try:
        print("⬇️  Đang tải PDF…")
        run_cmd([DOWNLOADER, url])

        # Truyền nguồn cho extractor ghi vào DB
        env = os.environ.copy()
        env["CURRENT_SOURCE_URL"] = url

        print("🧠  OCR & parse & ghi DB…")
        run_cmd([EXTRACTOR], env=env)

        # Xoá PDF còn sót (extractor đã xoá khi thành công)
        for f in (ROOT / OUTPUT_DIR).glob("*.pdf"):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

        print("✅ Hoàn tất 1 link.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi xử lý: {e}")

print("\n🎉 Pipeline kết thúc.")
