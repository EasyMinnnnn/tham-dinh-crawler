import os, re
from playwright.sync_api import sync_playwright
from src.db import init_schema, get_conn

BASE_URL   = "https://mof.gov.vn"
START_PATH = "/bo-tai-chinh/danh-sach-tham-dinh-ve-gia"
FULL_URL   = BASE_URL + START_PATH

YEAR = int(os.getenv("CRAWL_YEAR", "2025"))
KW_PERSONAL = ["danh sách thẩm định viên về giá", "điều chỉnh thông tin về thẩm định viên"]
KW_COMPANY  = ["thu hồi", "đình chỉ", "quyết định"]

def _n(s): return (s or "").strip().lower()

def is_target_year(title, href):
    t = _n(title)
    if str(YEAR) in t: return True
    return str(YEAR) in _n(href)

def classify_bucket(title):
    t = _n(title)
    if any(k in t for k in KW_PERSONAL): return "personal"
    if any(k in t for k in KW_COMPANY):  return "company"
    return None

def save_link(title, url, bucket):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO links(title,url,bucket,year) VALUES(?,?,?,?)",
            (title, url, bucket, YEAR)
        )

def crawl_links_and_classify():
    init_schema()
    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_page()
        page.goto(FULL_URL, timeout=60000)
        page.wait_for_timeout(5000)

        for el in page.query_selector_all("a"):
            href = el.get_attribute("href")
            if not href or not href.startswith(START_PATH + "/"): 
                continue
            title = (el.inner_text() or "").strip()
            if not title: 
                continue
            if not is_target_year(title, href): 
                continue

            bucket = classify_bucket(title)
            if not bucket: 
                continue

            full_url = BASE_URL + href
            save_link(title, full_url, bucket)

        page.context.browser.close()

if __name__ == "__main__":
    crawl_links_and_classify()
    print("✅ Crawl xong. Link đã lưu trong data.db → bảng links")
