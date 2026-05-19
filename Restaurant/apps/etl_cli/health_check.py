"""Health check for tenant ETL configuration and debug paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    package_root = Path(__file__).resolve().parents[2]
    parent = package_root.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate tenant ETL config and debug path health.")
    parser.add_argument(
        "--tenant",
        choices=["asia", "jupiter", "all"],
        default="all",
        help="Tenant scope to check.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _bootstrap_import_path()
    args = _build_parser().parse_args(argv)

    from Restaurant.etl_platform.tenant.service import TenantResolver, resolve_option_path_info

    tenants = ["asia", "jupiter"] if args.tenant == "all" else [args.tenant]
    resolver = TenantResolver()
    failures: list[str] = []

    print("== Tenant Config Checks ==")
    for tenant_id in tenants:
        context = resolver.resolve(tenant_id)
        print(f"\n[{tenant_id}] config_dir: {context.config_dir}")

        _check_path(
            label=f"{tenant_id}.bank_statement_pdf",
            path=resolve_option_path_info(context, "bank_statement_pdf")[0],
            required=True,
            expect_file=True,
            failures=failures,
            origin=resolve_option_path_info(context, "bank_statement_pdf")[1],
        )
        _check_path(
            label=f"{tenant_id}.bank_sqlite_output_path",
            path=resolve_option_path_info(context, "bank_sqlite_output_path")[0],
            required=False,
            expect_file=False,
            failures=failures,
            origin=resolve_option_path_info(context, "bank_sqlite_output_path")[1],
        )
        _check_path(
            label=f"{tenant_id}.cashbook_sqlite_output_path",
            path=resolve_option_path_info(context, "cashbook_sqlite_output_path")[0],
            required=False,
            expect_file=False,
            failures=failures,
            origin=resolve_option_path_info(context, "cashbook_sqlite_output_path")[1],
        )

    print("\n== Launch.json Checks ==")
    launch_file = Path(__file__).resolve().parents[2] / ".vscode" / "launch.json"
    if not launch_file.exists():
        failures.append(f"missing launch file: {launch_file}")
        print(f"[FAIL] launch_file missing: {launch_file}")
    else:
        _check_launch_profiles(launch_file, tenants, failures)

    print("\n== Health Check Result ==")
    if failures:
        print(f"FAIL ({len(failures)} issue(s))")
        for item in failures:
            print(f" - {item}")
        return 1

    print("OK (no blocking issues found)")
    return 0


def _check_launch_profiles(launch_file: Path, tenants: list[str], failures: list[str]) -> None:
    data = json.loads(launch_file.read_text(encoding="utf-8"))
    configs = {cfg.get("name"): cfg for cfg in data.get("configurations", [])}

    target_profiles = []
    for tenant in tenants:
        title = tenant.capitalize()
        target_profiles.extend(
            [
                f"Restaurant Bank - {title}",
                f"Restaurant Cashbook - {title}",
            ]
        )

    for profile_name in target_profiles:
        cfg = configs.get(profile_name)
        if cfg is None:
            failures.append(f"missing debug profile: {profile_name}")
            print(f"[FAIL] profile missing: {profile_name}")
            continue

        print(f"\n[{profile_name}]")
        args = cfg.get("args", [])
        arg_map = _parse_args(args)

        for key in ("--output", "--sqlite-output"):
            if key in arg_map:
                _check_path(
                    label=f"{profile_name}:{key}",
                    path=Path(arg_map[key]),
                    required=False,
                    expect_file=False,
                    failures=failures,
                )

        for key in ("--input", "--source-dir", "--statement-pdf", "--pdf-base-dir", "--agenda-file"):
            if key in arg_map:
                p = Path(arg_map[key])
                _check_path(
                    label=f"{profile_name}:{key}",
                    path=p,
                    required=True,
                    expect_file=(key in {"--input", "--statement-pdf", "--agenda-file"} and p.suffix != ""),
                    failures=failures,
                )


def _parse_args(args: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    idx = 0
    while idx < len(args) - 1:
        key = args[idx]
        if key.startswith("--"):
            result[key] = args[idx + 1]
            idx += 2
        else:
            idx += 1
    return result


def _check_path(
    label: str,
    path: Path | None,
    required: bool,
    expect_file: bool,
    failures: list[str],
    origin: str | None = None,
) -> None:
    if path is None:
        if required:
            msg = f"{label}: missing path"
            failures.append(msg)
            print(f"[FAIL] {msg}")
        else:
            print(f"[WARN] {label}: not configured")
        return

    if expect_file:
        if path.exists() and path.is_file():
            if origin:
                print(f"[OK] {label}: {_safe_text(path)} (origin={origin})")
            else:
                print(f"[OK] {label}: {_safe_text(path)}")
        else:
            msg = f"{label}: file not found ({_safe_text(path)})"
            failures.append(msg)
            print(f"[FAIL] {msg}")
        return

    parent = path.parent
    if parent.exists():
        if origin:
            print(f"[OK] {label}: parent exists ({_safe_text(parent)}) (origin={origin})")
        else:
            print(f"[OK] {label}: parent exists ({_safe_text(parent)})")
    else:
        msg = f"{label}: parent directory missing ({_safe_text(parent)})"
        failures.append(msg)
        print(f"[FAIL] {msg}")


def _safe_text(value: Path) -> str:
    """Return ASCII-safe path text for legacy Windows console encodings."""
    return ascii(str(value))


if __name__ == "__main__":
    raise SystemExit(main())
