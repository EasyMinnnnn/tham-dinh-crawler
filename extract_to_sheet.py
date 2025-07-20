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
sheet_name = os.getenv("SHEET_NAME", "Trang tính1")  # ✅ Đổi tên tại đây nếu cần
worksheet = gc.open_by_key(sheet_id).worksheet(sheet_name)

# Hàm trích dữ liệu từ JSON OCR
def extract_data_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ JSON lỗi cú pháp: {json_path} – {e}")
            return []

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
                if any(cell for cell in row_text):
                    all_text.append(row_text)
    return all_text

# Quét thư mục outputs và xử lý file .json
json_dir = "outputs"
processed = 0

for file in os.listdir(json_dir):
    if file.endswith(".json"):
        file_path = os.path.join(json_dir, file)
        print(f"📄 Đang xử lý file: {file}")
        try:
            rows = extract_data_from_json(file_path)
            if rows:
                preview = rows[0]
                print(f"👀 Dòng đầu tiên preview: {preview}")
                worksheet.append_rows(rows, value_input_option="RAW")
                print(f"✅ Đã ghi {len(rows)} dòng vào Google Sheet.")
            else:
                print(f"⚠️ Không có dữ liệu bảng trong file: {file}")
            os.remove(file_path)
            processed += 1
        except Exception as e:
            print(f"❌ Lỗi khi xử lý {file}: {e}")

print(f"\n📊 Tổng số file đã xử lý thành công: {processed}")
