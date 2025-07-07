from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        url = "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/thong-bao-so-543tb-btc-ve-viec-dieu-chinh-thong-tin-ve-tham-dinh-vien-ve-gia-nam-2025"  # Thay bằng link thật
        await page.goto(url)
        print("Đã mở trang:", url)

        # Chờ nút xuất hiện (KHÔNG cần iframe)
        download_button = await page.wait_for_selector('button#download[title="Download"]')
        print("Đã tìm thấy nút download, đang click...")

        # Click và chờ tải
        async with page.expect_download() as download_info:
            await download_button.click()
        download = await download_info.value

        # Lưu file
        save_path = "downloaded_file.pdf"
        await download.save_as(save_path)
        print(f"Đã tải file về: {save_path}")

        await browser.close()

asyncio.run(run())
