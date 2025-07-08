import json
import os
import gspread
from google.oauth2.service_account import Credentials

# Thiết lập Google Sheet API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(CREDS)

# Mở Google Sheet và chọn "Trang tính 2"
spreadsheet = gc.open("Tham Dinh Sheet")
worksheet = spreadsheet.worksheet("Trang tính 2")

# Đọc file JSON từ thư mục outputs
def extract_data_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_text = []
    for page in data.get("pages", []):
        for table in page.get("tables", []):
            for row in table.get("rows", []):
                row_text = []
                for cell in row.get("cells", []):
                    texts = [
                        block.get("textBlock", {}).get("text", "")
                        for block in cell.get("blocks", [])
                    ]
                    row_text.append(" ".join(texts).strip())
                all_text.append(row_text)
    return all_text

# Duyệt qua tất cả file JSON trong thư mục outputs và ghi vào sheet
for file in os.listdir("outputs"):
    if file.endswith(".json"):
        rows = extract_data_from_json(os.path.join("outputs", file))
        for row in rows:
            worksheet.append_row(row)
