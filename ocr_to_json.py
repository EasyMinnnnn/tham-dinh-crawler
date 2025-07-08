# src/ocr_to_json.py
import os
import json
from google.cloud import documentai_v1 as documentai
from google.protobuf.json_format import MessageToJson

def parse_pdf_with_docai(pdf_path):
    project_id = "geocoding-api-464306"
    location = "eu" 
    processor_id = "72cb2ba0beaa1f9d"

    # Load from ENV secret
    creds_json = os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"]
    with open("gcloud_key.json", "w", encoding="utf-8") as f:
        f.write(creds_json)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcloud_key.json"

    client = documentai.DocumentProcessorServiceClient()
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    with open(pdf_path, "rb") as f:
        pdf_content = f.read()

    raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    result = client.process_document(request=request)
    return result.document

if __name__ == "__main__":
    os.makedirs("outputs", exist_ok=True)
    document = parse_pdf_with_docai("outputs/downloaded.pdf")
    with open("outputs/result.json", "w", encoding="utf-8") as f:
        f.write(MessageToJson(document))
