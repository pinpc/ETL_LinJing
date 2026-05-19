"""Tenant service placeholders."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ..shared.errors import ConfigurationError, ValidationError
from .interfaces import ITenantResolver
from .models import TenantContext


class TenantResolver(ITenantResolver):
    """Resolve tenant context from tenant-specific YAML config."""

    def __init__(self, tenants_root: Path | None = None) -> None:
        self._tenants_root = tenants_root or Path(__file__).resolve().parents[2] / "tenants"

    def resolve(self, tenant_id: str) -> TenantContext:
        config_path = self._resolve_config_path(tenant_id)
        raw_config = _read_yaml(config_path)
        if not isinstance(raw_config, dict):
            raise ValidationError(f"Tenant config must be a mapping: {config_path}")

        return TenantContext(
            tenant_id=tenant_id,
            display_name=str(raw_config.get("display_name") or tenant_id),
            config_dir=config_path.parent,
            bank_account=str(raw_config.get("bank_account") or ""),
            default_kost=str(raw_config.get("default_kost") or ""),
            options=_normalize_options(raw_config.get("options")),
        )

    def _resolve_config_path(self, tenant_id: str) -> Path:
        tenant_dir = self._tenants_root / tenant_id
        yaml_path = tenant_dir / "tenant_config.yaml"
        yml_path = tenant_dir / "tenant_config.yml"
        if yaml_path.exists():
            return yaml_path
        if yml_path.exists():
            return yml_path
        raise ConfigurationError(f"Missing tenant config for '{tenant_id}' in {tenant_dir}")


def _read_yaml(config_path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ConfigurationError(
            "PyYAML is required for tenant config loading. Install with 'pip install pyyaml'."
        ) from exc

    with config_path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValidationError(f"Unsupported YAML structure in {config_path}.")
    return loaded


def _normalize_options(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("Tenant 'options' must be a mapping.")
    return value.copy()


def resolve_option_str(options: dict[str, Any], key: str) -> str | None:
    """Resolve optional string option from tenant options mapping."""
    value = options.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if normalized else None


def resolve_option_path(context: TenantContext, key: str) -> Path | None:
    """Resolve optional path option, supporting absolute and tenant-relative paths."""
    path, _origin = resolve_option_path_info(context, key)
    return path


def resolve_option_path_info(context: TenantContext, key: str) -> tuple[Path | None, str]:
    """Resolve optional path and return its resolution origin for diagnostics."""
    raw = resolve_option_str(context.options, key)
    if raw is None:
        return None, "unset"

    expanded = _expand_path_template(raw, context)
    if not expanded:
        return None, "empty_after_expansion"

    candidate = Path(expanded)
    if candidate.is_absolute():
        return candidate, "absolute_or_template"
    return (context.config_dir / candidate).resolve(), "tenant_relative_or_template"


_ENV_PATTERN = re.compile(r"\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_path_template(raw: str, context: TenantContext) -> str:
    """Expand supported path placeholders for tenant configs."""
    workspace_root = context.config_dir.parents[1]
    expanded = raw
    expanded = expanded.replace("${WORKSPACE_ROOT}", str(workspace_root))
    expanded = expanded.replace("${TENANT_DIR}", str(context.config_dir))

    def repl(match: re.Match[str]) -> str:
        env_name = match.group(1)
        return os.environ.get(env_name, "")

    expanded = _ENV_PATTERN.sub(repl, expanded)
    return expanded.strip()

