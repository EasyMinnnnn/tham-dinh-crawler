import os
import json
import asyncio
import gspread
from playwright.async_api import async_playwright
from google.oauth2.service_account import Credentials

async def crawl_new_links():
    base_url = "https://mof.gov.vn"
    full_url = base_url + "/bo-tai-chinh/danh-sach-tham-dinh-ve-gia"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(full_url, timeout=20000)
        await page.wait_for_timeout(5000)

        links = await page.query_selector_all("a")
        new_items = []

        for link in links:
            href = await link.get_attribute("href")
            title = await link.inner_text()
            if (
                href and
                href.startswith("/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/") and
                title.strip()
            ):
                full_link = base_url + href
                new_items.append({
                    "title": title.strip(),
                    "link": full_link
                })

        await browser.close()
        print(f"🔍 Đã tìm thấy {len(new_items)} link phù hợp.")
        return new_items

def write_to_google_sheet(new_items):
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(creds_json)
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1
    existing_links = set(sheet.col_values(2))  # Cột B

    count_new = 0
    for item in reversed(new_items):  # Giữ thứ tự mới nhất ở trên
        if item["link"] not in existing_links:
            sheet.insert_row([item["title"], item["link"]], 1)
            print("✅ Đã thêm:", item["title"])
            count_new += 1

    print("🧾 Tổng số dòng mới:", count_new)

if __name__ == "__main__":
    try:
        items = asyncio.run(crawl_new_links())
        write_to_google_sheet(items)
    except Exception as e:
        print("❌ Lỗi khi xử lý:", e)
