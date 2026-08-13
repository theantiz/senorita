import abc


class IntegrationAdapter(abc.ABC):
    """
    Abstract base class for all external integration adapters.
    Each provider (Gmail, WhatsApp, Slack, etc.) must implement this interface.
    """

    @abc.abstractmethod
    def get_oauth_url(self, state: str) -> str:
        """
        Returns the OAuth consent screen URL to redirect the user to.
        """
        pass

    @abc.abstractmethod
    async def exchange_code_for_tokens(self, code: str) -> dict:
        """
        Exchanges authorization code for access and refresh tokens.
        Returns a dict containing:
          - access_token: str
          - refresh_token: str | None
          - expires_at: datetime | None (timezone-aware)
          - scopes: list[str]
        """
        pass

    @abc.abstractmethod
    async def refresh_access_token(self, integration) -> dict:
        """
        Refreshes the access token using the stored refresh token.
        Returns a dict containing:
          - access_token: str
          - refresh_token: str | None (updated if returned by provider)
          - expires_at: datetime | None (timezone-aware)
        """
        pass

    @abc.abstractmethod
    def is_token_valid(self, integration) -> bool:
        """
        Checks if the integration's access token is still valid.
        Typically compares integration.token_expires_at with current time.
        """
        pass

    async def revoke_tokens(self, integration) -> None:
        """
        Optional: Revokes the stored tokens at the provider's endpoint.
        """
        pass


_registry: dict[str, IntegrationAdapter] = {}

def register_adapter(provider: str, adapter: IntegrationAdapter) -> None:
    """Register an adapter for a given provider name."""
    _registry[provider] = adapter

def get_adapter(provider: str) -> IntegrationAdapter:
    """Retrieve the registered adapter for the provider name."""
    if provider not in _registry:
        raise ValueError(f"No integration adapter registered for provider: {provider}")
    return _registry[provider]
