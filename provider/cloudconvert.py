from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from cloudconvert_client import CloudConvertClient, CloudConvertError, resolve_api_base_url


class CloudconvertProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict) -> None:
        try:
            resolve_api_base_url(credentials)
            CloudConvertClient(credentials).validate_credentials()
        except CloudConvertError as exc:
            raise ToolProviderCredentialValidationError(str(exc)) from exc
