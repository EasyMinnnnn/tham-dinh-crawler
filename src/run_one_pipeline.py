import asyncio
import os
import subprocess
from src.download_pdf import run as download_pdf
from src.extract_to_sheet import run as extract_to_sheet

async def main():
    print("🌐 Đang crawl link PDF...")
    latest_pdf = await download_pdf(only_latest=True)

    if not latest_pdf:
        print("❌ Không tìm thấy PDF mới.")
        return

    print(f"📄 PDF mới nhất: {latest_pdf}")
    print("🧠 Đang OCR...")

    try:
        subprocess.run(["python", "ocr_to_json.py", str(latest_pdf)], check=True, env=os.environ)
    except subprocess.CalledProcessError as e:
        print(f"❌ OCR thất bại: {e}")
        return

    print("📊 Đang extract JSON vào Google Sheet...")
    await extract_to_sheet(file_path=latest_pdf.replace(".pdf", ".json"))

if __name__ == "__main__":
    asyncio.run(main())
