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
from google.protobuf.json_format import MessageToDict

os.makedirs("preprocessed", exist_ok=True)

# 🔐 Load credentials
credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if not credentials_json:
    print("❌ Thiếu biến GOOGLE_APPLICATION_CREDENTIALS_JSON.")
    sys.exit(1)

try:
    credentials_dict = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
except Exception as e:
    print(f"❌ GOOGLE_APPLICATION_CREDENTIALS_JSON không hợp lệ: {e}")
    sys.exit(1)

project_id = os.environ.get("GOOGLE_PROJECT_ID")
processor_id = os.environ.get("GOOGLE_PROCESSOR_ID")  # Form Parser
processor_id_ocr = os.environ.get("GOOGLE_PROCESSOR_ID_OCR")  # Document OCR
location = os.environ.get("GOOGLE_LOCATION", "us")

if not project_id or not processor_id or not processor_id_ocr:
    print("❌ Thiếu GOOGLE_PROJECT_ID hoặc PROCESSOR_ID hoặc PROCESSOR_ID_OCR.")
    sys.exit(1)

client = documentai.DocumentProcessorServiceClient(credentials=credentials)
name_form_parser = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
name_doc_ocr = f"projects/{project_id}/locations/{location}/processors/{processor_id_ocr}"

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
            for row in list(table.header_rows) + list(table.body_rows):
                row_cells = []
                for cell in row.cells:
                    cell_text = extract_text(cell.layout.text_anchor, text)
                    row_cells.append(cell_text)
                table_rows.append(row_cells)
            result_tables.append(table_rows)
    return result_tables

def extract_fields_from_ocr(pdf_bytes):
    try:
        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name_doc_ocr, raw_document=raw_document)
        result = client.process_document(request=request)
        text = result.document.text
        print("📄 Văn bản OCR trích được:\n" + "-"*40 + f"\n{text}\n" + "-"*40)

        company_match = re.search(r"(Công\s*ty[\s\S]{0,200}?\([^\)]+T[ĐD]G\))", text, re.IGNORECASE)
        company_name = company_match.group(1).strip() if company_match else ""

        sohieu_match = re.search(r"Số[:\s]+(\d+)(?=/TB-BTC)", text, re.IGNORECASE)
        sohieu = sohieu_match.group(1).strip() if sohieu_match else ""

        time_match = re.search(r"Thời gian ký[:\s]+([^\n]+)", text)
        sign_time = time_match.group(1).strip() if time_match else ""

        return company_name, sohieu, sign_time
    except Exception as e:
        print(f"⚠️ Lỗi OCR Document: {e}")
        return "", "", ""

def push_data_to_google_sheet(company_name, table_rows, sohieu, sign_time):
    try:
        sheet_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        sheet_id = os.environ.get("GOOGLE_SHEET_ID")
        if not sheet_json or not sheet_id:
            print("⚠️ Thiếu GOOGLE_CREDENTIALS_JSON hoặc GOOGLE_SHEET_ID.")
            return

        creds_dict = json.loads(sheet_json)
        creds = SheetCredentials.from_service_account_info(creds_dict)
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        data = []

        if company_name:
            data.append({"range": "Sheet1!A1", "values": [[company_name]]})

        if table_rows:
            data.append({"range": "Sheet1!C1", "values": table_rows})

        if sohieu:
            data.append({"range": "Sheet1!H2", "values": [[sohieu]]})

        if sign_time:
            data.append({"range": "Sheet1!I2", "values": [[sign_time]]})

        if not data:
            print("⚠️ Không có dữ liệu nào để ghi vào Google Sheet.")
            return

        sheet.values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": data}
        ).execute()
        print("📤 Đã ghi toàn bộ dữ liệu vào Google Sheet.")
    except Exception as e:
        print(f"❌ Lỗi khi push dữ liệu lên Google Sheet: {e}")

def process_file(pdf_path, override_sohieu=None):
    json_path = pdf_path.replace(".pdf", ".json")
    print(f"\n📄 Đang xử lý file: {pdf_path}")
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        company_name, sohieu, sign_time = extract_fields_from_ocr(pdf_bytes)

        if override_sohieu:
            sohieu = override_sohieu

        raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name_form_parser, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document

        if not document.text.strip():
            print(f"⚠️ Không có văn bản OCR được từ: {pdf_path}")
            return False

        document_dict = MessageToDict(document._pb, preserving_proto_field_name=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(document_dict, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã lưu file JSON: {json_path}")

        tables = extract_table_from_document(document)
        table_rows = tables[0] if tables else []

        push_data_to_google_sheet(company_name, table_rows, sohieu, sign_time)

        os.remove(pdf_path)
        return True

    except GoogleAPICallError as api_error:
        print(f"❌ Lỗi từ Google API: {api_error}")
    except Exception as e:
        print(f"❌ Lỗi khi xử lý {pdf_path}: {e}")
    return False

if __name__ == "__main__":
    input_dir = "outputs"
    os.makedirs(input_dir, exist_ok=True)
    files = [f for f in os.listdir(input_dir) if f.endswith(".pdf")]
    override_sohieu = sys.argv[2] if len(sys.argv) > 2 else None
    success = 0
    for f in files:
        path = os.path.join(input_dir, f)
        if process_file(path, override_sohieu):
            success += 1
    print(f"\n📊 Tổng số file đã xử lý thành công: {success}")
