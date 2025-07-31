import os
import json
import time
import requests
import subprocess
from urllib.parse import urljoin
from pathlib import Path
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# ==== Load Google Sheet ====
sheet_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
sheet_id = os.environ.get("GOOGLE_SHEET_ID")
if not sheet_json or not sheet_id:
    print("❌ Thiếu GOOGLE_CREDENTIALS_JSON hoặc GOOGLE_SHEET_ID.")
    exit(1)

creds_dict = json.loads(sheet_json)
creds = Credentials.from_service_account_info(creds_dict)
sheet = build("sheets", "v4", credentials=creds).spreadsheets()

# ==== Load Links ====
result = sheet.values().get(spreadsheetId=sheet_id, range="Tonghop!A2:B").execute()
rows = result.get("values", [])

if not rows:
    print("❌ Không có link nào trong sheet 'Tonghop'.")
    exit(0)

print(f"🔗 Tổng số link trong sheet: {len(rows)}")

# ==== Lặp và xử lý từng link ====
processed = 0
for idx, row in enumerate(rows):
    if len(row) < 2:
        continue
    url, category = row[0], row[1].lower()
    if category not in ["điều chỉnh", "thu hồi"]:
        print(f"⏭️ Bỏ qua link không thuộc nhóm xử lý: {url}")
        continue

    print(f"\n📄 ({processed+1}) Đang xử lý: {url} [{category}]")

    try:
        subprocess.run(["python", "download_pdf.py", url], check=True)
        time.sleep(1)

        output_dir = Path("outputs")
        pdf_files = list(output_dir.glob("*.pdf"))
        if not pdf_files:
            print("❌ Không tìm thấy file PDF.")
            continue

        latest_pdf = max(pdf_files, key=os.path.getmtime)

        # 🔁 OCR bằng đúng luồng xử lý theo loại
        if category == "điều chỉnh":
            subprocess.run(["python", "ocr_to_json.py", str(latest_pdf)], check=True)
        elif category == "thu hồi":
            subprocess.run(["python", "extract_to_sheet.py", str(latest_pdf)], check=True)

        processed += 1

    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi xử lý link {url}: {e}")
        continue

print(f"\n✅ Đã xử lý xong {processed} link phù hợp.")
