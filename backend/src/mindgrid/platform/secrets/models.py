"""Re-export: the secrets table lives with the settings tables (same scopes, one migration)."""

from mindgrid.platform.settings.models import SecretValue

__all__ = ["SecretValue"]
