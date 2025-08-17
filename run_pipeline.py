import os
import subprocess
import sqlite3
from typing import List, Tuple

# ======== CONFIG ========
CRAWL_YEAR = int(os.getenv("CRAWL_YEAR", "2025"))
OUTPUT_DIR = "outputs"
PIPELINE_LIMIT = int(os.getenv("PIPELINE_LIMIT", "5"))

# đường dẫn DB (trùng với src/db.py)
DB_PATH = "data.db"

# ======== UTILS ========
def fetch_personal_links(year: int, limit: int) -> List[Tuple[str, str]]:
    """
    Lấy link 'personal' theo năm từ bảng links (mới nhất trước).
    Trả về list[(title, url)].
    """
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH)
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
subprocess.run(["python", "src/crawl_links_and_classify.py"], check=False)

# ======== 2) LẤY LINK 'CÁ NHÂN' NĂM 2025 TỪ DB ========
links = fetch_personal_links(CRAWL_YEAR, PIPELINE_LIMIT)
print(f"🔗 Sẽ xử lý {len(links)} link 'Cá nhân' (năm {CRAWL_YEAR})")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ======== 3) VÒNG LẶP: DOWNLOAD → OCR+PARSE+UPSERT DB ========
for idx, (title, url) in enumerate(links, 1):
    print(f"\n🟡 [{idx}] {title}")
    try:
        # Tải PDF
        print("⬇️  Đang tải PDF…")
        subprocess.run(["python", "src/download_pdf.py", url], check=True)

        # Set nguồn để extract_to_db ghi vào DB (source_url)
        env = os.environ.copy()
        env["CURRENT_SOURCE_URL"] = url

        # OCR + parse + upsert DB (dùng Google Document AI trong extract_to_db.py)
        print("🧠  OCR & parse & ghi DB…")
        subprocess.run(["python", "src/extract_to_db.py"], check=True, env=env)

        # extract_to_db.py đã tự xóa PDF sau khi xử lý thành công.
        # Nếu bạn muốn dọn kỹ: xóa mọi file .pdf còn lại (trường hợp lỗi)
        leftover = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".pdf")]
        for f in leftover:
            try:
                os.remove(os.path.join(OUTPUT_DIR, f))
            except Exception:
                pass

        print("✅ Hoàn tất 1 link.")

    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi xử lý: {e}")

print("\n🎉 Pipeline kết thúc.")
