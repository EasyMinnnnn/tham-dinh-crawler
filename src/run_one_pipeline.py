import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import subprocess
from src.download_pdf import run as download_pdf
from src.utils import print_step

async def main():
    print_step("📦 BASE64_PDF_END")
    print_step("🌐 Đã vào trang danh sách.")

    pdf_files = download_pdf(limit=1)
    if not pdf_files:
        print("❌ Không tải được file PDF nào.")
        return

    latest_pdf = pdf_files[0]
    print_step(f"📄 PDF mới nhất: {latest_pdf}")
    print_step("🧠 Đang OCR...")

    try:
        subprocess.run(["python", "ocr_to_json.py", str(latest_pdf)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ OCR lỗi: {e}")
        raise

    print_step("📤 Đang đẩy dữ liệu vào Google Sheet...")

    try:
        subprocess.run(["python", "extract_to_sheet.py", str(latest_pdf).replace(".pdf", ".json")], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi extract: {e}")
        raise

    print_step("✅ Hoàn thành toàn bộ pipeline!")

if __name__ == "__main__":
    asyncio.run(main())
