import os
import json
import re
from playwright.sync_api import sync_playwright
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# ============ CONFIG ============
BASE_URL   = "https://mof.gov.vn"
START_PATH = "/bo-tai-chinh/danh-sach-tham-dinh-ve-gia"
FULL_URL   = BASE_URL + START_PATH

# Năm crawl (mặc định 2025)
YEAR = int(os.getenv("CRAWL_YEAR", "2025"))

# Tên tab đích
SHEET_TAB_PERSONAL = os.getenv("SHEET_TAB_PERSONAL", "Personal")
SHEET_TAB_COMPANY  = os.getenv("SHEET_TAB_COMPANY",  "Company")

# Từ khóa phân loại
KW_PERSONAL = [
    "danh sách thẩm định viên về giá",
    "điều chỉnh thông tin về thẩm định viên",
]
KW_COMPANY = ["thu hồi", "đình chỉ", "quyết định"]

# ============ GOOGLE SHEETS ============
sheet_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
sheet_id   = os.environ.get("GOOGLE_SHEET_ID")

if not sheet_json or not sheet_id:
    print("❌ Thiếu GOOGLE_CREDENTIALS_JSON hoặc GOOGLE_SHEET_ID.")
    raise SystemExit(1)

creds_dict = json.loads(sheet_json)
creds = Credentials.from_service_account_info(creds_dict)
service = build("sheets", "v4", credentials=creds)
sheet = service.spreadsheets()

# ============ HELPERS ============
def _normalize(s: str) -> str:
    return (s or "").strip().lower()

def is_target_year(title: str, href: str) -> bool:
    """
    Ưu tiên lọc theo '2025' trong tiêu đề; nếu không có thì fallback theo URL.
    Có thể mở rộng nếu MOF thay đổi mẫu tiêu đề.
    """
    t = _normalize(title)
    if str(YEAR) in t:
        return True
    return str(YEAR) in _normalize(href)

def classify_bucket(title: str) -> str | None:
    t = _normalize(title)
    if any(k in t for k in KW_PERSONAL):
        return "personal"
    if any(k in t for k in KW_COMPANY):
        return "company"
    return None

def write_to_sheet(target_tab: str, rows: list[list[str]]) -> None:
    if not rows:
        return
    sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{target_tab}!A2",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()
    print(f"📄 Đã ghi {len(rows)} link vào sheet '{target_tab}'.")

# ============ MAIN ============
def crawl_links_and_classify():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            print(f"🌐 Đang mở trang: {FULL_URL}")
            page.goto(FULL_URL, timeout=60000)
            page.wait_for_timeout(5000)  # chờ JS load

            elements = page.query_selector_all("a")
            print(f"🔗 Tổng số thẻ <a>: {len(elements)}")

            personal_rows: list[list[str]] = []
            company_rows: list[list[str]] = []
            seen_links: set[str] = set()

            for el in elements:
                href = el.get_attribute("href")
                if not href or not href.startswith(START_PATH + "/"):
                    continue

                title = (el.inner_text() or "").strip()
                if not title:
                    continue

                # Lọc theo năm
                if not is_target_year(title, href):
                    continue

                bucket = classify_bucket(title)
                if not bucket:
                    continue

                full_link = BASE_URL + href

                # Chống trùng URL
                if full_link in seen_links:
                    continue
                seen_links.add(full_link)

                row = [title, full_link]
                if bucket == "personal":
                    personal_rows.append(row)
                else:
                    company_rows.append(row)

        finally:
            browser.close()

        if not personal_rows and not company_rows:
            print("⚠️ Không tìm thấy link phù hợp (năm/keywords).")
            return

        print(f"✅ Link hợp lệ: Cá nhân={len(personal_rows)} | Doanh nghiệp={len(company_rows)}")
        write_to_sheet(SHEET_TAB_PERSONAL, personal_rows)
        write_to_sheet(SHEET_TAB_COMPANY,  company_rows)

if __name__ == "__main__":
    crawl_links_and_classify()
