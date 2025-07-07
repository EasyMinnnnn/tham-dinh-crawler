from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Trang chứa PDF
        await page.goto("https://mof.gov.vn/bo-tai-chinh/...")  # Đổi URL thật

        # Chờ iframe xuất hiện
        frame_element = await page.wait_for_selector("iframe")
        frame = await frame_element.content_frame()

        # Kiểm tra frame tồn tại
        if frame is None:
            raise Exception("Không tìm thấy iframe chứa nội dung!")

        # Chờ nút download trong frame
        download_button = await frame.wait_for_selector("button.download")

        # Click để tải file
        print("Đang click nút download...")
        async with page.expect_download() as download_info:
            await download_button.click()
        download = await download_info.value

        save_path = "downloaded_file.pdf"
        await download.save_as(save_path)
        print(f"Đã tải file về: {save_path}")

        await browser.close()

asyncio.run(run())
