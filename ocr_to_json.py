import os
import json
from google.cloud import documentai_v1beta3 as documentai

# Thiết lập client
project_id = os.environ["GOOGLE_PROJECT_ID"]
location = "us"  # hoặc "asia-southeast1"
processor_id = os.environ["GOOGLE_PROCESSOR_ID"]

client = documentai.DocumentUnderstandingServiceClient()
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

input_dir = "outputs"
output_dir = "outputs"
os.makedirs(output_dir, exist_ok=True)

processed = 0

for file_name in os.listdir(input_dir):
    if file_name.endswith(".pdf"):
        pdf_path = os.path.join(input_dir, file_name)
        json_path = pdf_path.replace(".pdf", ".json")

        print(f"🧠 OCR file: {file_name}")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")

        try:
            result = client.process_document(
                request={"name": name, "raw_document": raw_document}
            )
            document = result.document

            if not document.pages:
                print(f"⚠️ Không có trang nào được OCR từ: {file_name}")
                continue

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(document._pb.__class__.to_dict(document._pb), f, ensure_ascii=False)

            print(f"✅ Đã OCR xong: {json_path}")
            os.remove(pdf_path)  # cleanup
            processed += 1

        except Exception as e:
            print(f"❌ Lỗi OCR {file_name}: {e}")

print(f"\n📄 Tổng số file OCR thành công: {processed}")
