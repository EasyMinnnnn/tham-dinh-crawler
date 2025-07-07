import requests

# Ví dụ: link đầy đủ (bạn copy từ Google Sheet)
url = "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia/thong-bao-so-543tb-btc-ve-viec-dieu-chinh-thong-tin-ve-tham-dinh-vien-ve-gia-nam-2025"

response = requests.get(url)
print("Status Code:", response.status_code)

if response.ok:
    print("Nội dung HTML độ dài:", len(response.text))
    print("30 ký tự đầu tiên:", response.text[:30])
else:
    print("Không tải được nội dung.")
