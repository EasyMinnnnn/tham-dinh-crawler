import requests
from bs4 import BeautifulSoup
import re
import os
import json
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

BASE_URL = "https://mof.gov.vn"
START_PATH = "/bo-tai-chinh/danh-sach-tham-dinh-ve-gia"
FULL_URL = BASE_URL + START_PATH

# Các từ khóa để phân loại
KEYWORD_DIEU_CHINH = "điều chỉnh"
KEYWORD_THU_HOI = "thu hồi"

# Load thông tin Google Sheet
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
    print(f"🌐 Đang mở trang: {FULL_URL}")
    response = requests.get(FULL_URL)
    soup = BeautifulSoup(response.text, "html.parser")

    links = []
    for a in soup.find_all("a"):
        href = a.get("href")
        title = a.get_text(strip=True)

        if href and href.startswith("/bo-tai-chinh") and "/danh-sach-tham-dinh-ve-gia/" in href:
            full_link = BASE_URL + href
            kind = classify_title(title)
            links.append([full_link, title, kind])

    print(f"🔗 Tổng số link hợp lệ: {len(links)}")

    if not links:
        print("⚠️ Không tìm thấy link nào để ghi vào sheet.")
        return

    # Ghi vào sheet 'Tonghop'
    values = [["Link", "Tiêu đề", "Loại"]] + links
    sheet.values().update(
        spreadsheetId=sheet_id,
        range="Tonghop!A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

    print("📤 Đã ghi danh sách link vào sheet 'Tonghop'.")

if __name__ == "__main__":
    crawl_links_and_classify()
