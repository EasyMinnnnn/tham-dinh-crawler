import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

def crawl_new_links():
    url = "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia"
    res = requests.get(url, timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")

    base = "https://mof.gov.vn"
    found = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        title = a.get_text(strip=True)
        if href.startswith("/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/") and title:
            full_url = base + href
            found.append({"title": title, "link": full_url})

    print(f"🔍 Đã tìm thấy {len(found)} link phù hợp.")
    return found

def write_to_google_sheet(new_items):
    # Xác thực Google Sheets
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(creds_json)
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1
    existing_links = set(sheet.col_values(2))

    count_new = 0
    for item in reversed(new_items):
        if item["link"] not in existing_links:
            sheet.insert_row([item["title"], item["link"]], 1)
            print("✅ Đã thêm:", item["title"])
            count_new += 1

    print("🧾 Tổng số dòng mới:", count_new)

if __name__ == "__main__":
    try:
        items = crawl_new_links()
        write_to_google_sheet(items)
    except Exception as e:
        print("❌ Lỗi khi xử lý:", e)
