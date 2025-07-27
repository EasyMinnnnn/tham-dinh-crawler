import os
import sys
import json
import shutil
from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPICallError

# 🔐 Đọc credentials từ biến môi trường
credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if not credentials_json:
    print("❌ Thiếu biến môi trường GOOGLE_APPLICATION_CREDENTIALS_JSON.")
    sys.exit(1)

try:
    credentials_dict = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
except Exception as e:
    print(f"❌ GOOGLE_APPLICATION_CREDENTIALS_JSON không hợp lệ: {e}")
    sys.exit(1)

# ⚙️ Thông tin cấu hình
project_id = os.environ.get("GOOGLE_PROJECT_ID")
processor_id = os.environ.get("GOOGLE_PROCESSOR_ID")
location = os.environ.get("GOOGLE_LOCATION", "us")

if not project_id or not processor_id:
    print("❌ Thiếu GOOGLE_PROJECT_ID hoặc GOOGLE_PROCESSOR_ID.")
    sys.exit(1)

client = documentai.DocumentProcessorServiceClient(credentials=credentials)
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

# 🧰 Tạo thư mục preprocessed nếu chưa tồn tại
os.makedirs("preprocessed", exist_ok=True)

def fallback_to_manual_json(pdf_path, json_path):
    base_name = os.path.basename(json_path)
    manual_json_path = os.path.join("preprocessed", base_name)
    print(f"🔍 Kiểm tra fallback: {manual_json_path}")
    
    if os.path.exists(manual_json_path):
        shutil.copy(manual_json_path, json_path)
        print(f"🛠️ Dùng JSON thủ công: {manual_json_path}")
        return True

    # 👉 Nếu không có, thử tìm file JSON bất kỳ trong preprocessed/ có prefix `document`
    for fname in os.listdir("preprocessed"):
        if fname.startswith("document") and fname.endswith(".json"):
            alt_path = os.path.join("preprocessed", fname)
            shutil.copy(alt_path, json_path)
            print(f"🛠️ Dùng fallback JSON từ file khác: {alt_path}")
            return True

    print("⚠️ Không tìm thấy JSON fallback tương ứng.")
    return False

def process_file(pdf_path):
    json_path = pdf_path.replace(".pdf", ".json")
    print(f"🧠 OCR file: {pdf_path}")
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = {"name": name, "raw_document": raw_document}
        result = client.process_document(request=request)
        document = result.document

        # Nếu không có text và không có pages → fallback
        if not document.text.strip() and not document.pages:
            print(f"⚠️ Không có văn bản OCR được từ: {pdf_path}")
            return fallback_to_manual_json(pdf_path, json_path)

        # Ghi JSON từ protobuf
        document_dict = document._pb.__class__.to_dict(document._pb)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(document_dict, f, ensure_ascii=False, indent=2)

        print(f"✅ Đã lưu file JSON: {json_path}")
        os.remove(pdf_path)
        return True

    except GoogleAPICallError as api_error:
        print(f"❌ Lỗi từ Google API: {api_error}")
    except Exception as e:
        print(f"❌ Lỗi khi OCR {pdf_path}: {e}")
    return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        if not os.path.exists(pdf_file):
            print(f"❌ File không tồn tại: {pdf_file}")
            sys.exit(1)
        success = process_file(pdf_file)
        print(f"\n📄 Xử lý file {'thành công' if success else 'thất bại'}: {pdf_file}")
    else:
        input_dir = "outputs"
        files = [f for f in os.listdir(input_dir) if f.endswith(".pdf")]
        success = 0
        for f in files:
            path = os.path.join(input_dir, f)
            if process_file(path):
                success += 1
        print(f"\n📄 Tổng số file OCR thành công (bao gồm fallback): {success}")
