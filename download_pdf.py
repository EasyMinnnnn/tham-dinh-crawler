import asyncio
from playwright.async_api import async_playwright

async def main():
    url = "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/thong-bao-so-543tb-btc-ve-viec-dieu-chinh-thong-tin-ve-tham-dinh-vien-ve-gia-nam-2025"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Tải trang
        await page.goto(url)

        # Chờ nút tải PDF xuất hiện
        download_button = await page.wait_for_selector('button[aria-label="Download"]', timeout=10000)

        # Bắt sự kiện download
        async with page.expect_download() as download_info:
            await download_button.click()

        download = await download_info.value
        path = await download.path()
        print("File tải về tạm:", path)

        # Lưu file
        await download.save_as("thongbao.pdf")
        print("Đã lưu file thongbao.pdf thành công.")

        await browser.close()

asyncio.run(main())
