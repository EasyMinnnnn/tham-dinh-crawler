import os
import sys
import time
from urllib.parse import urlparse, urljoin
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

OUTPUT_DIR = "outputs"
DEFAULT_BASE = "https://mof.gov.vn"

def ensure_unique_path(path: Path) -> Path:
    """Nếu file đã tồn tại thì thêm -1, -2... vào trước đuôi mở rộng."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 1
    while True:
        candidate = path.with_name(f"{stem}-{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1

def slugify_filename(name: str, default: str = "download") -> str:
    s = "".join(ch if ch.isalnum() or ch in (" ", "_", "-", ".", "(", ")") else " " for ch in name)
    s = "_".join(s.split())
    return s or default

def _build_full_url(url_or_rel: str) -> tuple[str, str]:
    """Trả về (base_url, relative_path_or_full)."""
    if url_or_rel.startswith("http"):
        parsed = urlparse(url_or_rel)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rel = parsed.path or ""
        if parsed.query:
            rel += f"?{parsed.query}"
        return base, rel
    return DEFAULT_BASE, url_or_rel

def _click_with_fallbacks(page) -> str | None:
    """
    Cố gắng bấm các selector tải xuống phổ biến và trả về tên file gợi ý (nếu có).
    Trả về None nếu không bấm được.
    """
    # 1) ID thường gặp
    try:
        page.wait_for_selector("#download", timeout=3000)
        page.locator("#download").click()
        return None
    except Exception:
        pass

    # 2) thẻ có thuộc tính download
    links = page.locator("a[download]")
    if links.count() > 0:
        try:
            links.first.click()
            return None
        except Exception:
            pass

    # 3) liên kết đuôi .pdf
    pdf_links = page.locator('a[href$=".pdf"]')
    if pdf_links.count() > 0:
        try:
            # Nếu có nhiều link, ưu tiên cái đầu
            pdf_links.first.click()
            return None
        except Exception:
            pass

    # 4) theo text
    for sel in [
        "text=/.*tải(\\s|$)/i",
        "text=/download/i",
        "role=link[name=/tải|download/i]",
        "role=button[name=/tải|download/i]",
    ]:
        try:
            page.locator(sel).first.click()
            return None
        except Exception:
            continue

    return None

def download_latest_pdf(url_or_rel: str) -> str | None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    base_url, relative_link = _build_full_url(url_or_rel)
    full_url = urljoin(base_url, relative_link)

    headless = os.getenv("PLAYWRIGHT_HEADLESS", "1") != "0"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True, user_agent=user_agent)
        page = context.new_page()

        print(f"🌐 Đang mở trang: {full_url}")
        page.goto(full_url, timeout=60000, wait_until="domcontentloaded")
        # đợi thêm cho JS render (SPA)
        page.wait_for_timeout(5000)

        try:
            # Bấm nút tải với nhiều fallback
            print("🔎 Tìm nút/đường dẫn tải PDF…")
            with page.expect_download(timeout=20000) as dl_info:
                _click_with_fallbacks(page)

            download = dl_info.value

            # Lấy tên file gợi ý; nếu không có thì tự đặt từ tiêu đề trang
            suggested = download.suggested_filename or ""
            if not suggested:
                title = page.title() or "download"
                suggested = slugify_filename(title) + ".pdf"

            out_path = ensure_unique_path(Path(OUTPUT_DIR) / suggested)
            download.save_as(str(out_path))
            print(f"✅ Đã tải file về: {out_path}")

            return str(out_path)

        except PWTimeout:
            print("❌ Hết hạn chờ tải xuống (timeout).")
        except Exception as e:
            print(f"❌ Không thể tải file: {e}")
        finally:
            # Debug artifacts
            try:
                page.screenshot(path="debug_screenshot.png")
                print("🖼️ Đã chụp ảnh màn hình: debug_screenshot.png")
            except Exception:
                pass
            try:
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                print("🧾 Đã lưu HTML: debug_page.html")
            except Exception:
                pass
            try:
                print("📁 outputs hiện có:", os.listdir(OUTPUT_DIR))
            except Exception:
                pass
            context.close()
            browser.close()

    return None

if __name__ == "__main__":
    # Cách dùng:
    #   python src/download_pdf.py "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/..."
    #   hoặc truyền relative path:
    #   python src/download_pdf.py "/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/..."
    #
    # Tuỳ chọn:
    #   PLAYWRIGHT_HEADLESS=0  (để mở cửa sổ trình duyệt khi debug)
    #   PRINT_BASE64=1         (in base64 PDF sau khi tải)
    #
    target = None
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        # ví dụ mặc định (cập nhật nếu cần)
        target = "/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/thong-bao-so-622tb-btc-ve-danh-sach-tham-dinh-vien-ve-gia-nam-2025"

    pdf_path = download_latest_pdf(target)
    if pdf_path and os.getenv("PRINT_BASE64") == "1":
        import base64
        try:
            with open(pdf_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            print("📦 BASE64_PDF_BEGIN")
            print(encoded)
            print("📦 BASE64_PDF_END")
        except Exception as e:
            print(f"❌ Không thể đọc file PDF để in base64: {e}")
