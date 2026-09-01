# CloudConvert

A Dify plugin that converts PDF and office files using the CloudConvert API.

**Namespace:** `erbanku/cloudconvert` · **License:** MIT

## Tools

- **pdf_to_docx** — Convert PDF to DOCX (supports page range, password, hyphen handling, OCR, and layout options)
- **office_to_pdf** — Convert Word, Excel, PowerPoint, RTF, and OpenDocument files to PDF
- **convert_office_file** — General-purpose converter for PDF, Word, Excel, PowerPoint, CSV, text, HTML, image, and OpenDocument formats
- **list_supported_conversions** — Lists available conversion formats, with optional filters

## Setup

1. Get a CloudConvert API key with `task.read` and `task.write` scopes.
2. Add the key to the plugin's provider settings.
3. *(Optional)* Set a custom `api_base_url` if using a regional or sandbox endpoint.

## How It Works

Upload a file in Dify → the plugin sends it to CloudConvert → converts it → returns the result as a downloadable file with proper filename and type.

## Privacy

Files are sent to CloudConvert for processing. See [PRIVACY.md](https://github.com/erbanku/cloudconvert/blob/main/PRIVACY.md) for details.
