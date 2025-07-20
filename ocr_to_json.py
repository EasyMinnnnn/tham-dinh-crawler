import os
import sys
import json
from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPICallError

# 🔐 Lấy đường dẫn file credentials từ biến môi trường và đọc nội dung
credentials_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
with open(credentials_path, "r", encoding="utf-8") as f:
    credentials_dict = json.load(f)
credentials = service_account.Credentials.from_service_account_info(credentials_dict)

# ⚙️ Khởi tạo Document AI client
project_id = os.environ["GOOGLE_PROJECT_ID"]
location = "us"
processor_id = os.environ["GOOGLE_PROCESSOR_ID"]

client = documentai.DocumentProcessorServiceClient(credentials=credentials)
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

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
        if not document.pages:
            print(f"⚠️ Không có trang nào được OCR từ: {pdf_path}")
            return False

        document_dict = document._pb.__class__.to_dict(document._pb)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(document_dict, f, ensure_ascii=False)

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
        process_file(pdf_file)
    else:
        # Chạy toàn bộ thư mục nếu không có đối số
        input_dir = "outputs"
        files = [f for f in os.listdir(input_dir) if f.endswith(".pdf")]
        success = 0
        for f in files:
            path = os.path.join(input_dir, f)
            if process_file(path):
                success += 1
        print(f"\n📄 Tổng số file OCR thành công: {success}")
