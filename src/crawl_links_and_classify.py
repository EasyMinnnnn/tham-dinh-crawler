import os
import json
import re
from playwright.sync_api import sync_playwright
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# ✨ Constants
BASE_URL = "https://mof.gov.vn"
START_PATH = "/bo-tai-chinh/danh-sach-tham-dinh-ve-gia"
FULL_URL = BASE_URL + START_PATH

KEYWORD_DIEU_CHINH = "điều chỉnh"
KEYWORD_THU_HOI = "thu hồi"

# ✨ Load Google Sheet credentials
sheet_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
sheet_id = os.environ.get("GOOGLE_SHEET_ID")

if not sheet_json or not sheet_id:
    print("❌ Thiếu GOOGLE_CREDENTIALS_JSON hoặc GOOGLE_SHEET_ID.")
    exit(1)

creds_dict = json.loads(sheet_json)
creds = Credentials.from_service_account_info(creds_dict)
service = build("sheets", "v4", credentials=creds)
sheet = service.spreadsheets()

def classify_title(title):
    lower = title.lower()
    if KEYWORD_DIEU_CHINH in lower:
        return "Điều chỉnh"
    elif KEYWORD_THU_HOI in lower:
        return "Thu hồi"
    else:
        return "Khác"

def crawl_links_and_classify():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        print(f"🌐 Đang mở trang: {FULL_URL}")
        page.goto(FULL_URL, timeout=60000)
        page.wait_for_timeout(3000)

        elements = page.query_selector_all(".list-item a")
        print(f"🔗 Tổng số thẻ <a>: {len(elements)}")

        data = []

        for el in elements:
            href = el.get_attribute("href")
            title = el.inner_text().strip()
            if href and "/portal" not in href:
                full_link = BASE_URL + href if href.startswith("/") else href
                category = classify_title(title)
                if category != "Khác":
                    data.append([title, full_link, category])

        browser.close()

        if not data:
            print("⚠️ Không tìm thấy link nào để ghi vào sheet.")
            return

        print(f"🔗 Tổng số link hợp lệ: {len(data)}")

        # Ghi dữ liệu vào sheet 'Tonghop' từ ô A2
        sheet.values().update(
            spreadsheetId=sheet_id,
            range="Tonghop!A2",
            valueInputOption="RAW",
            body={"values": data}
        ).execute()

        print(f"📄 Đã ghi {len(data)} link vào sheet 'Tonghop'.")

if __name__ == "__main__":
    crawl_links_and_classify()
