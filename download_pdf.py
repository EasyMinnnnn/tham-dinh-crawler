import asyncio
import os
import sys
import time
from urllib.parse import urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

async def run(url):
    os.makedirs("outputs", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, timeout=15000)
            print("🌐 Đã mở trang:", url)

            # Đợi nút download trong tối đa 10s
            try:
                download_button = await page.wait_for_selector('button#download[title="Download"]', timeout=10000)
            except PlaywrightTimeoutError:
                print("❌ Không tìm thấy nút download trong trang.")
                return

            print("📥 Đã tìm thấy nút download, đang click...")

            async with page.expect_download() as download_info:
                await download_button.click()
            download = await download_info.value

            # Tạo tên file từ slug URL hoặc timestamp
            slug = os.path.basename(urlparse(url).path)
            filename = f"{slug or int(time.time())}.pdf"
            save_path = os.path.join("outputs", filename)

            await download.save_as(save_path)
            print(f"✅ Đã tải file về: {save_path}")
        except Exception as e:
            print("❌ Lỗi khi tải file:", e)
        finally:
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("⚠️ Cách dùng: python download_pdf.py <URL>")
    else:
        asyncio.run(run(sys.argv[1]))
