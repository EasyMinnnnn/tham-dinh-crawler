# src/download_pdf.py
from playwright.async_api import async_playwright
import asyncio
import os

async def run():
    os.makedirs("outputs", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        url = "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/thong-bao-so-543tb-btc-ve-viec-dieu-chinh-thong-tin-ve-tham-dinh-vien-ve-gia-nam-2025"
        await page.goto(url)
        print("Đã mở trang:", url)

        download_button = await page.wait_for_selector('button#download[title="Download"]')
        print("Đã tìm thấy nút download, đang click...")

        async with page.expect_download() as download_info:
            await download_button.click()
        download = await download_info.value

        save_path = os.path.join("outputs", "downloaded.pdf")
        await download.save_as(save_path)
        print(f"Đã tải file về: {save_path}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
