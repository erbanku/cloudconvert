from __future__ import annotations

from pathlib import Path

import yaml

PLUGIN_DIR = Path(__file__).resolve().parent.parent


def test_manifest_has_required_fields() -> None:
    manifest = yaml.safe_load((PLUGIN_DIR / "manifest.yaml").read_text(encoding="utf-8"))
    for key in [
        "author",
        "name",
        "type",
        "label",
        "description",
        "icon",
        "plugins",
        "resource",
        "version",
        "created_at",
        "privacy",
        "repo",
        "contact",
    ]:
        assert key in manifest, f"manifest missing: {key}"
    runner = manifest.get("meta", {}).get("runner", {})
    assert runner.get("language") == "python"
    assert str(runner.get("version")).startswith("3.")
    assert runner.get("entrypoint") == "main"
    assert "tools" in manifest["plugins"]
    assert manifest["privacy"] == "PRIVACY.md"
    assert manifest["repo"] == "https://github.com/erbanku/cloudconvert"
    assert (PLUGIN_DIR / "PRIVACY.md").is_file()
    assert (PLUGIN_DIR / "LICENSE").is_file()


def test_generated_yaml_files_exist() -> None:
    expected = ['provider/cloudconvert.yaml', 'tools/convert_office_file.yaml', 'tools/list_supported_conversions.yaml', 'tools/office_to_pdf.yaml', 'tools/pdf_to_docx.yaml']
    for rel in expected:
        assert (PLUGIN_DIR / rel).exists(), f"missing YAML file: {rel}"
