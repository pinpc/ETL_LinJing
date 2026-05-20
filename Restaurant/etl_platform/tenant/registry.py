"""Tenant discovery registry utilities."""

from __future__ import annotations

from pathlib import Path

from .service import TenantResolver


def list_tenant_config_paths(tenants_root: Path | None = None) -> dict[str, Path]:
    """Discover tenant config file paths from tenants/* folders."""
    root = tenants_root or Path(__file__).resolve().parents[2] / "tenants"
    if not root.exists():
        return {}

    discovered: dict[str, Path] = {}
    for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir():
            continue
        yaml_path = child / "tenant_config.yaml"
        yml_path = child / "tenant_config.yml"
        if yaml_path.exists():
            discovered[child.name.strip().lower()] = yaml_path
        elif yml_path.exists():
            discovered[child.name.strip().lower()] = yml_path
    return discovered


def list_tenant_ids(tenants_root: Path | None = None) -> list[str]:
    """List tenant ids discovered from tenant config files."""
    return sorted(list_tenant_config_paths(tenants_root=tenants_root).keys())


def list_tenants(tenants_root: Path | None = None) -> list[dict[str, object]]:
    """List tenant metadata for API/UI consumption."""
    resolver = TenantResolver(tenants_root=tenants_root)
    tenants: list[dict[str, object]] = []
    for tenant_id in list_tenant_ids(tenants_root=tenants_root):
        display_name = tenant_id
        supported_modules: list[str] = ["bank", "cashbook"]
        try:
            context = resolver.resolve(tenant_id)
            display_name = context.display_name or tenant_id
            raw_supported = context.options.get("enabled_modules")
            if isinstance(raw_supported, list):
                normalized = sorted(
                    {
                        str(item).strip().lower()
                        for item in raw_supported
                        if str(item).strip().lower() in {"bank", "cashbook"}
                    }
                )
                if normalized:
                    supported_modules = normalized
        except Exception:
            # Keep registry resilient even when one tenant config is malformed.
            pass

        tenants.append(
            {
                "tenant_id": tenant_id,
                "display_name": display_name,
                "supported_modules": supported_modules,
            }
        )
    return tenants
