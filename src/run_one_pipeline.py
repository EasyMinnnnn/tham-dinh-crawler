import asyncio
import os
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

        await page.wait_for_timeout(5000)
        html = await page.content()
        with open("mof_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        link_elements = await page.query_selector_all("a")
        print(f"🔎 Tổng số thẻ <a>: {len(link_elements)}")

        valid_links = []
        for link in link_elements:
            href = await link.get_attribute("href")
            text = await link.inner_text()
            if href:
                print(f"↪️ {text.strip()} --> {href.strip()}")
            if href and "danh-sach-tham-dinh-ve-gia" in href and href.endswith(".html"):
                valid_links.append(href.strip())

        if not valid_links:
            print("❌ Không tìm thấy bài viết hợp lệ.")
            await browser.close()
            return

        relative_path = valid_links[0]
        detail_url = relative_path if relative_path.startswith("http") else domain + relative_path
        print("🔗 Link chi tiết:", detail_url)

        await browser.close()

    print("📅 Đang tải PDF...")
    subprocess.run(["python", "download_pdf.py", detail_url], check=True)

    output_dir = Path("outputs")
    pdf_files = list(output_dir.glob("*.pdf"))
    if not pdf_files:
        print("❌ Không tìm thấy file PDF sau khi tải.")
        return

    latest_pdf = max(pdf_files, key=os.path.getmtime)
    print("📄 PDF mới nhất:", latest_pdf)

    print("🧐 Đang OCR và extract bảng...")
    try:
        subprocess.run(["python", "ocr_to_json.py", str(latest_pdf)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi chạy OCR: {e}")
        return

    print("✅ Hoàn tất pipeline cho dòng đầu.")

if __name__ == "__main__":
    asyncio.run(main())
