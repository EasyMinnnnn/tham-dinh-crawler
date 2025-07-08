import json
import os
import gspread
from google.oauth2.service_account import Credentials

# Thiết lập Google Sheet API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Lấy credentials từ biến môi trường (dạng 1 dòng JSON)
creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
CREDS = Credentials.from_service_account_info(creds_info, scopes=SCOPES)

gc = gspread.authorize(CREDS)

# Truy cập sheet theo ID (không dùng .sheet1 nữa)
sheet_id = os.environ["GOOGLE_SHEET_ID"]
sh = gc.open_by_key(sheet_id)
worksheet = sh.worksheet("Trang tính2")  # Hoặc "Sheet2" tùy bạn

# Đọc file JSON từ thư mục output
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

# Trích và ghi vào Sheet
import os
for file in os.listdir("outputs"):
    if file.endswith(".json"):
        rows = extract_data_from_json(os.path.join("outputs", file))
        for row in rows:
            worksheet.append_row(row)
