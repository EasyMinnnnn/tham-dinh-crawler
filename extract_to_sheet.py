import json
import os
import gspread
from google.oauth2.service_account import Credentials

# Kết nối Google Sheet API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(CREDS)

# Ghi vào Trang tính 2
sheet = gc.open("Tham Dinh Sheet").worksheet("Trang tính 2")

# Đọc JSON
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
                    row_text.append(" ".join(texts))
                all_text.append(row_text)
    return all_text

# Duyệt qua thư mục outputs
for file in os.listdir("outputs"):
    if file.endswith(".json"):
        rows = extract_data_from_json(os.path.join("outputs", file))
        for row in rows:
            sheet.append_row(row)
