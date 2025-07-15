import os
import sys
import json
from google.cloud import documentai_v1 as documentai
from google.protobuf.json_format import MessageToJson
from google.api_core.client_options import ClientOptions

def parse_pdf_with_docai(pdf_path):
    # --- Config ---
    project_id = "geocoding-api-464306"
    location = "eu"  # phải khớp với processor
    processor_id = "72cb2ba0beaa1f9d"
    mime_type = "application/pdf"

    # --- Load credentials từ biến môi trường ---
    creds_json = os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"]
    creds_dict = json.loads(creds_json)

    # --- Setup endpoint theo vùng ---
    endpoint = f"{location}-documentai.googleapis.com"
    opts = ClientOptions(api_endpoint=endpoint)

    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    # --- Đọc nội dung file PDF ---
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()

    raw_document = documentai.RawDocument(content=pdf_content, mime_type=mime_type)
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)

    print("📄 Đang gửi tài liệu lên Document AI...")
    result = client.process_document(request=request)
    return result.document

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("⚠️ Cách dùng: python ocr_to_json.py outputs/tenfile.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print("❌ File không tồn tại:", pdf_path)
        sys.exit(1)

    os.makedirs("outputs", exist_ok=True)

    try:
        document = parse_pdf_with_docai(pdf_path)

        json_name = os.path.splitext(os.path.basename(pdf_path))[0] + ".json"
        json_path = os.path.join("outputs", json_name)

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(MessageToJson(document))

        print(f"✅ Đã lưu kết quả OCR vào: {json_path}")
    except Exception as e:
        print("❌ Lỗi khi OCR:", e)
