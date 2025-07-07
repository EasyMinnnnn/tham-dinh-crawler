from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # URL trang chi tiết thông báo
        await page.goto("https://mof.gov.vn/bo-tai-chinh/...")   # <== Đổi thành URL thật

        # Tìm nút download theo class
        download_button = await page.wait_for_selector("button.download")

        # Click để tải file
        print("Đang click nút download...")
        async with page.expect_download() as download_info:
            await download_button.click()
        download = await download_info.value

        # Lưu file về workspace
        save_path = "downloaded_file.pdf"
        await download.save_as(save_path)
        print(f"Đã tải file về: {save_path}")

        await browser.close()

asyncio.run(run())
