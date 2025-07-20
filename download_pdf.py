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

        page.wait_for_timeout(2000)

        try:
            print("📥 Đang tìm nút download...")
            download_button = page.locator(
                "xpath=/html/body/div[1]/div/main/div/div[1]/div/div[2]/div[4]/div/form/div/div/div[2]/div[3]/div/div/div[2]/button[4]"
            )
            if download_button.is_visible():
                with page.expect_download(timeout=15000) as download_info:
                    download_button.click()
                download = download_info.value
                download_path = os.path.join(output_dir, download.suggested_filename)
                download.save_as(download_path)
                print(f"✅ Đã tải file về: {download_path}")
                return download_path
            else:
                print("❌ Nút download không hiển thị.")
        except Exception as e:
            print(f"❌ Không tìm thấy nút download hoặc lỗi tải: {e}")
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
