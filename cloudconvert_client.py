from __future__ import annotations

import json
import mimetypes
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests


DEFAULT_API_BASE_URL = "https://api.cloudconvert.com/v2"
REQUEST_TIMEOUT_SECONDS = 60
UPLOAD_TIMEOUT_SECONDS = 600
DOWNLOAD_TIMEOUT_SECONDS = 600
DEFAULT_WAIT_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 2.0

PDF_TO_DOCX_OPTION_KEYS = (
    "pages",
    "password",
    "connect_hyphens",
    "prioritize_visual_appearance",
    "images_ocr",
)

OFFICE_FORMATS = {
    "csv",
    "doc",
    "docm",
    "docx",
    "dot",
    "dotx",
    "html",
    "odp",
    "ods",
    "odt",
    "pdf",
    "pot",
    "potx",
    "pps",
    "ppsx",
    "ppt",
    "pptm",
    "pptx",
    "rtf",
    "txt",
    "xls",
    "xlsm",
    "xlsx",
    "xlt",
    "xltx",
    "jpg",
    "jpeg",
    "png",
}


class CloudConvertError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass(slots=True)
class PreparedInputFile:
    filename: str
    mime_type: str
    content: bytes


@dataclass(slots=True)
class ConvertedFile:
    filename: str
    mime_type: str
    content: bytes
    url: str
    size_bytes: int


def clean_string(value: Any) -> str:
    return str(value or "").strip()


def normalize_format(value: Any) -> str:
    text = clean_string(value).lower()
    if text.startswith("."):
        text = text[1:]
    return text


def resolve_api_base_url(credentials: dict[str, Any]) -> str:
    raw_url = clean_string(credentials.get("api_base_url")) or DEFAULT_API_BASE_URL
    raw_url = raw_url.rstrip("/")
    if not raw_url.startswith(("https://", "http://")):
        raise CloudConvertError("CloudConvert API Base URL must start with https:// or http://.")
    parsed = urlparse(raw_url)
    if not parsed.netloc:
        raise CloudConvertError("CloudConvert API Base URL is invalid.")
    if not parsed.path.endswith("/v2"):
        raw_url = f"{raw_url}/v2"
    return raw_url


def infer_format_from_filename(filename: str) -> str:
    suffix = os.path.splitext(filename)[1].lower().lstrip(".")
    if not suffix:
        raise CloudConvertError(
            "input_format is required when the input file name does not include an extension."
        )
    return suffix


