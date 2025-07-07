import requests

# ✅ Link bạn muốn kiểm tra
url = "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/thong-bao-so-543tb-btc-ve-viec-dieu-chinh-thong-tin-ve-tham-dinh-vien-ve-gia-nam-2025"

# ✅ Gửi request tải nội dung
response = requests.get(url)
print("Status Code:", response.status_code)

if response.ok:
    # ✅ In độ dài nội dung
    print("Nội dung HTML độ dài:", len(response.text))
    print("30 ký tự đầu tiên:", response.text[:30])

    # ✅ Lưu HTML ra file để dễ kiểm tra
    with open("page.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Đã lưu file page.html thành công.")
else:
    print("Tải nội dung thất bại.")
