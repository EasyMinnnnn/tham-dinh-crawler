import os
import base64
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

def download_latest_pdf(base_url="https://mof.gov.vn", relative_link=""):
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        full_url = urljoin(base_url, relative_link)
        print(f"🌐 Đang mở trang: {full_url}")
        page.goto(full_url, timeout=60000)
        page.wait_for_timeout(5000)  # tăng thời gian đợi render

        try:
            print("📥 Đang tìm nút download theo ID '#download'...")
            page.wait_for_selector("#download", timeout=15000)  # tăng timeout

            with page.expect_download(timeout=15000) as download_info:
                page.click("#download")

            download = download_info.value
            file_path = os.path.join(output_dir, download.suggested_filename)
            download.save_as(file_path)
            print(f"✅ Đã tải file về: {file_path}")
            return file_path

        except Exception as e:
            print(f"❌ Không thể tải file: {e}")
            print("📄 HTML hiện tại để debug:")
            try:
                print(page.content())
            except:
                print("⚠️ Không thể in HTML.")
        finally:
            print("📁 Kiểm tra thư mục outputs:")
            print(os.listdir(output_dir))
            context.close()
            browser.close()

    return None

if __name__ == "__main__":
    pdf_path = download_latest_pdf(
        relative_link="/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/quyet-dinh-so-2320tb-btc-ve-viec-thu-hoi-giay-chung-nhan-du-dieu-kien-kinh-doanh-dich-vu-tham-dinh-gia"
    )

    if pdf_path:
        try:
            with open(pdf_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
                print("📦 BASE64_PDF_BEGIN")
                print(encoded)
                print("📦 BASE64_PDF_END")
        except Exception as e:
            print(f"❌ Không thể đọc file PDF để in base64: {e}")
