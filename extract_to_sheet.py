import os
import json
import gspread
from google.oauth2.service_account import Credentials
import base64

# Lấy thông tin từ biến môi trường GitHub Actions
sheet_id = os.environ["GOOGLE_SHEET_ID"]
creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]

# Giải mã credentials từ chuỗi JSON
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict)
gc = gspread.authorize(creds)

# Chọn sheet cụ thể
sheet = gc.open_by_key(sheet_id).worksheet("Trang tính 2")

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
                    texts = [block.get("textBlock", {}).get("text", "") for block in cell.get("blocks", [])]
                    row_text.append(" ".join(texts))
                all_text.append(row_text)
    return all_text

# Ghi dữ liệu
for file in os.listdir("outputs"):
    if file.endswith(".json"):
        rows = extract_data_from_json(os.path.join("outputs", file))
        for row in rows:
            sheet.append_row(row)
