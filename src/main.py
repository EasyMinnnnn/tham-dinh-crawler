import os
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def main():
    # 1. Crawl website
    url = "https://mof.gov.vn/bo-tai-chinh/danh-sach-tham-dinh-ve-gia"
    res = requests.get(url)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    # Ví dụ: chọn tất cả thẻ chứa tiêu đề (tuỳ chỉnh selector phù hợp)
    items = soup.select("div.news-list li")
    new_items = []
    for item in items:
        title = item.get_text(strip=True)
        link = item.find("a")["href"]
        new_items.append({"title": title, "link": link})

    # 2. Kết nối Google Sheets
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = eval(creds_json)   # Biến môi trường chứa JSON
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1

    # 3. Đọc danh sách link đã có
    existing = sheet.col_values(2)  # Giả sử cột 2 lưu link

    # 4. Ghi item mới
    for item in new_items:
        if item["link"] not in existing:
            sheet.append_row([item["title"], item["link"]])
            print("Đã thêm:", item["title"])

if __name__ == "__main__":
    main()

