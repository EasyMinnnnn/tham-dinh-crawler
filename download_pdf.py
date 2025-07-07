from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/thong-bao-so-543tb-btc-ve-viec-dieu-chinh-thong-tin-ve-tham-dinh-vien-ve-gia-nam-2025")

        # Nếu nút download là button, selector ví dụ như sau:
        # await page.click("button[aria-label='Download']")

        # Hoặc nếu là link tải, dùng selector phù hợp:
        # await page.click("a:has-text('Tải về')")

        # Hoặc in ra tất cả link để kiểm tra:
        links = await page.query_selector_all("a")
        for link in links:
            text = await link.inner_text()
            href = await link.get_attribute("href")
            print(f"Link: {text} - {href}")

        await asyncio.sleep(5)
        await browser.close()

asyncio.run(run())
