import asyncio
import os
import subprocess
import re
from pathlib import Path
from playwright.async_api import async_playwright

@@ -30,17 +31,23 @@
                print(f"↪️ {text.strip()} --> {href.strip()}")
            if href and href.startswith("/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/"):
                href = href.strip()
                valid_links.append(href)
                text = text.strip()
                valid_links.append((href, text))

        if not valid_links:
            print("❌ Không tìm thấy bài viết hợp lệ.")
            await browser.close()
            return

        relative_path = valid_links[0]
        relative_path, title_text = valid_links[0]
        detail_url = domain + relative_path
        print("🔗 Link chi tiết:", detail_url)

        # Trích số hiệu văn bản, ví dụ: 586/TB-BTC
        match = re.search(r"(\d{2,5}/TB-BTC)", title_text, re.IGNORECASE)
        doc_number = match.group(1) if match else ""
        print("📎 Số hiệu văn bản:", doc_number)

        await browser.close()

    print("📅 Đang tải PDF...")
@@ -57,12 +64,14 @@

    print("🧐 Đang OCR và extract bảng...")
    try:
        subprocess.run(["python", "ocr_to_json.py", str(latest_pdf)], check=True)
        env = os.environ.copy()
        env["DOCUMENT_NUMBER"] = doc_number  # 👈 Truyền biến môi trường vào OCR script
        subprocess.run(["python", "ocr_to_json.py", str(latest_pdf)], check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi chạy OCR: {e}")
        return

    print("✅ Hoàn tất pipeline cho dòng đầu.")

if __name__ == "__main__":
    asyncio.run(main())
