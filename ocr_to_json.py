import os
import json
from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPICallError

# 🔐 Tải credentials từ biến môi trường (dạng JSON)
credentials_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
credentials_dict = json.loads(credentials_json)
credentials = service_account.Credentials.from_service_account_info(credentials_dict)

# ⚙️ Thiết lập Document AI client
project_id = os.environ["GOOGLE_PROJECT_ID"]
location = "us"
processor_id = os.environ["GOOGLE_PROCESSOR_ID"]

client = documentai.DocumentProcessorServiceClient(credentials=credentials)
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

input_dir = "outputs"
processed = 0

for filename in os.listdir(input_dir):
    if filename.endswith(".pdf"):
        pdf_path = os.path.join(input_dir, filename)
        json_path = pdf_path.replace(".pdf", ".json")

        print(f"🧠 OCR file: {filename}")
        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            raw_document = documentai.RawDocument(
                content=pdf_bytes, mime_type="application/pdf"
            )

            request = {"name": name, "raw_document": raw_document}
            result = client.process_document(request=request)

            document = result.document
            if not document.pages:
                print(f"⚠️ Không có trang nào được OCR từ: {filename}")
                continue

            document_dict = document._pb.__class__.to_dict(document._pb)

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(document_dict, f, ensure_ascii=False)

            print(f"✅ Đã lưu file JSON: {json_path}")
            os.remove(pdf_path)
            processed += 1

        except GoogleAPICallError as api_error:
            print(f"❌ Lỗi từ Google API: {api_error}")
        except Exception as e:
            print(f"❌ Lỗi khác khi OCR {filename}: {e}")

print(f"\n📄 Tổng số file OCR thành công: {processed}")
