import asyncio
import os
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    base_url = "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(base_url, timeout=30000)
        print("🌐 Đã vào trang danh sách.")

        # Chờ trang tải xong
        await page.wait_for_timeout(5000)

        # Lưu HTML để kiểm tra sau
        html = await page.content()
        with open("mof_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        # Lấy toàn bộ thẻ <a> trên trang
        link_elements = await page.query_selector_all("a")
        print(f"🔎 Tổng số thẻ <a>: {len(link_elements)}")

        valid_links = []
        for link in link_elements:
            href = await link.get_attribute("href")
            text = await link.inner_text()
            if href:
                print(f"↪️ {text.strip()} --> {href.strip()}")
            if href and href.startswith("/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/") and href.count("/") > 4:
                valid_links.append(href)

        if not valid_links:
            print("❌ Không tìm thấy bài viết hợp lệ.")
            await browser.close()
            return

        detail_url = valid_links[0]
        if not detail_url.startswith("http"):
            detail_url = "https://mof.gov.vn" + detail_url

        print("🔗 Link chi tiết:", detail_url)
        await browser.close()

    # Bước 1: Download PDF
    print("📥 Đang tải PDF...")
    subprocess.run(["python", "download_pdf.py", detail_url], check=True)

    # Tìm file PDF mới nhất trong thư mục outputs/
    output_dir = Path("outputs")
    pdf_files = list(output_dir.glob("*.pdf"))
    if not pdf_files:
        print("❌ Không tìm thấy file PDF sau khi tải.")
        return

    latest_pdf = max(pdf_files, key=os.path.getmtime)
    print("📄 PDF mới nhất:", latest_pdf)

    # Bước 2: OCR file đó
    print("🧠 Đang OCR...")
    subprocess.run(["python", "ocr_to_json.py", str(latest_pdf)], check=True)

    # Bước 3: Extract vào Google Sheet
    json_file = str(latest_pdf).replace(".pdf", ".json")
    print("📊 Đang extract dữ liệu sang Google Sheet...")
    subprocess.run(["python", "extract_to_sheet.py", json_file], check=True)

    print("✅ Hoàn tất pipeline cho dòng đầu tiên.")

if __name__ == "__main__":
    asyncio.run(main())
