import os
import sys
import json
from google.cloud import documentai_v1beta3 as documentai
from google.cloud.documentai_v1beta3 import types

# Đọc đường dẫn file PDF từ dòng lệnh
pdf_path = sys.argv[1]

# Ghi file key.json từ GOOGLE_CREDENTIALS_JSON
credentials_content = os.environ["GOOGLE_CREDENTIALS_JSON"]

with open("key.json", "w") as f:
    f.write(credentials_content)

# Đặt biến môi trường để dùng Application Default Credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"

# Khởi tạo Document AI client
client = documentai.DocumentProcessorServiceClient()

# Lấy thông tin project và processor ID từ biến môi trường
project_id = os.environ["GOOGLE_PROJECT_ID"]
location = os.environ.get("GOOGLE_LOCATION", "us")
processor_id = os.environ["GOOGLE_PROCESSOR_ID"]

# Gán tài nguyên processor
name = client.processor_path(project_id, location, processor_id)

# Đọc file PDF
with open(pdf_path, "rb") as f:
    document_content = f.read()

# Gửi yêu cầu OCR
raw_document = types.RawDocument(content=document_content, mime_type="application/pdf")
request = types.ProcessRequest(name=name, raw_document=raw_document)
result = client.process_document(request=request)

# Hiển thị nội dung đã nhận dạng
print("📄 Nội dung OCR:")
print(result.document.text)
