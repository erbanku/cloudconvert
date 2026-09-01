from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))

from cloudconvert_client import (
    CloudConvertClient,
    build_pdf_to_docx_options,
    filter_office_operations,
    prepare_input_file,
)


class FakeResponse:
    def __init__(self, payload: dict, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode("utf-8")
        self.text = json.dumps(payload)
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.text)


class FakeSession:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def request(self, **kwargs):
        self.requests.append(kwargs)
        if kwargs["method"] == "POST" and kwargs["url"].endswith("/jobs"):
            return FakeResponse(
                {
                    "data": {
                        "id": "job-1",
                        "tasks": [
                            {"id": "import-1", "name": "import_file"},
                            {"id": "export-1", "name": "export_file"},
                        ],
                    }
                }
            )
        return FakeResponse({"data": []})


def test_pdf_to_docx_options_match_cloudconvert_pdf_options() -> None:
    options = build_pdf_to_docx_options(
        {
            "pages": "1-3",
            "connect_hyphens": False,
            "prioritize_visual_appearance": True,
            "images_ocr": True,
        }
    )

    assert options == {
        "pages": "1-3",
        "connect_hyphens": False,
        "prioritize_visual_appearance": True,
        "images_ocr": True,
    }


def test_prepare_input_file_accepts_dify_blob_shape() -> None:
    prepared = prepare_input_file(
        {
            "filename": "scan",
            "extension": "pdf",
            "mime_type": "application/pdf",
            "blob": b"%PDF-1.7",
        }
    )

    assert prepared.filename == "scan.pdf"
    assert prepared.mime_type == "application/pdf"
    assert prepared.content == b"%PDF-1.7"


def test_create_conversion_job_uses_upload_convert_export_tasks() -> None:
    session = FakeSession()
    client = CloudConvertClient({"api_key": "key"}, session=session)  # type: ignore[arg-type]

    job = client.create_conversion_job(
        input_format="pdf",
        output_format="docx",
        options={"pages": "1-2", "images_ocr": True},
    )

    assert job["id"] == "job-1"
    request = session.requests[0]
    assert request["method"] == "POST"
    payload = request["json"]
    assert payload["tasks"]["import_file"]["operation"] == "import/upload"
    assert payload["tasks"]["convert_file"]["operation"] == "convert"
    assert payload["tasks"]["convert_file"]["input"] == "import_file"
    assert payload["tasks"]["convert_file"]["input_format"] == "pdf"
    assert payload["tasks"]["convert_file"]["output_format"] == "docx"
    assert payload["tasks"]["convert_file"]["pages"] == "1-2"
    assert payload["tasks"]["export_file"]["operation"] == "export/url"


def test_office_filter_keeps_office_related_operations() -> None:
    operations = [
        {"input_format": "docx", "output_format": "pdf"},
        {"input_format": "mp4", "output_format": "webm"},
        {"input_format": "pdf", "output_format": "png"},
    ]

    filtered = filter_office_operations(operations, office_only=True, limit=10)

    assert filtered == [operations[0], operations[2]]


def test_prepare_input_file_requires_content_or_url() -> None:
    with pytest.raises(Exception, match="does not include file bytes"):
        prepare_input_file({"filename": "missing.docx"})
