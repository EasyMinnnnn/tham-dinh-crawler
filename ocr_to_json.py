import os
import sys
import json
import shutil
import re
from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPICallError

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials as SheetCredentials

os.makedirs("preprocessed", exist_ok=True)

# 🔐 Load credentials
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

project_id = os.environ.get("GOOGLE_PROJECT_ID")
processor_id = os.environ.get("GOOGLE_PROCESSOR_ID")
location = os.environ.get("GOOGLE_LOCATION", "us")

if not project_id or not processor_id:
    print("❌ Thiếu GOOGLE_PROJECT_ID hoặc GOOGLE_PROCESSOR_ID.")
    sys.exit(1)

client = documentai.DocumentProcessorServiceClient(credentials=credentials)
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

def push_to_google_sheet(json_data: dict, sheet_range="Sheet1!A1"):
    try:
        sheet_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        sheet_id = os.environ.get("GOOGLE_SHEET_ID")
        if not sheet_json or not sheet_id:
            print("⚠️ Không có biến GOOGLE_CREDENTIALS_JSON hoặc GOOGLE_SHEET_ID.")
            return

        creds_dict = json.loads(sheet_json)
        creds = SheetCredentials.from_service_account_info(creds_dict)
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
        sheet.values().update(
            spreadsheetId=sheet_id,
            range=sheet_range,
            valueInputOption="RAW",
            body={"values": [[json_str]]}
        ).execute()
        print("📤 Đã push nội dung OCR JSON lên Google Sheet.")
    except Exception as e:
        print(f"❌ Lỗi khi push lên Google Sheet: {e}")

def fallback_from_manual_json(pdf_path, json_path):
    base_name = os.path.basename(json_path)
    manual_json_path = os.path.join("preprocessed", base_name)
    if os.path.exists(manual_json_path):
        shutil.copy(manual_json_path, json_path)
        print(f"🛠️ Dùng JSON thủ công từ preprocessed/: {manual_json_path}")
        return True
    return False

def fallback_from_any_document_json(pdf_path, json_path):
    pdf_basename = os.path.basename(pdf_path)
    document_files = [f for f in os.listdir(".") if re.match(r"document.*\.json$", f)]
    if not document_files:
        print("⚠️ Không tìm thấy file document*.json nào để fallback.")
        return False

    print(f"🔎 Đang thử fallback từ các file: {document_files}")
    for doc_file in sorted(document_files):
        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                print(f"📄 File {doc_file} chứa {len(data)} record.")
                for idx, record in enumerate(data):
                    input_source = record.get("inputSource", "")
                    if not input_source:
                        continue
                    if pdf_basename in input_source:
                        document_data = record.get("document", {})
                        with open(json_path, "w", encoding="utf-8") as out:
                            json.dump(document_data, out, ensure_ascii=False, indent=2)
                        print(f"🛠️ Fallback thành công từ {doc_file} (record {idx}) cho: {pdf_basename}")
                        return True
                    else:
                        print(f"⛔ Không khớp: {input_source} với {pdf_basename}")
        except Exception as e:
            print(f"❌ Lỗi đọc {doc_file}: {e}")
    print(f"⚠️ Không tìm thấy khớp trong bất kỳ document*.json nào cho: {pdf_basename}")
    return False

def process_file(pdf_path):
    json_path = pdf_path.replace(".pdf", ".json")
    print(f"\n🧠 OCR file: {pdf_path}")
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = {"name": name, "raw_document": raw_document}
        result = client.process_document(request=request)
        document = result.document

        if not document.text.strip() and not document.pages:
            print(f"⚠️ Không có văn bản OCR được từ: {pdf_path}")
            if fallback_from_manual_json(pdf_path, json_path) or fallback_from_any_document_json(pdf_path, json_path):
                print("📁 Đã fallback nhưng KHÔNG push lên Google Sheet vì không có kết quả OCR.")
                return True
            return False

        document_dict = document._pb.__class__.to_dict(document._pb)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(document_dict, f, ensure_ascii=False, indent=2)

        print(f"✅ Đã lưu file JSON: {json_path}")
        push_to_google_sheet(document_dict, sheet_range="Sheet1!A1")
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
        os.makedirs(input_dir, exist_ok=True)
        files = [f for f in os.listdir(input_dir) if f.endswith(".pdf")]
        success = 0
        for f in files:
            path = os.path.join(input_dir, f)
            if process_file(path):
                success += 1
        print(f"\n📊 Tổng số file đã xử lý thành công: {success}")
