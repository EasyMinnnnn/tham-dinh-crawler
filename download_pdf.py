import os
import time
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
        page.wait_for_timeout(3000)

        try:
            print("📥 Đang dò các phần tử có thể là nút download...")

            # Dò toàn bộ các thẻ có thể click được
            candidates = page.locator("a, button, div, span")
            count = candidates.count()

            for i in range(count):
                el = candidates.nth(i)
                try:
                    text = el.inner_text().strip().lower()
                except:
                    continue  # Bỏ qua nếu không đọc được

                if "tải" in text or ".pdf" in text:
                    print(f"🔘 Thử click: '{text}'")
                    with page.expect_download(timeout=15000) as download_info:
                        el.click()
                    download = download_info.value
                    file_path = os.path.join(output_dir, download.suggested_filename)
                    download.save_as(file_path)
                    print(f"✅ Đã tải file về: {file_path}")
                    return file_path

            print("❌ Không tìm thấy nút nào có chứa 'Tải' hoặc '.pdf'.")
        except Exception as e:
            print(f"❌ Lỗi khi tải file: {e}")
        finally:
            print("📁 Kiểm tra thư mục outputs:")
            print(os.listdir(output_dir))
            context.close()
            browser.close()

    return None

if __name__ == "__main__":
    download_latest_pdf(
        relative_link="/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/quyet-dinh-so-2320tb-btc-ve-viec-thu-hoi-giay-chung-nhan-du-dieu-kien-kinh-doanh-dich-vu-tham-dinh-gia"
    )
