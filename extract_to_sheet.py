import os
import json
import gspread
from google.oauth2.service_account import Credentials

# Thiết lập Google Sheet API
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Nhận credentials từ biến môi trường
creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
CREDS = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
gc = gspread.authorize(CREDS)

# Lấy thông tin sheet
sheet_id = os.environ["GOOGLE_SHEET_ID"]
sheet_name = os.getenv("SHEET2_NAME", "Trang tính2")
worksheet = gc.open_by_key(sheet_id).worksheet(sheet_name)

# Trích dữ liệu từ file JSON OCR
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

# Quét thư mục và ghi dữ liệu
json_dir = "outputs"
processed = 0

for file in os.listdir(json_dir):
    if file.endswith(".json"):
        file_path = os.path.join(json_dir, file)
        try:
            rows = extract_data_from_json(file_path)
            if rows:
                worksheet.append_rows(rows)
                print(f"✅ Đã ghi {len(rows)} dòng từ: {file}")
            else:
                print(f"⚠️ Không có bảng nào trong file: {file}")
            os.remove(file_path)  # Xóa file đã xử lý
            processed += 1
        except Exception as e:
            print(f"❌ Lỗi xử lý {file}: {e}")

print(f"\n📊 Tổng số file đã xử lý: {processed}")
