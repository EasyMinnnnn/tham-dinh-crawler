import os
import asyncio
from playwright.async_api import async_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials

async def main():
    # 1. Crawl dữ liệu
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia")
        await page.wait_for_timeout(5000)

        html = await page.content()
        print("HTML Length:", len(html))

        links = await page.query_selector_all("a")
        new_items = []
        for link in links:
            title = await link.inner_text()
            href = await link.get_attribute("href")
            if (
                href 
                and href.startswith("/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/")
            ):
                print("Title:", title.strip(), "| Link:", href.strip())
                new_items.append({"title": title.strip(), "link": href.strip()})
        
        await browser.close()

    # 2. Kết nối Google Sheet
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = eval(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1

    # 3. Lấy danh sách link đã có
    existing_links = set(sheet.col_values(2))
    print("Đã có", len(existing_links), "link.")

    # 4. Thêm mới lên đầu
    count_new = 0
    for item in reversed(new_items):  # reversed để giữ thứ tự mới nhất trên cùng
        if item["link"] not in existing_links:
            # Chèn dòng trống lên đầu
            sheet.insert_row([], 1)
            # Ghi dữ liệu vào dòng 1
            sheet.update('A1', [[item["title"], item["link"]]])
            print("Đã thêm:", item["title"])
            count_new += 1

    print("Tổng số dòng mới:", count_new)

if __name__ == "__main__":
    asyncio.run(main())
