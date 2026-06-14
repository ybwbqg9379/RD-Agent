"""[FORK] Drive qlib's ``qrun`` directly on US data, bypassing RD-Agent's loop.

Why this exists
---------------
RD-Agent's qlib quant scenario (``fin_factor`` / ``fin_model`` / ``fin_quant``) is
hardcoded + tested only for China A-shares, and its docker-SDK loop wrapper fails on
US data with ``instrument ... does not contain data for day`` — even though the very
same ``qrun`` config runs fine when invoked directly (proven; see FORK.md §9.7).

This module is the reliable alternative: it runs ``qrun`` inside our ``local_qlib``
image (built from the sibling ``ybwbqg9379/qlib`` fork) with ``~/.qlib`` mounted, and
parses the backtest metrics out of qlib's output. No LLM, no RD-Agent loop.

Two modes
---------
1. **Workflow config** already inside the image (e.g. the qlib fork's
   ``examples/fork/workflow_config_lightgbm_alpha158_us.yaml``)::

       python -m rdagent.custom.us_qlib_backtest \
           --config examples/fork/workflow_config_lightgbm_alpha158_us.yaml

2. **A model workspace on the host** (e.g. one RD-Agent generated under
   ``git_ignore_folder/RD-Agent_workspace/<id>/`` with ``model.py`` + a rendered
   ``conf_*.yaml``). The workspace is mounted and the Jinja context is passed as env
   (qlib renders the conf from ``os.environ``)::

       python -m rdagent.custom.us_qlib_backtest \
           --workspace git_ignore_folder/RD-Agent_workspace/<id> \
           --config conf_baseline_factors_model.yaml \
           --env-json '{"dataset_cls":"TSDatasetH","step_len":"20", ...}'

Programmatic use::

    from rdagent.custom.us_qlib_backtest import run_backtest
    result = run_backtest(config="examples/fork/workflow_config_lightgbm_alpha158_us.yaml")
    print(result.metrics)        # {'IC': ..., 'excess_return_with_cost': {...}, ...}
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# The image our qlib Dockerfile builds (FORK.md §5.4 / §6). It bundles the sibling
# qlib fork and has MLFLOW_ALLOW_FILE_STORE=true baked in.
IMAGE = "local_qlib:latest"
# Host qlib data dir (holds us_data). Mounted read-only into the container.
QLIB_HOME = Path("~/.qlib").expanduser()
# Default working dir inside the image = the qlib repo, so in-image example configs
# like ``examples/fork/...`` resolve without mounting anything extra.
QLIB_REPO_IN_IMAGE = "/workspace/qlib"

# qlib labels its three risk_analysis blocks like this; we map them to short keys.
_RISK_BLOCKS = {
    "benchmark return": "benchmark",
    "excess return without cost": "excess_return_without_cost",
    "excess return with cost": "excess_return_with_cost",
}
_RISK_FIELDS = ("mean", "std", "annualized_return", "information_ratio", "max_drawdown")


@dataclass
class BacktestResult:
    exit_code: int
    metrics: dict = field(default_factory=dict)
    raw_stdout: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and bool(self.metrics)


def _docker_cmd(config: str, workspace: Path | None, env: dict[str, str], gpu: bool = False) -> list[str]:
    """Build the ``docker run`` argv. List form (no shell) keeps ``$close`` etc. in
    feature expressions intact — passing them through a shell would eat the ``$``.

    gpu=True adds ``--gpus all`` so PyTorch models (e.g. qlib's GRU) train on the
    RTX 5090. Requires the image to carry a Blackwell-capable torch (cu128; the qlib
    Dockerfile installs it — see FORK.md §9.9). LightGBM/CPU runs don't need this."""
    cmd = ["docker", "run", "--rm"]
    if gpu:
        cmd += ["--gpus", "all"]
    cmd += ["-v", f"{QLIB_HOME}:/root/.qlib"]
    if workspace is not None:
        cmd += ["-v", f"{workspace.resolve()}:/ws", "-w", "/ws"]
    else:
        cmd += ["-w", QLIB_REPO_IN_IMAGE]
    for key, value in env.items():
        cmd += ["-e", f"{key}={value}"]
    cmd += [IMAGE, "qrun", config]
    return cmd


def parse_metrics(stdout: str) -> dict:
    """Extract the signal IC block and the three risk_analysis blocks from qrun output."""
    metrics: dict = {}

    # Signal IC dict, e.g.  {'IC': 0.0066, 'ICIR': ..., 'Rank IC': ..., 'Rank ICIR': ...}
    ic = {}
    for key in ("IC", "ICIR", "Rank IC", "Rank ICIR"):
        m = re.search(rf"'{re.escape(key)}':\s*(-?[\d.eE+]+)", stdout)
        if m:
            ic[key] = float(m.group(1))
    if ic:
        metrics["signal_ic"] = ic

    # Risk-analysis blocks. Each starts with a labelled line, followed by the rows.
    for label, short in _RISK_BLOCKS.items():
        m = re.search(rf"analysis results of (?:the )?{re.escape(label)}", stdout)
        if not m:
            continue
        tail = stdout[m.end() : m.end() + 1200]
        block = {}
        for fld in _RISK_FIELDS:
            fm = re.search(rf"{fld}\s+(-?[\d.eE+]+)", tail)
            if fm:
                block[fld] = float(fm.group(1))
        if block:
            metrics[short] = block

    return metrics


def run_backtest(
    config: str,
    workspace: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 7200,
    gpu: bool = False,
) -> BacktestResult:
    """Run ``qrun <config>`` in the local_qlib container on US data and parse metrics.

    config:    qrun workflow YAML — a path inside the image (mode 1) or a filename
               relative to ``workspace`` (mode 2).
    workspace: optional host dir to mount at ``/ws`` (RD-Agent model workspace).
    env:       extra container env (Jinja context for rendered RD-Agent configs).
    gpu:       pass ``--gpus all`` so PyTorch models train on the RTX 5090 (needs the
               cu128 torch baked into the image). Leave False for LightGBM/CPU configs.
    """
    run_env = {"MLFLOW_ALLOW_FILE_STORE": "true", "PYTHONPATH": "./"}
    if env:
        run_env.update({k: str(v) for k, v in env.items()})
    ws = Path(workspace) if workspace is not None else None
    proc = subprocess.run(
        _docker_cmd(config, ws, run_env, gpu=gpu),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = proc.stdout + proc.stderr
    return BacktestResult(exit_code=proc.returncode, metrics=parse_metrics(out), raw_stdout=out)


def _format(result: BacktestResult) -> str:
    if not result.metrics:
        return f"No metrics parsed (exit={result.exit_code}). Tail:\n" + "\n".join(
            result.raw_stdout.splitlines()[-15:]
        )
    lines = []
    ic = result.metrics.get("signal_ic", {})
    if ic:
        lines.append("Signal:  " + "  ".join(f"{k}={v:.4f}" for k, v in ic.items()))
    header = f"{'block':<28}{'ann_return':>12}{'info_ratio':>12}{'max_drawdown':>14}"
    lines.append(header)
    for short in ("benchmark", "excess_return_without_cost", "excess_return_with_cost"):
        b = result.metrics.get(short)
        if b:
            lines.append(
                f"{short:<28}{b.get('annualized_return', float('nan')):>12.4f}"
                f"{b.get('information_ratio', float('nan')):>12.4f}"
                f"{b.get('max_drawdown', float('nan')):>14.4f}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="[FORK] Drive qlib qrun on US data, bypass RD-Agent's loop.")
    p.add_argument("--config", required=True, help="qrun workflow YAML (in-image path or workspace-relative).")
    p.add_argument("--workspace", default=None, help="Host model-workspace dir to mount (RD-Agent generated).")
    p.add_argument("--env-json", default=None, help="JSON dict of extra container env (Jinja context).")
    p.add_argument("--gpu", action="store_true", help="Pass --gpus all (PyTorch models on the RTX 5090; needs cu128 image).")
    p.add_argument("--json", action="store_true", help="Print parsed metrics as JSON.")
    args = p.parse_args(argv)

    env = json.loads(args.env_json) if args.env_json else None
    result = run_backtest(config=args.config, workspace=args.workspace, env=env, gpu=args.gpu)
    if args.json:
        print(json.dumps({"exit_code": result.exit_code, "metrics": result.metrics}, indent=2))
    else:
        print(_format(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
