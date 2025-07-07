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

    # 2. Lấy tất cả thẻ <li> để debug thử
    items = soup.find_all("li")
    print("Tổng số items:", len(items))

    new_items = []
    for item in items:
        a_tag = item.find("a")
        if a_tag and "href" in a_tag.attrs:
            title = a_tag.get_text(strip=True)
            link = a_tag["href"]
            print("Title:", title, "| Link:", link)
            new_items.append({"title": title, "link": link})

    # 3. Kết nối Google Sheets
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = eval(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1

    # 4. Đọc danh sách link đã có
    existing = sheet.col_values(2)  # Cột 2 chứa link

    # 5. Ghi các item mới vào Sheet
    count_new = 0
    for item in new_items:
        if item["link"] not in existing:
            sheet.append_row([item["title"], item["link"]])
            print("Đã thêm:", item["title"])
            count_new += 1

    print("Tổng số dòng mới đã thêm:", count_new)

if __name__ == "__main__":
    main()
