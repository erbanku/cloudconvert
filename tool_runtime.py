from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from cloudconvert_client import (
    CloudConvertClient,
    CloudConvertError,
    OFFICE_FORMATS,
    build_generic_convert_options,
    build_pdf_to_docx_options,
    clean_string,
    filter_office_operations,
    infer_format_from_filename,
    normalize_format,
    parse_bool,
    parse_wait_timeout,
    prepare_input_file,
)


def emit_error(tool: Tool, action: str, exc: Exception) -> Generator[ToolInvokeMessage, None, None]:
    message = str(exc)
    yield tool.create_text_message(f"CloudConvert {action} failed: {message}")
    yield tool.create_json_message(
        {
            "status": "error",
            "action": action,
            "error": message,
            "error_type": exc.__class__.__name__,
        }
    )


def emit_conversion_result(
    tool: Tool,
    *,
    action: str,
    tool_parameters: dict[str, Any],
    input_format: str,
    output_format: str,
    options: dict[str, Any],
) -> Generator[ToolInvokeMessage, None, None]:
    try:
        input_file = prepare_input_file(tool_parameters.get("input_file"))
        input_format = normalize_format(input_format) or infer_format_from_filename(
            input_file.filename
        )
        output_format = normalize_format(output_format)
        wait_timeout_seconds = parse_wait_timeout(tool_parameters.get("wait_timeout_seconds"))

        client = CloudConvertClient(tool.runtime.credentials)
        summary, converted_files = client.convert_file(
            input_file=input_file,
            input_format=input_format,
            output_format=output_format,
            options=options,
            wait_timeout_seconds=wait_timeout_seconds,
        )

        output_files = [
            {
                "filename": item.filename,
                "mime_type": item.mime_type,
                "size_bytes": item.size_bytes,
                "url": item.url,
            }
            for item in converted_files
        ]
        result = {
            "status": "success",
            "action": action,
            **summary,
            "output_file_count": len(converted_files),
            "output_files": output_files,
        }
        first = converted_files[0]
        yield tool.create_text_message(
            f"Converted {input_file.filename} from {input_format} to {output_format}."
        )
        yield tool.create_variable_message("job_id", summary.get("job_id"))
        yield tool.create_variable_message("export_task_id", summary.get("export_task_id"))
        yield tool.create_variable_message("output_filename", first.filename)
        yield tool.create_variable_message("output_format", output_format)
        yield tool.create_variable_message("output_file_count", len(converted_files))
        yield tool.create_json_message(result)
        for converted_file in converted_files:
            yield tool.create_blob_message(
                blob=converted_file.content,
                meta={
                    "mime_type": converted_file.mime_type,
                    "filename": converted_file.filename,
                },
            )
    except CloudConvertError as exc:
        yield from emit_error(tool, action, exc)
    except Exception as exc:  # pragma: no cover - runtime safeguard
        yield from emit_error(tool, action, exc)


class PdfToDocxTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        options = build_pdf_to_docx_options(tool_parameters)
        yield from emit_conversion_result(
            self,
            action="pdf_to_docx",
            tool_parameters=tool_parameters,
            input_format="pdf",
            output_format="docx",
            options=options,
        )


class OfficeToPdfTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        options = build_generic_convert_options(tool_parameters)
        yield from emit_conversion_result(
            self,
            action="office_to_pdf",
            tool_parameters=tool_parameters,
            input_format=clean_string(tool_parameters.get("input_format")),
            output_format="pdf",
            options=options,
        )


class ConvertOfficeFileTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        output_format = normalize_format(tool_parameters.get("output_format"))
        if output_format not in OFFICE_FORMATS:
            yield from emit_error(
                self,
                "convert_office_file",
                CloudConvertError(
                    "output_format must be one of the supported office-related formats."
                ),
            )
            return
        options = build_generic_convert_options(tool_parameters)
        yield from emit_conversion_result(
            self,
            action="convert_office_file",
            tool_parameters=tool_parameters,
            input_format=clean_string(tool_parameters.get("input_format")),
            output_format=output_format,
            options=options,
        )


class ListSupportedConversionsTool(Tool):
    def _invoke(
        self, tool_parameters: dict[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        action = "list_supported_conversions"
        try:
            input_format = normalize_format(tool_parameters.get("input_format"))
            output_format = normalize_format(tool_parameters.get("output_format"))
            include_options = bool(
                parse_bool(tool_parameters.get("include_options"), default=False)
            )
            office_only = bool(parse_bool(tool_parameters.get("office_only"), default=True))
            limit = int(tool_parameters.get("limit") or 50)
            limit = max(1, min(limit, 200))

            client = CloudConvertClient(self.runtime.credentials)
            operations = client.list_operations(
                input_format=input_format,
                output_format=output_format,
                include_options=include_options,
            )
            filtered = filter_office_operations(
                operations,
                office_only=office_only,
                limit=limit,
            )
            result = {
                "status": "success",
                "action": action,
                "input_format": input_format,
                "output_format": output_format,
                "include_options": include_options,
                "office_only": office_only,
                "returned_count": len(filtered),
                "operations": filtered,
            }
            yield self.create_text_message(
                f"Found {len(filtered)} CloudConvert conversion operation(s)."
            )
            yield self.create_variable_message("returned_count", len(filtered))
            yield self.create_variable_message("operations", filtered)
            yield self.create_json_message(result)
        except CloudConvertError as exc:
            yield from emit_error(self, action, exc)
        except Exception as exc:  # pragma: no cover - runtime safeguard
            yield from emit_error(self, action, exc)
