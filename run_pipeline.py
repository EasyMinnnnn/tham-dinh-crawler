import os
import subprocess
import time
import gspread
import json
from google.oauth2.service_account import Credentials

# ======== CONFIG ========
SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
CREDENTIALS = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
OUTPUT_DIR = "outputs"
SHEET2_NAME = os.getenv("SHEET2_NAME", "Trang tính2")

# ======== 1. RUN CRAWLER (main.py dùng Playwright) ========
print("🚀 Đang crawl link mới từ Playwright...")
subprocess.run(["python", "main.py"], check=True)

# ======== 2. LẤY LINK MỚI TRONG SHEET1 ========
print("📄 Đang đọc Google Sheet...")
creds = Credentials.from_service_account_info(CREDENTIALS, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID).sheet1

titles = sheet.col_values(1)
links = sheet.col_values(2)
latest_links = list(zip(titles, links))[:5]  # ⏳ Giới hạn 5 link mới nhất

print(f"🔗 Sẽ xử lý {len(latest_links)} link mới")

# ======== 3. VÒNG LẶP: DOWNLOAD → OCR → ĐẨY LÊN SHEET ========
for idx, (title, link) in enumerate(latest_links, 1):
    print(f"\n🟡 [{idx}] Xử lý: {title}")
    try:
        # Tải PDF
        subprocess.run(["python", "download_pdf.py", link], check=True)

        # Tìm file PDF vừa tải
        pdf_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".pdf")]
        if not pdf_files:
            print("❌ Không tìm thấy file PDF nào để OCR.")
            continue

        pdf_path = os.path.join(OUTPUT_DIR, pdf_files[0])

        # OCR
        subprocess.run(["python", "ocr_to_json.py", pdf_path], check=True)

        # Extract to Sheet
        subprocess.run(["python", "extract_to_sheet.py"], check=True)

        # Cleanup
        os.remove(pdf_path)
        print(f"🧹 Đã xóa {pdf_path}")
    except subprocess.CalledProcessError as e:
        print("❌ Lỗi khi xử lý pipeline:", e)

print("\n✅ Đã xử lý toàn bộ link mới.")
