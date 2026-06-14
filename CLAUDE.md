# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## This is a fork

This repo is a **self-use fork** of `microsoft/RD-Agent` (`upstream` remote).
**Read `FORK.md` before making changes** — it defines the customization policy:
prefer extension over modification, mark unavoidable upstream edits with `# [FORK]`,
log every divergence in `FORK.md §6`, and sync upstream via `git merge upstream/main`
(never rebase). No PRs are sent upstream.

**Before committing:** a local `commit-msg` gate enforces Conventional Commits +
a mandatory `Fork: <reason>` trailer on every commit we author (`FORK.md §3`). If
`git config --get core.hooksPath` is empty, run `./scripts/setup-hooks.sh` once first.
Commit subject: `type(scope): description`; add a `Fork:` trailer line in the body.

## Commands

```bash
# Setup (upstream uses conda + make; pip/uv also work)
make dev                     # editable install with dev extras
./scripts/setup-hooks.sh     # enable the commit gate (once per clone)
rdagent health_check         # environment self-check (Docker, etc.)

# Tests / lint (what CI runs — offline only, no Docker/API keys)
make lint                    # ruff + mypy
make test-offline            # pytest -m offline
pytest -m offline -q         # same, directly

# Run a scenario (most require Docker)
rdagent fin_factor           # qlib factor R&D loop
rdagent fin_model            # qlib model R&D loop
rdagent fin_quant            # joint factor+model
rdagent data_science --competition <name>   # data science / Kaggle loop
rdagent general_model <paper_url>           # read paper/report → implement model
rdagent llm_finetune         # FT-Agent: LLM fine-tuning loop
rdagent ui                   # Streamlit log viewer
rdagent server_ui            # Web UI backend
```

Config is driven by `.env` + environment variables (Pydantic settings; loaded via
`dotenv` in `rdagent/app/cli.py` before imports). LLM goes through **LiteLLM** by
default — see `FORK.md §5` for the local llama.cpp setup.

## Architecture

RD-Agent automates **data-driven R&D** as an evolving loop: an agent proposes a
**hypothesis**, turns it into an **experiment**, **codes** it, **runs** it (usually in
Docker), and **summarizes feedback** — then iterates, learning from a growing trace.
"R" = propose ideas, "D" = implement them.

### The R&D loop spine
The core abstractions live in **`rdagent/core/`**:
- **`scenario.py` (`Scenario`)** — domain context (background, data, environment).
- **`proposal.py`** — `Hypothesis`, `HypothesisGen` (propose), `Hypothesis2Experiment`
  (plan), and `Trace` (the running history of `(hypothesis, experiment, feedback)` used
  for learning).
- **`developer.py` (`Developer`)** — base for code generation + execution; the two
  concrete roles are **Coder** (write code) and **Runner** (execute it).
- **`evolving_framework.py` / `evolving_agent.py`** — `EvolvingStrategy`, `EvoStep`,
  and `RAGEvoAgent`, the engine that combines RAG + evolving strategy + evaluation.
- **`evaluation.py`**, `experiment.py`, `knowledge_base.py`, `conf.py`.

The orchestrator that wires these into a runnable loop is
**`rdagent/components/workflow/rd_loop.py` (`RDLoop`)**:
`HypothesisGen → Hypothesis2Experiment → Coder → Runner → Summarizer (feedback) → loop`,
with retries + checkpointing. App-level subclasses (e.g. `FactorRDLoop`,
`DataScienceLoop`) specialize it per scenario.

### Scenarios (`rdagent/scenarios/`)
Each scenario is a **self-contained set of the spine's pieces** for one domain:
`qlib` (quant: factor/model/quant), `data_science`, `kaggle`, `general_model`
(paper→model), `finetune` (FT-Agent), `rl` (AutoRL-bench), plus `shared`. A scenario
typically implements: a `Scenario` subclass, a `HypothesisGen`, a `Hypothesis2Experiment`,
`Coder` + `Runner` developers, and an `Experiment2Feedback`. Example (qlib factor):
`scenarios/qlib/experiment/factor_experiment.py:QlibFactorScenario`,
`.../proposal/factor_proposal.py`, `.../developer/factor_coder.py` (CoSTEER),
`.../developer/factor_runner.py`.

### Reusable components (`rdagent/components/`)
Cross-scenario building blocks scenarios compose: `coder/` (incl. the CoSTEER
evolving-coder framework), `runner/`, `proposal/`, `workflow/` (`RDLoop` +
`BasePropSetting`), `knowledge_management/` (RAG), `benchmark/`, `loader/`,
`document_reader/`, `interactor/`, `agent/`.

### LLM backend (`rdagent/oai/`)
`LLMSettings` (`llm_conf.py`) holds model/key config; `backend` is a **class path**,
defaulting to `rdagent.oai.backend.LiteLLMAPIBackend` (`backend/litellm.py`), loaded
dynamically via `import_class()`. **LiteLLM means any provider works** — including
local OpenAI-compatible servers (llama.cpp, vLLM) via `CHAT_MODEL=openai/<name>` +
`OPENAI_API_BASE`. `LiteLLMSettings` uses `env_prefix = "LITELLM_"` for its own knobs.
Adding a backend = subclass `APIBackend` and point `BACKEND` at it (fork-friendly,
no upstream edit). See `FORK.md §5`.

### Configuration (`rdagent/core/conf.py`)
Pydantic-settings based. `ExtendedBaseSettings` is the base; `RDAgentSettings` holds
global knobs. Each scenario has a config class inheriting `BasePropSetting`
(`components/workflow/conf.py`) with its own `env_prefix` (e.g. `QLIB_FACTOR_`, `DS_`)
that wires up the scenario's class paths (`scen`, `hypothesis_gen`, `coder`, `runner`,
…). **This is the primary extension seam**: register a new scenario by writing the
classes + a config class — no upstream file is modified.

### Docker execution (`rdagent/utils/env.py`)
LLM-generated code runs in sandboxed environments via the `Env` abstraction:
`DockerEnv`/`DockerConf` (+ per-scenario subclasses like `QTDockerEnv`, `DSDockerEnv`)
and a `LocalEnv` fallback. Runners call `env.execute(...)`. This is why most scenarios
need Docker (`docker run hello-world` must work without sudo).

### CLI (`rdagent/app/`)
`cli.py` is a **Typer** app (entry point `rdagent = rdagent.app.cli:app`). Subcommands
map to `rdagent/app/<area>/` (`qlib_rd_loop/`, `data_science/`, `general_model/`,
`finetune/`, `rl/`, `benchmark/`, `utils/`). Each command loads a scenario config class,
instantiates an `RDLoop` subclass, and runs the loop.

## Conventions

- **Extension over modification.** Almost everything is config-driven class loading
  (`import_class()` on dotted paths). Add a scenario/backend/component as new files +
  a config class rather than editing upstream. Put fork-only code in `rdagent/custom/`
  (this fork's private dir). See `FORK.md §2`.
- **CI runs offline only.** `make test-offline` (pytest `-m offline`) + `make lint`
  (ruff + mypy). Don't make offline tests require Docker or network/API keys.
- **mypy is strict** (`disallow_untyped_defs`, etc. in `pyproject.toml`). Type new code.
- **Docker is the execution substrate** for real scenario runs; the offline test suite
  and `health_check` do not need a live model.
