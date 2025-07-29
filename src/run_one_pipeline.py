import asyncio
import os
import re
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    base_url = "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia"
    domain = "https://mof.gov.vn"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(base_url, timeout=30000)
        print("🌐 Đã vào trang danh sách.")

        # Cuộn để tải động
        await page.mouse.wheel(0, 3000)
        await page.wait_for_timeout(3000)

        # Debug HTML nếu cần
        html = await page.content()
        with open("mof_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        # Trích toàn bộ <a> từ danh sách
        link_elements = await page.locator("a").all()
        print(f"🔎 Tổng số thẻ <a>: {len(link_elements)}")

        valid_links = []
        for link in link_elements:
            href = await link.get_attribute("href")
            text = (await link.inner_text()).strip()

            if href and "/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/" in href:
                print(f"↪️ {text} --> {href}")
                valid_links.append((text, href.strip()))

        if not valid_links:
            print("❌ Không tìm thấy bài viết hợp lệ.")
            await browser.close()
            return

        # Lấy bài đầu tiên
        title, relative_path = valid_links[0]
        detail_url = domain + relative_path
        print("🔗 Link chi tiết:", detail_url)

        # Trích số hiệu văn bản từ tiêu đề
        match = re.search(r"\b\d{3,4}/TB-BTC\b", title)
        so_van_ban = match.group(0) if match else ""
        print("📎 Số hiệu văn bản:", so_van_ban)

        await browser.close()

    # Tải file PDF
    print("📅 Đang tải PDF...")
    subprocess.run(["python", "download_pdf.py", detail_url], check=True)

    output_dir = Path("outputs")
    pdf_files = list(output_dir.glob("*.pdf"))
    if not pdf_files:
        print("❌ Không tìm thấy file PDF sau khi tải.")
        return

    latest_pdf = max(pdf_files, key=os.path.getmtime)
    print("📄 PDF mới nhất:", latest_pdf)

    # Gửi sang OCR
    print("🧐 Đang OCR và extract bảng...")
    try:
        subprocess.run(["python", "ocr_to_json.py", str(latest_pdf), so_van_ban], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi chạy OCR: {e}")
        return

    print("✅ Hoàn tất pipeline cho dòng đầu.")

if __name__ == "__main__":
    asyncio.run(main())
