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
        local_config = _read_tenant_local_config(config_path.parent)
        manifest = _read_tenant_manifest(config_path.parent)
        options = _merge_tenant_options(
            tenant_id=tenant_id,
            tenant_config=raw_config,
            tenant_manifest=manifest,
            tenant_local_config=local_config,
        )

        return TenantContext(
            tenant_id=tenant_id,
            display_name=str(raw_config.get("display_name") or manifest.get("display_name") or tenant_id),
            config_dir=config_path.parent,
            bank_account=str(raw_config.get("bank_account") or manifest.get("bank_account") or ""),
            default_kost=str(raw_config.get("default_kost") or manifest.get("default_kost") or ""),
            options=options,
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


def list_available_tenant_ids(tenants_root: Path | None = None) -> list[str]:
    """List tenant ids discovered from tenants/*/tenant_config.yaml."""
    from .registry import list_tenant_ids

    return list_tenant_ids(tenants_root=tenants_root)


def list_available_tenants(tenants_root: Path | None = None) -> list[dict[str, str]]:
    """List available tenants with display labels for API/UI dropdowns."""
    from .registry import list_tenants

    return [
        {
            "tenant_id": str(item["tenant_id"]),
            "display_name": str(item["display_name"]),
        }
        for item in list_tenants(tenants_root=tenants_root)
    ]


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


def _read_tenant_manifest(tenant_dir: Path) -> dict[str, Any]:
    manifest_yaml = tenant_dir / "tenant_manifest.yaml"
    manifest_yml = tenant_dir / "tenant_manifest.yml"
    if manifest_yaml.exists():
        loaded = _read_yaml(manifest_yaml)
    elif manifest_yml.exists():
        loaded = _read_yaml(manifest_yml)
    else:
        return {}

    if not isinstance(loaded, dict):
        raise ValidationError("Tenant manifest must be a mapping.")
    return loaded


def _read_tenant_local_config(tenant_dir: Path) -> dict[str, Any]:
    local_yaml = tenant_dir / "tenant_local.yaml"
    local_yml = tenant_dir / "tenant_local.yml"
    if local_yaml.exists():
        loaded = _read_yaml(local_yaml)
    elif local_yml.exists():
        loaded = _read_yaml(local_yml)
    else:
        return {}

    if not isinstance(loaded, dict):
        raise ValidationError("Tenant local config must be a mapping.")
    return loaded


def _merge_tenant_options(
    *,
    tenant_id: str,
    tenant_config: dict[str, Any],
    tenant_manifest: dict[str, Any],
    tenant_local_config: dict[str, Any],
) -> dict[str, Any]:
    merged = _normalize_options(tenant_manifest.get("options"))
    merged.update(_normalize_options(tenant_config.get("options")))
    merged.update(_normalize_options(tenant_local_config.get("options")))

    runner_aliases = tenant_manifest.get("runner_aliases")
    if runner_aliases is None:
        return merged
    if not isinstance(runner_aliases, dict):
        raise ValidationError("Tenant manifest field 'runner_aliases' must be a mapping.")

    for module_name, target_tenant in runner_aliases.items():
        module = str(module_name).strip().lower()
        if module not in {"bank", "cashbook"}:
            raise ValidationError(
                f"Tenant manifest has unsupported runner alias module '{module_name}' for tenant '{tenant_id}'."
            )
        target = str(target_tenant).strip().lower()
        if not target:
            raise ValidationError(
                f"Tenant manifest runner alias for module '{module}' must not be empty for tenant '{tenant_id}'."
            )
        merged[f"{module}_runner_tenant_id"] = target

    return merged


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

