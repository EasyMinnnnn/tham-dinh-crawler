import os
import asyncio
from playwright.async_api import async_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials

async def main():
    # 1. Dùng Playwright để render JS và lấy HTML
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia")
        await page.wait_for_timeout(5000)  # đợi 5 giây load JS
        
        html = await page.content()
        print("HTML Length:", len(html))
        
        # Lấy tất cả thẻ <a> trong trang
        links = await page.query_selector_all("a")
        new_items = []
        for link in links:
            title = await link.inner_text()
            href = await link.get_attribute("href")
            if href and "/bo-tai-chinh/" in href:
                print("Title:", title.strip(), "| Link:", href.strip())
                new_items.append({"title": title.strip(), "link": href.strip()})
        
        await browser.close()

    # 2. Ghi ra Google Sheet
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = eval(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1
    existing = sheet.col_values(2)

    count_new = 0
    for item in new_items:
        if item["link"] not in existing:
            sheet.append_row([item["title"], item["link"]])
            print("Đã thêm:", item["title"])
            count_new += 1
    print("Tổng số dòng mới:", count_new)

if __name__ == "__main__":
    asyncio.run(main())