def parse_bool(value: Any, *, default: bool | None = None) -> bool | None:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = clean_string(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise CloudConvertError(f"Invalid boolean value: {value!r}")


def parse_wait_timeout(value: Any) -> int:
    if value is None or value == "":
        return DEFAULT_WAIT_TIMEOUT_SECONDS
    try:
        timeout = int(value)
    except (TypeError, ValueError) as exc:
        raise CloudConvertError("wait_timeout_seconds must be a number.") from exc
    return max(30, min(timeout, 900))


def parse_options_json(raw_value: Any) -> dict[str, Any]:
    if raw_value is None or raw_value == "":
        return {}
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if not isinstance(raw_value, str):
        raise CloudConvertError("options_json must be a JSON object string.")
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise CloudConvertError(f"options_json must be valid JSON: {exc.msg}.") from exc
    if not isinstance(parsed, dict):
        raise CloudConvertError("options_json must decode to a JSON object.")
    return parsed


def build_pdf_to_docx_options(tool_parameters: dict[str, Any]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    pages = clean_string(tool_parameters.get("pages"))
    if pages:
        options["pages"] = pages
    password = clean_string(tool_parameters.get("password"))
    if password:
        options["password"] = password
    options["connect_hyphens"] = parse_bool(
        tool_parameters.get("connect_hyphens"), default=False
    )
    options["prioritize_visual_appearance"] = parse_bool(
        tool_parameters.get("prioritize_visual_appearance"), default=True
    )
    options["images_ocr"] = parse_bool(tool_parameters.get("images_ocr"), default=True)
    return {key: value for key, value in options.items() if value is not None}


def build_generic_convert_options(tool_parameters: dict[str, Any]) -> dict[str, Any]:
    options = parse_options_json(tool_parameters.get("options_json"))
    engine = clean_string(tool_parameters.get("engine"))
    if engine:
        options["engine"] = engine
    engine_version = clean_string(tool_parameters.get("engine_version"))
    if engine_version:
        options["engine_version"] = engine_version
    return options


def get_file_field(file_obj: Any, *field_names: str) -> Any:
    for field_name in field_names:
        if isinstance(file_obj, dict) and field_name in file_obj:
            return file_obj[field_name]
        value = getattr(file_obj, field_name, None)
        if value is not None:
            return value
    return None


def normalize_file_name(file_obj: Any) -> str:
    filename = clean_string(get_file_field(file_obj, "filename", "name"))
    extension = clean_string(get_file_field(file_obj, "extension"))
    if not filename:
        filename = "input"
    filename = os.path.basename(filename)
    if extension:
        extension = extension if extension.startswith(".") else f".{extension}"
        if not filename.lower().endswith(extension.lower()):
            filename = f"{filename}{extension}"
    return filename


def decode_file_blob(blob: Any) -> bytes | None:
    if blob is None:
        return None
    if isinstance(blob, bytes):
        return blob
    if isinstance(blob, bytearray):
        return bytes(blob)
    if isinstance(blob, memoryview):
        return blob.tobytes()
    if isinstance(blob, str):
        return blob.encode("utf-8")
    try:
        return bytes(blob)
    except TypeError as exc:
        raise CloudConvertError("Dify file blob could not be converted to bytes.") from exc


def prepare_input_file(file_value: Any, downloader: Any | None = None) -> PreparedInputFile:
    if isinstance(file_value, (list, tuple)):
        if not file_value:
            raise CloudConvertError("input_file is required.")
        file_value = file_value[0]
    if file_value is None:
        raise CloudConvertError("input_file is required.")

    filename = normalize_file_name(file_value)
    mime_type = clean_string(get_file_field(file_value, "mime_type", "mimeType"))
    content = decode_file_blob(get_file_field(file_value, "blob"))
    if content is None:
        file_url = clean_string(get_file_field(file_value, "url", "remote_url", "download_url"))
        if not file_url:
            raise CloudConvertError(
                f"Input file '{filename}' does not include file bytes or a downloadable URL."
            )
        request_get = downloader or requests.get
        try:
            response = request_get(file_url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CloudConvertError(
                f"Failed to download input file '{filename}' from Dify storage: {exc}"
            ) from exc
        content = response.content
        if not mime_type:
            mime_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()

    if not content:
        raise CloudConvertError(f"Input file '{filename}' is empty.")
    if not mime_type:
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return PreparedInputFile(filename=filename, mime_type=mime_type, content=content)


def output_mime_type(filename: str, response: requests.Response) -> str:
    mime_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
    if mime_type and mime_type != "application/octet-stream":
        return mime_type
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


class CloudConvertClient:
    def __init__(
        self,
        credentials: dict[str, Any],
        *,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = clean_string(credentials.get("api_key"))
        if not self.api_key:
            raise CloudConvertError("CloudConvert API Key is required.")
        self.base_url = resolve_api_base_url(credentials)
        self.session = session or requests.Session()

    def request(
        self,
        method: str,
        path: str,
        *,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
        **kwargs: Any,
    ) -> dict[str, Any]:
        url = path if path.startswith(("https://", "http://")) else f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            **headers,
        }
        if kwargs.get("json") is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise CloudConvertError(f"CloudConvert API request failed: {exc}") from exc

        if response.status_code >= 400:
            raise self._response_error(response)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise CloudConvertError("CloudConvert API returned invalid JSON.") from exc

    def validate_credentials(self) -> None:
        self.request("GET", "/tasks", params={"per_page": 1})

    def list_operations(
        self,
        *,
        input_format: str = "",
        output_format: str = "",
        include_options: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"filter[operation]": "convert"}
        if input_format:
            params["filter[input_format]"] = input_format
        if output_format:
            params["filter[output_format]"] = output_format
        if include_options:
            params["include"] = "options"
        payload = self.request("GET", "/operations", params=params)
        data = payload.get("data") or []
        if not isinstance(data, list):
            raise CloudConvertError("CloudConvert operations response was not a list.")
        return data

    def convert_file(
        self,
        *,
        input_file: PreparedInputFile,
        input_format: str,
        output_format: str,
        options: dict[str, Any] | None = None,
        wait_timeout_seconds: int = DEFAULT_WAIT_TIMEOUT_SECONDS,
    ) -> tuple[dict[str, Any], list[ConvertedFile]]:
        input_format = normalize_format(input_format) or infer_format_from_filename(
            input_file.filename
        )
        output_format = normalize_format(output_format)
        if not output_format:
            raise CloudConvertError("output_format is required.")

        job = self.create_conversion_job(
            input_format=input_format,
            output_format=output_format,
            options=options or {},
        )
        import_task = self.find_named_task(job, "import_file")
        export_task = self.find_named_task(job, "export_file")
        self.upload_import_file(import_task, input_file)
        finished_export = self.wait_for_task(
            str(export_task["id"]),
            wait_timeout_seconds=wait_timeout_seconds,
        )
        converted_files = self.download_exported_files(finished_export, output_format)
        summary = {
            "job_id": job.get("id"),
            "import_task_id": import_task.get("id"),
            "export_task_id": export_task.get("id"),
            "input_filename": input_file.filename,
            "input_format": input_format,
            "output_format": output_format,
        }
        return summary, converted_files

    def create_conversion_job(
        self,
        *,
        input_format: str,
        output_format: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        convert_task: dict[str, Any] = {
            "operation": "convert",
            "input": "import_file",
            "input_format": input_format,
            "output_format": output_format,
        }
        convert_task.update(options)
        payload = {
            "tag": f"dify-cloudconvert-{input_format}-to-{output_format}",
            "tasks": {
                "import_file": {"operation": "import/upload"},
                "convert_file": convert_task,
                "export_file": {"operation": "export/url", "input": "convert_file"},
            },
        }
        response = self.request("POST", "/jobs", json=payload)
        data = response.get("data")
        if not isinstance(data, dict):
            raise CloudConvertError("CloudConvert did not return a job object.")
        return data

    @staticmethod
    def find_named_task(job: dict[str, Any], name: str) -> dict[str, Any]:
        for task in job.get("tasks") or []:
            if task.get("name") == name:
                return task
        raise CloudConvertError(f"CloudConvert job is missing task '{name}'.")

    def upload_import_file(self, import_task: dict[str, Any], input_file: PreparedInputFile) -> None:
        form = ((import_task.get("result") or {}).get("form") or {})
        if not form.get("url"):
            import_task = self.wait_for_upload_form(str(import_task.get("id")))
            form = ((import_task.get("result") or {}).get("form") or {})
        upload_url = form.get("url")
        parameters = form.get("parameters") or {}
        if not upload_url or not isinstance(parameters, dict):
            raise CloudConvertError("CloudConvert did not return an upload form.")
        try:
            response = self.session.post(
                str(upload_url),
                data=parameters,
                files={
                    "file": (
                        input_file.filename,
                        input_file.content,
                        input_file.mime_type,
                    )
                },
                timeout=UPLOAD_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CloudConvertError(f"Failed to upload file to CloudConvert: {exc}") from exc

    def wait_for_upload_form(self, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            task = self.get_task(task_id)
            form = ((task.get("result") or {}).get("form") or {})
            if form.get("url"):
                return task
            time.sleep(0.5)
        raise CloudConvertError("Timed out waiting for the CloudConvert upload form.")

    def wait_for_task(self, task_id: str, *, wait_timeout_seconds: int) -> dict[str, Any]:
        deadline = time.monotonic() + wait_timeout_seconds
        while time.monotonic() < deadline:
            task = self.get_task(task_id)
            status = task.get("status")
            if status == "finished":
                return task
            if status == "error":
                message = clean_string(task.get("message")) or "CloudConvert task failed."
                code = clean_string(task.get("code")) or None
                raise CloudConvertError(message, code=code)
            time.sleep(POLL_INTERVAL_SECONDS)
        raise CloudConvertError(
            f"Timed out waiting for CloudConvert task {task_id} after {wait_timeout_seconds} seconds."
        )

    def get_task(self, task_id: str) -> dict[str, Any]:
        response = self.request("GET", f"/tasks/{task_id}")
        data = response.get("data")
        if not isinstance(data, dict):
            raise CloudConvertError("CloudConvert did not return a task object.")
        return data

    def download_exported_files(
        self, export_task: dict[str, Any], output_format: str
    ) -> list[ConvertedFile]:
        files = ((export_task.get("result") or {}).get("files") or [])
        if not files:
            raise CloudConvertError("CloudConvert export task did not return any files.")
        converted_files: list[ConvertedFile] = []
        for index, file_info in enumerate(files, start=1):
            url = clean_string(file_info.get("url"))
            if not url:
                raise CloudConvertError("CloudConvert export file did not include a download URL.")
            filename = clean_string(file_info.get("filename")) or f"converted-{index}.{output_format}"
            try:
                response = requests.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise CloudConvertError(f"Failed to download CloudConvert output: {exc}") from exc
            converted_files.append(
                ConvertedFile(
                    filename=filename,
                    mime_type=output_mime_type(filename, response),
                    content=response.content,
                    url=url,
                    size_bytes=len(response.content),
                )
            )
        return converted_files

    @staticmethod
    def _response_error(response: requests.Response) -> CloudConvertError:
        message = response.text.strip() or "CloudConvert API returned an error."
        code: str | None = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            message = clean_string(payload.get("message")) or message
            code = clean_string(payload.get("code")) or None
            errors = payload.get("errors")
            if isinstance(errors, dict) and errors:
                details = []
                for key, value in errors.items():
                    if isinstance(value, list):
                        details.append(f"{key}: {', '.join(str(item) for item in value)}")
                    else:
                        details.append(f"{key}: {value}")
                if details:
                    message = f"{message} ({'; '.join(details)})"
        if response.status_code in {401, 403}:
            message = (
                "CloudConvert authentication failed. Check the API key and make sure it "
                f"has task.read and task.write scopes. {message}"
            ).strip()
        return CloudConvertError(message, status_code=response.status_code, code=code)


def filter_office_operations(
    operations: list[dict[str, Any]],
    *,
    office_only: bool,
    limit: int,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for operation in operations:
        if office_only:
            input_format = normalize_format(operation.get("input_format"))
            output_format = normalize_format(operation.get("output_format"))
            if input_format not in OFFICE_FORMATS and output_format not in OFFICE_FORMATS:
                continue
        filtered.append(operation)
        if len(filtered) >= limit:
            break
    return filtered
