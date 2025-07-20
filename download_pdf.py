import os
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

DOWNLOAD_DIR = "outputs"
BASE_URL = "https://mof.gov.vn"

async def download_pdf(link):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        full_url = link if link.startswith("http") else BASE_URL + link
        print(f"🌐 Đã mở trang: {full_url}")
        await page.goto(full_url, timeout=60000)
        await page.wait_for_timeout(2000)

        try:
            print("📥 Đang tìm nút download PDF theo XPath...")
            with context.expect_page() as new_page_info:
                await page.locator('//html/body/div[1]/div/main/div/div[1]/div/div[2]/div[4]/div/form/div/div/div[2]/div[3]/div/div/div[2]/button[4]').click()
            new_tab = await new_page_info.value
            await new_tab.wait_for_load_state()
            pdf_url = new_tab.url
            print(f"📄 Link file PDF: {pdf_url}")

            # Tải file PDF về local
            filename = pdf_url.split("/")[-1]
            save_path = os.path.join(DOWNLOAD_DIR, filename)
            content = await new_tab.content()
            if "pdf" not in content.lower():
                print("❌ Không phải file PDF.")
                return None

            async with context.request.get(pdf_url) as response:
                if response.ok:
                    with open(save_path, "wb") as f:
                        f.write(await response.body())
                    print(f"✅ Đã lưu file: {save_path}")
                    return save_path
                else:
                    print("❌ Không thể tải file PDF.")
                    return None

        except Exception as e:
            print(f"❌ Lỗi khi tải PDF: {e}")
            return None
        finally:
            await browser.close()
