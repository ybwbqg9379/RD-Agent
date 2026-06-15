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

Live local-qlib source (skip the image rebuild)
-----------------------------------------------
The image bakes a ``git clone`` of the qlib fork, so editing the host's sibling
``~/Development/Github/qlib`` repo normally only reaches a run after a push + image
rebuild. Pass ``qlib_src`` (CLI ``--qlib-src``) to bind-mount the host repo over
``/workspace/qlib`` instead, so pure-Python edits (models, handlers, examples,
collectors, configs) are live immediately::

    python -m rdagent.custom.us_qlib_backtest --qlib-src \
        --config examples/fork/workflow_config_lightgbm_alpha158_us.yaml

Caveat handled automatically: qlib's cython ``qlib/data/_libs`` ``.so`` are compiled
for a specific Python (host 3.12 vs image 3.10), so the host tree's ``.so`` won't
import in the container. We overlay the *image's* compiled ``_libs`` back on top (a
one-time extraction cached under ``~/.cache/rdagent``). Editing the ``.pyx`` cython
core itself therefore still needs an image rebuild; everything else is live.
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
# Sibling qlib fork on the host — the default target for ``--qlib-src`` (live source).
SIBLING_QLIB = Path("~/Development/Github/qlib").expanduser()
# Where we stash the image's compiled cython _libs so we can overlay them when the
# host qlib source shadows /workspace/qlib (see ``_ensure_libs_cache``).
LIBS_CACHE = Path("~/.cache/rdagent/local_qlib_libs").expanduser()

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


def _ensure_libs_cache() -> Path | None:
    """Extract the image's compiled ``qlib/data/_libs`` to a host cache, once.

    When ``qlib_src`` shadows ``/workspace/qlib`` with the host repo, that tree's
    cython ``.so`` are built for the host's Python (3.12) and won't import in the
    container (3.10). We overlay this cache — the *image's* own ``_libs``, built for
    the container's Python — back over that subdir so the ABI matches. Returns the
    cache path, or ``None`` if the one-time extraction failed (caller then skips the
    overlay; a stale/empty cache is never used)."""
    if any(LIBS_CACHE.glob("*.so")):
        return LIBS_CACHE
    LIBS_CACHE.mkdir(parents=True, exist_ok=True)
    extract = [
        "docker", "run", "--rm", "-v", f"{LIBS_CACHE}:/out", "--entrypoint", "bash", IMAGE,
        "-c", f"cp -a {QLIB_REPO_IN_IMAGE}/qlib/data/_libs/. /out/",
    ]
    proc = subprocess.run(extract, capture_output=True, text=True)
    return LIBS_CACHE if proc.returncode == 0 and any(LIBS_CACHE.glob("*.so")) else None


def _docker_cmd(
    config: str,
    workspace: Path | None,
    env: dict[str, str],
    gpu: bool = False,
    qlib_src: Path | None = None,
    libs_overlay: Path | None = None,
) -> list[str]:
    """Build the ``docker run`` argv. List form (no shell) keeps ``$close`` etc. in
    feature expressions intact — passing them through a shell would eat the ``$``.

    gpu=True adds ``--gpus all`` so PyTorch models (e.g. qlib's GRU) train on the
    RTX 5090. Requires the image to carry a Blackwell-capable torch (cu128; the qlib
    Dockerfile installs it — see FORK.md §9.9). LightGBM/CPU runs don't need this.

    qlib_src, when set, bind-mounts the host qlib repo over ``/workspace/qlib`` (live
    source); libs_overlay then re-mounts the image's ABI-correct compiled ``_libs``."""
    # --shm-size: PyTorch DataLoader workers pass tensors via /dev/shm; Docker's default
    # 64MB overflows ("unable to allocate shared memory"). RD-Agent's QlibDockerConf uses 16g.
    cmd = ["docker", "run", "--rm", "--shm-size=16g"]
    if gpu:
        cmd += ["--gpus", "all"]
    cmd += ["-v", f"{QLIB_HOME}:/root/.qlib"]
    if qlib_src is not None:
        cmd += ["-v", f"{qlib_src.resolve()}:{QLIB_REPO_IN_IMAGE}"]
        if libs_overlay is not None:
            cmd += ["-v", f"{libs_overlay}:{QLIB_REPO_IN_IMAGE}/qlib/data/_libs:ro"]
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
    qlib_src: str | Path | None = None,
) -> BacktestResult:
    """Run ``qrun <config>`` in the local_qlib container on US data and parse metrics.

    config:    qrun workflow YAML — a path inside the image (mode 1) or a filename
               relative to ``workspace`` (mode 2).
    workspace: optional host dir to mount at ``/ws`` (RD-Agent model workspace).
    env:       extra container env (Jinja context for rendered RD-Agent configs).
    gpu:       pass ``--gpus all`` so PyTorch models train on the RTX 5090 (needs the
               cu128 torch baked into the image). Leave False for LightGBM/CPU configs.
    qlib_src:  optional host qlib repo to bind-mount over ``/workspace/qlib`` so local
               edits are live without an image rebuild (the image's compiled cython
               ``_libs`` are overlaid back automatically). Defaults to the in-image
               clone when None.
    """
    run_env = {"MLFLOW_ALLOW_FILE_STORE": "true", "PYTHONPATH": "./"}
    if env:
        run_env.update({k: str(v) for k, v in env.items()})
    ws = Path(workspace) if workspace is not None else None
    qsrc = Path(qlib_src).expanduser() if qlib_src is not None else None
    libs_overlay = _ensure_libs_cache() if qsrc is not None else None
    proc = subprocess.run(
        _docker_cmd(config, ws, run_env, gpu=gpu, qlib_src=qsrc, libs_overlay=libs_overlay),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = proc.stdout + proc.stderr
    return BacktestResult(exit_code=proc.returncode, metrics=parse_metrics(out), raw_stdout=out)


def _format(result: BacktestResult) -> str:
    if not result.metrics:
        return f"No metrics parsed (exit={result.exit_code}). Tail:\n" + "\n".join(
            result.raw_stdout.splitlines()[-15:],
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
                f"{b.get('max_drawdown', float('nan')):>14.4f}",
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="[FORK] Drive qlib qrun on US data, bypass RD-Agent's loop.")
    p.add_argument("--config", required=True, help="qrun workflow YAML (in-image path or workspace-relative).")
    p.add_argument("--workspace", default=None, help="Host model-workspace dir to mount (RD-Agent generated).")
    p.add_argument("--env-json", default=None, help="JSON dict of extra container env (Jinja context).")
    p.add_argument("--gpu", action="store_true", help="Pass --gpus all (PyTorch models on the RTX 5090; needs cu128 image).")
    p.add_argument(
        "--qlib-src",
        nargs="?",
        const=str(SIBLING_QLIB),
        default=None,
        help="Bind-mount a host qlib repo over /workspace/qlib for live source (no rebuild). "
        f"Bare flag uses the sibling fork ({SIBLING_QLIB}); pass a path to override.",
    )
    p.add_argument("--json", action="store_true", help="Print parsed metrics as JSON.")
    args = p.parse_args(argv)

    env = json.loads(args.env_json) if args.env_json else None
    result = run_backtest(
        config=args.config, workspace=args.workspace, env=env, gpu=args.gpu, qlib_src=args.qlib_src,
    )
    if args.json:
        print(json.dumps({"exit_code": result.exit_code, "metrics": result.metrics}, indent=2))
    else:
        print(_format(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
