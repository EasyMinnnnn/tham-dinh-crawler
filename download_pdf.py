import os
import time
from pathlib import Path
from playwright.async_api import async_playwright

DOWNLOAD_DIR = "outputs"
BASE_URL = "https://mof.gov.vn"

async def download_pdf(link):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        full_url = link if link.startswith("http") else BASE_URL + link
        print(f"🌐 Đã mở trang: {full_url}")
        await page.goto(full_url, timeout=60000)
        await page.wait_for_timeout(2000)  # Đợi 2s cho trang load ổn định

        # Tìm nút tải theo đúng XPath bạn cung cấp
        try:
            print("📥 Đang tìm nút download PDF...")
            download_button = await page.wait_for_selector(
                '//html/body/div[1]/div/main/div/div[1]/div/div[2]/div[4]/div/form/div/div/div[2]/div[3]/div/div/div[2]/button[4]',
                timeout=10000
            )

            if download_button:
                print("📥 Đã tìm thấy nút download, đang click...")
                download = await page.expect_download()
                await download_button.click()
                dl = await download.value
                save_path = os.path.join(DOWNLOAD_DIR, dl.suggested_filename)
                await dl.save_as(save_path)
                print(f"✅ Đã tải file về: {save_path}")
                return save_path
            else:
                print("❌ Không tìm thấy nút download trong trang.")
                return None

        except Exception as e:
            print("❌ Lỗi khi click nút download:", e)
            return None
        finally:
            await browser.close()
