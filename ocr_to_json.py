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
from google.protobuf.json_format import MessageToDict  # ✅ convert protobuf to dict

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

def extract_text(text_anchor, text):
    if not text_anchor.text_segments:
        return ""
    result = ""
    for segment in text_anchor.text_segments:
        start = segment.start_index if segment.start_index else 0
        end = segment.end_index
        result += text[start:end]
    return result.strip()

def extract_table_from_document(document):
    result_tables = []
    text = document.text
    for page in document.pages:
        for table in page.tables:
            table_rows = []
            # ✅ fix lỗi RepeatedComposite: convert cả hai về list
            for row in list(table.header_rows) + list(table.body_rows):
                row_cells = []
                for cell in row.cells:
                    cell_text = extract_text(cell.layout.text_anchor, text)
                    row_cells.append(cell_text)
                table_rows.append(row_cells)
            result_tables.append(table_rows)
    return result_tables

def push_table_to_google_sheet(table_rows, sheet_range="Sheet1!A1"):
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

        if not table_rows:
            print("⚠️ Không có bảng nào được tìm thấy.")
            return

        sheet.values().update(
            spreadsheetId=sheet_id,
            range=sheet_range,
            valueInputOption="RAW",
            body={"values": table_rows}
        ).execute()
        print("📤 Đã push bảng lên Google Sheet.")
    except Exception as e:
        print(f"❌ Lỗi khi push bảng lên Google Sheet: {e}")

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
        except Exception as e:
            print(f"❌ Lỗi đọc {doc_file}: {e}")
    print(f"⚠️ Không tìm thấy khớp trong bất kỳ document*.json nào cho: {pdf_basename}")
    return False

def process_file(pdf_path):
    json_path = pdf_path.replace(".pdf", ".json")
    print(f"\n📄 Đang xử lý file: {pdf_path}")
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document

        if not document.text.strip():
            print(f"⚠️ Không có văn bản OCR được từ: {pdf_path}")
            if fallback_from_manual_json(pdf_path, json_path) or fallback_from_any_document_json(pdf_path, json_path):
                print("📁 Đã fallback nhưng KHÔNG push lên Google Sheet vì không có kết quả OCR.")
                return True
            return False

        # ✅ Sửa lỗi to_dict → dùng MessageToDict
        document_dict = MessageToDict(document._pb, preserving_proto_field_name=True)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(document_dict, f, ensure_ascii=False, indent=2)

        print(f"✅ Đã lưu file JSON: {json_path}")

        tables = extract_table_from_document(document)
        if tables:
            push_table_to_google_sheet(tables[0])  # chỉ đẩy bảng đầu tiên
        else:
            print("⚠️ Không có bảng nào để push.")
        os.remove(pdf_path)
        return True

    except GoogleAPICallError as api_error:
        print(f"❌ Lỗi từ Google API: {api_error}")
    except Exception as e:
        print(f"❌ Lỗi khi xử lý {pdf_path}: {e}")
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
