from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent


def load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec and spec.loader, f'cannot load spec for {module_name}'
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_python_sources_are_importable() -> None:
    sys.path.insert(0, str(PLUGIN_DIR))
    try:
        expectations = [{'path': 'provider/cloudconvert.py', 'module_name': 'cloudconvert_provider', 'class_name': 'CloudconvertProvider'}, {'path': 'tools/convert_office_file.py', 'module_name': 'tools_convert_office_file', 'class_name': 'ConvertOfficeFileTool'}, {'path': 'tools/list_supported_conversions.py', 'module_name': 'tools_list_supported_conversions', 'class_name': 'ListSupportedConversionsTool'}, {'path': 'tools/office_to_pdf.py', 'module_name': 'tools_office_to_pdf', 'class_name': 'OfficeToPdfTool'}, {'path': 'tools/pdf_to_docx.py', 'module_name': 'tools_pdf_to_docx', 'class_name': 'PdfToDocxTool'}]
        for expectation in expectations:
            module = load_module(expectation['module_name'], PLUGIN_DIR / expectation['path'])
            assert hasattr(module, expectation['class_name'])
    finally:
        sys.path.remove(str(PLUGIN_DIR))
