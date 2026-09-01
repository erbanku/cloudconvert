# CloudConvert Dify Plugin Privacy Policy

Last updated: 2026-09-01 / Version: 0.1.2

This policy describes how the Dify tool plugin **erbanku/cloudconvert** ("the Plugin") handles information.

## Scope

This policy applies to data processed while the Plugin runs inside Dify: uploaded files, CloudConvert API credentials, conversion output, and runtime logs. Dify platform retention and access controls are governed by your Dify deployment provider.

## Data Collection and Use

- **Uploaded files**: Users provide PDF, Word, Excel, PowerPoint, and other office-related files through Dify tools or workflows. The Plugin reads those bytes to upload them to CloudConvert for conversion.
- **Conversion output**: The Plugin downloads the converted file from CloudConvert and returns it as a Dify file blob with filename and MIME metadata.
- **Credentials**: The Plugin requires a CloudConvert API key (and an optional API base URL). Credentials are stored by Dify as provider secrets and are sent only to the configured CloudConvert API host.

The Plugin does not collect analytics, telemetry, or personal data for profiling.

## Third-Party Transmission

Uploaded file contents **are sent** to CloudConvert (`api.cloudconvert.com` by default, or the optional sandbox/region endpoint you configure) so CloudConvert can convert the file. CloudConvert's own privacy policy and retention terms apply to files processed on their service.

See: https://cloudconvert.com/privacy

## Data Storage and Retention

- The Plugin does not persist uploaded files or converted outputs outside Dify's normal tool execution lifecycle.
- Temporary buffers used to upload and download files are released when the tool invocation completes.
- CloudConvert may retain files according to their account and job settings.

## Logging

The Plugin avoids logging file contents or API keys. Do not include confidential material in tool inputs unless your Dify environment and CloudConvert account meet your organization's security requirements.

## User Responsibilities

- Use this Plugin only for files you are permitted to send to CloudConvert.
- Restrict the CloudConvert API key to `task.read` and `task.write`.
- Remove the Plugin from Dify when it is no longer needed.

## Contact

For privacy questions, open an issue at https://github.com/erbanku/cloudconvert/issues.
