"""Run the standard local quality gate for the ETL platform."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def _bootstrap_import_path() -> None:
    package_root = Path(__file__).resolve().parents[2]
    parent = package_root.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))


@dataclass(slots=True)
class QualityStep:
    """One quality gate command."""

    name: str
    args: list[str]
    requires_local_data: bool = False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ETL health, smoke, and regression checks.")
    parser.add_argument(
        "--include-golden",
        action="store_true",
        help="Also run golden-master verification against configured local source data.",
    )
    parser.add_argument(
        "--scenarios",
        help="Optional golden-master scenarios file passed through to golden_master.",
    )
    return parser


def _quality_steps(*, include_golden: bool, scenarios: str | None) -> list[QualityStep]:
    steps = [
        QualityStep(
            name="health_check_namespace",
            args=["-m", "Restaurant.apps.etl_cli.health_check", "--namespace-only"],
        ),
        QualityStep(
            name="ci_smoke_bank",
            args=["-m", "Restaurant.apps.etl_cli.ci_smoke", "--module", "bank"],
        ),
        QualityStep(
            name="ci_smoke_cashbook",
            args=["-m", "Restaurant.apps.etl_cli.ci_smoke", "--module", "cashbook"],
        ),
    ]
    if include_golden:
        golden_args = ["-m", "Restaurant.apps.etl_cli.golden_master", "--mode", "verify"]
        if scenarios:
            golden_args.extend(["--scenarios", scenarios])
        steps.append(
            QualityStep(
                name="golden_master_verify",
                args=golden_args,
                requires_local_data=True,
            )
        )
    return steps


def _run_step(step: QualityStep, cwd: Path) -> int:
    command = [sys.executable, *step.args]
    print(f"\n== {step.name} ==")
    print(" ".join(command))
    sys.stdout.flush()
    completed = subprocess.run(command, cwd=str(cwd), check=False)
    if completed.returncode == 0:
        print(f"[OK] {step.name}")
    else:
        print(f"[FAIL] {step.name} exited with {completed.returncode}")
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    _bootstrap_import_path()
    args = _build_parser().parse_args(argv)
    workspace_root = Path(__file__).resolve().parents[3]
    failures: list[str] = []

    for step in _quality_steps(include_golden=args.include_golden, scenarios=args.scenarios):
        return_code = _run_step(step, workspace_root)
        if return_code != 0:
            failures.append(step.name)

    print("\n== Quality Gate Result ==")
    if failures:
        print(f"FAIL ({len(failures)} failed): {', '.join(failures)}")
        return 1
    print("OK (all selected checks passed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
