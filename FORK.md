# FORK.md — 本 Fork 的定制规范与维护手册

> **这是什么**：本仓库是从 [microsoft/RD-Agent](https://github.com/microsoft/RD-Agent)
> fork 而来的**自用定制版**。本文件是本 fork 的"单一事实来源"——记录我们和上游的差异、
> 定制规范、同步上游的操作流程、以及本地（WSL + llama.cpp）运行配置。
>
> **读者**：未来的我，以及任何进入本仓库的 agent（Claude Code / Codex 等）。
> **维护**：每次新增/修改定制，或同步一次上游，都要回来更新对应章节 + 底部"最后更新"。
>
> **最后更新**：2026-06-14（环境跑通 + 美股回测结果 ×2；GPU 镜像就绪[cu128/sm_120]；RD-Agent 循环有
> China-only/SDK bug，已用 `rdagent/custom/` 薄驱动绕过直接 qrun，见 §9.7/§9.8/§9.9/§10）

---

## 0. 本 Fork 的定位（先读这一节）

- **目的**：自用。在本地（WSL2 + RTX 5090 + llama.cpp）跑 RD-Agent 这个"自动化 R&D"
  多智能体框架，并按需加入我们自己的能力。
- **不提 PR**：我们**不打算**把改动贡献回上游 `microsoft/RD-Agent`。
  原因：(1) 没必要；(2) 上游不一定接受。
  → 推论：**无需保持 `main` 的"上游纯净度"**，`main` 就是我们的定制主线。
- **核心诉求**：既要**吃到上游更新**，又要**保留自己的定制**，还不能让两者打架。
  - 打架的唯一根源 = **合并冲突** = 我们和上游改了**同一行代码**。
  - 因此所有规范的本质，都是"降低与上游改同一行的概率"，而**与提不提 PR 无关**。

> 规范沿用我们在 `~/Development/Github/TradingAgents` 那套自用 fork 工作流（同一套思路：
> 扩展优于修改 / `Fork:` trailer 门禁 / merge 不 rebase）。

---

## 1. 当前状态（与上游的关系）

| 项 | 值 |
|---|---|
| 上游 (`upstream`) | https://github.com/microsoft/RD-Agent |
| 我们的远程 (`origin`) | https://github.com/ybwbqg9379/RD-Agent |
| Fork 基点 commit | `4f9ecb00`（`Document FT-Agent ICML release (#1406)`, 2026-05-06） |
| 当前与上游差异 | **0 ahead / 0 behind**（尚无任何本地定制；干净起点） |

> 上游是个非常活跃的多人仓库（数百分支）。我们只跟 `upstream/main`，其余分支不管。

---

## 2. 定制规范（动手前必读）

### 原则一：扩展优于修改（最重要）
能**加新文件**就绝不**改旧文件**。RD-Agent 大量用"配置里写类路径 + `import_class()` 动态加载"
的模式，扩展点设计良好，绝大多数定制都能不碰核心代码：

| 想做的事 | 落点（无需改上游文件） |
|---|---|
| 换模型 / 换端点 / 调参数 | `.env` 里的环境变量（见 §5；LLM 走 `LITELLM_*` / `OPENAI_API_*`） |
| 换 LLM 后端 | 写新 backend 类（继承 `rdagent.oai.backend` 的 `APIBackend`），`.env` 里把 `BACKEND` 指过去 |
| 加一个新 Scenario | 新建 `rdagent/scenarios/<我们的场景>/`（`Scenario`/`HypothesisGen`/`Coder`/`Runner`/`Experiment2Feedback` 各实现一份）+ 一个继承 `BasePropSetting` 的配置类，用 `env_prefix` 区分 |
| 换某个组件（Coder/Runner/提案器/反馈器） | 在 fork 自己的包里写新类，靠 scenario 的配置类把类路径指过去（不改上游类） |
| 我们自己的独立逻辑 | 新建 `rdagent/custom/`（本 fork 约定的私有目录，参照 TradingAgents 的 `custom/`） |

### 原则二：必须改上游文件时，把改动做到最小且可追踪
1. 真正的逻辑抽到独立模块（如 `rdagent/custom/...`），上游文件里只留**一行调用**。
2. 在改动处用统一标记，便于 `grep` 一键找出我们所有的侵入式改动：
   ```python
   # [FORK] 原因简述；详见 FORK.md §6 / rdagent/custom/xxx.py
   ```
3. 改完后到 §6 差异清单登记一条。

### 原则三：每条定制都登记
任何会让我们偏离上游的改动，都到 **§6 差异清单**记一行：做了什么 / 为什么 / 碰了哪些文件。
这样下次 merge 上游冲突时，能立刻判断每处冲突该怎么取舍。

### 快速自检：找出当前所有侵入式改动
```bash
grep -rn "\[FORK\]" --include="*.py" .          # 所有标记的侵入式改动
git diff --stat upstream/main..main             # 我们改/加了哪些文件
git log --oneline upstream/main..main           # 我们的全部定制 commit
git log --grep '^Fork:' --oneline               # 同上，靠 commit 的 Fork: 标记（见 §3）
```

---

## 3. Commit 规范与门禁

上游遵循 **Conventional Commits**（PR 标题有 `Lint PR Title` CI 校验）。我们**沿用同一套格式**
（这样同步上游后 `git log` 风格统一），并加一条标记把我们自己的 commit 和上游区分开。
**这条规范由一个本地（非 CI）git 门禁强制执行**，不合规的 commit 会被拒绝。

### 3.1 格式
```
<type>(<scope>): <description>

<body，可选>

Fork: <一句话说明这条改动为什么是我们加的>   ← 本 fork 的强制标记（见 3.2）
```

- **type**：`feat` | `fix` | `docs` | `refactor` | `perf` | `test` | `build` | `ci` | `chore` | `revert`
- **scope**：小写的子系统名，如 `core` `oai` `scenarios` `components` `app` `qlib`
  `data_science` `kaggle` `finetune` `rl` `docker` `conf` `docs` `deps`；本 fork 自己的横切改动可用 `fork`
- **description**：祈使句、不加句号；建议 ≤72 字符（门禁硬上限 100）
- 引用上游 issue 时沿用上游写法，在描述末尾加 `(#123)`

### 3.2 我们的 commit 如何与上游区分
**约定：凡是我们自己 author 的 commit，都必须带一个 `Fork:` trailer**（body 里单起一行，
`Fork: <原因>`）。

- 为什么用 trailer 而不是改 type/scope：保持和上游**完全一致**的 `type(scope): ...` 主题行，
  历史风格统一；区分信息放在 footer，既不污染主题、又能稳定 `grep`。
- 好处：`git log --grep '^Fork:'` 永远精确列出"我们加的东西"，即使多次 merge 之后我们的
  commit 和上游 commit 在 `git log` 里交错，也一眼可辨。
- 上游 commit 是通过 `git merge upstream/main` **合并**进来的，我们并不 author 它们，
  所以它们不带 `Fork:`，门禁也会放行 merge commit（见下）。

示例：
```
feat(scenarios): add A-share factor scenario

Fork: 上游 qlib 场景默认美股/中证，本地自用想跑 A 股因子
```

### 3.3 门禁（本地 git hook，强制、非 CI）
门禁是一个版本化的 `commit-msg` 钩子，位于 **`.githooks/commit-msg`**。它会拒绝：
1. 主题行不符合 `type(scope): description`；
2. 主题超过 100 字符；
3. 缺少 `Fork:` trailer。

`merge` / `revert` / `fixup!` / `squash!` 这类自动生成或非我们 author 的消息会被自动放行
（上游 commit 正是经由 merge 进来）。

**启用（每个 clone 一次性操作）**——git 钩子不随 clone 分发，需要把 git 指到 `.githooks/`：
```bash
./scripts/setup-hooks.sh            # 等价于 git config core.hooksPath .githooks
git config --get core.hooksPath     # 验证，应输出 .githooks
```
> **给 agent 的提示**：进入本仓库后若 `git config --get core.hooksPath` 为空，
> 先跑 `./scripts/setup-hooks.sh` 再开始工作。
>
> 真正的紧急情况可用 `git commit --no-verify` 绕过，但**不鼓励**，且仍要事后补登记 §6。

---

## 4. 同步上游的标准流程（SOP）

我们用的是 **"`main` 即定制主线"** 模式（不开独立定制分支，因为不提 PR）。
定期把上游合并进来即可：

```bash
# 1. 确保工作区干净
git status

# 2. 拉取上游最新
git fetch upstream

# 3. 看上游领先了多少、有哪些 commit
git log --oneline main..upstream/main

# 4. 合并进我们的 main（用 merge，不用 rebase——保留清晰的合并历史）
git merge upstream/main

# 5. 若有冲突：结合 §6 差异清单逐个解决，保留我们的定制意图
#    解决后：git add -A && git commit

# 6. 跑一遍冒烟测试（见 §7）确认没被上游改动弄坏

# 7. 推到我们自己的 origin
git push origin main

# 8. 回到本文件更新 §1 的"Fork 基点 commit"和底部"最后更新"
```

> **为什么用 merge 不用 rebase**：我们不提 PR，不需要线性历史；merge 能完整保留
> "某次同步上游"这个事件，将来排查问题更清楚，也不会重写已推送的历史。

---

## 5. 本地运行配置（WSL + llama.cpp）

> RD-Agent **大多数场景依赖 Docker**（LLM 生成的代码在容器里跑）。确保 `docker run hello-world`
> 无需 sudo 可跑通（见上游 README "Quick start"）。LLM 推理本身走本机 llama.cpp，与 Docker 无关。

> ✅ **以下配置 2026-06-14 已实测跑通**（uv 3.11 venv + chat/embedding 双 llama.cpp + Docker）。
> rdagent `APIBackend` 端到端验证：chat 返回正常、embedding 返回 1024 维向量。

### 5.1 安装（实测：用 uv 建 3.11 venv，别用系统 3.12）
上游 CI 只测 Python **3.10/3.11**（`constraints/3.11.txt` 在仓库里）；本机系统 Python 是 3.12，
**不要**直接用。用 uv 建隔离 venv：
```bash
uv venv --python 3.11 .venv                                   # 建 3.11 venv
uv pip install --python .venv/bin/python -e '.[lint,test]' -c constraints/3.11.txt
# 注：uv venv 默认不含 pip，别再 `python -m pip ...`，全程用 `uv pip`。
# 跑 rdagent 用 .venv/bin/rdagent（或 source .venv/bin/activate）。
./scripts/setup-hooks.sh                                       # 启用 commit 门禁（每 clone 一次）
```
> `make dev` 也行（装 docs,lint,package,test 全量），但它假设 conda/pipenv 环境；本机没 conda，
> 上面的 uv 路线更省、更可控。`[lint,test]` 足够跑 CLI + `pytest -m offline` + lint。

### 5.2 指向本机 llama.cpp —— chat + embedding 双 server（不花 API 钱）
RD-Agent 默认后端是 **LiteLLM**（`rdagent.oai.backend.LiteLLMAPIBackend`）。它**需要 chat
和 embedding 两个模型**（embedding 用于知识库/RAG；`health_check` 第一步就测 embedding）。
本机没有 embedding 模型，故采"全本地 embedding"：**起两个 llama.cpp，端口错开**。

**当前默认组合（2026-06-14 实测）**：chat = `granite8b`（轻量）+ embedding = **Jina Embeddings v5**。

**(1) embedding server @ 8081** —— Jina v5 small-retrieval（2026-02 发布，677M，官方 GGUF，
119 语言，RAG 调优；已下 F16 到 `~/models/gguf/jina-embeddings-v5-small-retrieval/`）：
```bash
~/llama.cpp/build/bin/llama-server \
  --model ~/models/gguf/jina-embeddings-v5-small-retrieval/v5-small-retrieval-F16.gguf \
  --host 0.0.0.0 --port 8081 \
  --embeddings \
  -ngl 999 -c 2048 -ub 2048 -b 2048 --no-warmup
# ⚠️ 不要加 --pooling！Jina v5 的 GGUF 自带正确 pooling_type(=last)，手动指 --pooling mean
#    会触发 "model default pooling_type is [3], but [1] was specified" 并降低检索质量。
# ⚠️ batch 仍压到 2048（-ub/-b）：大 batch 会让 compute buffer 暴涨。F16 此配置占 ~3GB。
```

**(2) chat server @ 8080** —— granite8b（8B，CTX 压到 32K，避免 128K 的巨大 KV）：
```bash
CTX=32768 ~/start-llamacpp.sh granite8b   # 8B 轻量，~9GB；和 jina 共存仅 ~17.7GB，宽松
```

**(3) `.env`**（仓库根，已 gitignore；chat 走 `openai/`+8080，embedding 走 `litellm_proxy/`+8081）：
```bash
BACKEND=rdagent.oai.backend.LiteLLMAPIBackend
CHAT_MODEL=openai/granite8b
OPENAI_API_BASE=http://localhost:8080/v1
OPENAI_API_KEY=sk-local-dummy
EMBEDDING_MODEL=litellm_proxy/jina-v5-small
LITELLM_PROXY_API_BASE=http://localhost:8081/v1
LITELLM_PROXY_API_KEY=sk-local-dummy
USE_CHAT_CACHE=True
USE_EMBEDDING_CACHE=True
```
> **为什么 embedding 用 `litellm_proxy/` 前缀**：litellm 的 `openai/` provider 只认全局
> `OPENAI_API_BASE`（=8080），无法给 embedding 单独指端点；`litellm_proxy/` 会读
> `LITELLM_PROXY_API_BASE`（=8081），这样 chat/embedding 各走各的 server。实测 OK。

**显存账（实测，32GB 单卡）**：jina v5 F16 ~3GB + granite8b@32K ~12GB + 基线 ~2GB
≈ **17.7GB / 32GB**，余 ~15GB，非常宽松。

### 5.3 选哪个本地模型
**chat**（RD-Agent 的 coder/proposal 吃模型，弱模型出烂代码/烂假设，按需求权衡）：
- **先跑通流程 / 省显存（当前默认）**：`granite8b`（8B，~12GB@32K，快）。质量一般但够验证全链路。
- **要真实效果**：换 `openai/qwen`（Qwen3.6-27B，质量最好）；但 + jina 后显存吃紧，chat 上下文要压到 ~32K，且 qwen 是 thinking 模型（`max_tokens` 要给足）。
- **超长上下文场景**：`gemma-moe`（256K）。

**embedding** = **Jina Embeddings v5 small-retrieval**（2026-02，最新轻量 SOTA，"把 4B 质量蒸馏进 sub-1B"，119 语言含中文，专门的 retrieval 变体对口 RAG）。1024 维。换 chat 不影响它。
- 备选：`jina-v5-text-nano`（239M，更小）；`EmbeddingGemma-300M`（Gemma 生态）；`Qwen3-Embedding-0.6B`（2025，曾用过）。
- embedding 固定用 `Qwen3-Embedding-0.6B`（1024 维），换 chat 模型不影响它。
- 各场景的真实上下文峰值/坑实跑后记到 §9。

### 5.4 运行一个场景
```bash
rdagent health_check          # 先自检
rdagent fin_factor            # qlib 因子循环
rdagent fin_model             # qlib 模型循环
rdagent fin_quant             # 因子+模型联合
rdagent data_science          # 通用数据科学 / Kaggle（--competition <name>）
rdagent general_model <url>   # 读论文/报告 → 抽取并实现模型
rdagent llm_finetune          # FT-Agent：LLM 微调循环
rdagent ui                    # Streamlit 日志查看器
rdagent server_ui             # Web UI 后端
```

---

## 6. 与上游的差异清单（Changelog of Divergence）

> 每条定制登记一行。当前为空——这是干净起点。

| 日期 | 定制内容 | 为什么 | 落点（文件） | 是否侵入上游文件 |
|---|---|---|---|---|
| 2026-06-14 | 加入 fork 治理文档骨架（本文件 + CLAUDE.md + commit 门禁 + setup 脚本） | 把自用 fork 工作流（同步上游/可追踪定制/commit 区分）固化下来 | `FORK.md`、`CLAUDE.md`、`.githooks/commit-msg`、`scripts/setup-hooks.sh`（均新增） | 否（纯新增，不碰上游代码） |
| 2026-06-14 | qlib 场景从 A 股改为**美股**（`cn_data→us_data`、`region cn→us`、`market csi300→sp500`、`benchmark SH000300→^GSPC`）| 我们研究美股不研究 A 股；us_data 已下到 `~/.qlib/qlib_data/us_data`（值取自姊妹 fork `qlib` 的 US workflow）。RD-Agent 无 region/market 配置开关，模板按固定路径加载，只能改模板 | `rdagent/scenarios/qlib/experiment/factor_template/*.yaml`(3)、`model_template/*.yaml`(2)、`factor_data_template/generate.py`，均 `# [FORK]` 标记 | **是**（6 文件，侵入式；同步上游时这几个模板若被上游改要留意冲突）|
| 2026-06-14 | 修 `QTDockerEnv.prepare()`：空 `extra_volumes` 提前返回（修运行时探测的 `StopIteration`）+ 检查 `us_data` 而非写死下载 `cn_data` | fin_model 在 `env_type=docker` 下，运行时探测用空挂载调 `get_model_env()` → `next(iter({}))` 崩；且原逻辑写死自动下 A 股 cn_data | `rdagent/utils/env.py`（`# [FORK]`）| **是**（核心文件，上游常改，合并冲突风险高）|
| 2026-06-14 | qlib 镜像加 `ENV MLFLOW_ALLOW_FILE_STORE=true` | 新版 MLflow 拒绝文件存储后端、qrun 回测会 abort，需此 opt-out | `rdagent/scenarios/qlib/docker/Dockerfile`（`# [FORK]`，需重建镜像）| **是**（1 行）|
| 2026-06-14 | qlib 镜像改用姊妹 fork `ybwbqg9379/qlib`（替代上游固定老 commit）| 连上我们的 qlib fork + 用能读 us_data 的较新 qlib | `rdagent/scenarios/qlib/docker/Dockerfile`（`# [FORK]`）| **是**（1 行 clone URL）|
| 2026-06-14 | 新增 `rdagent/custom/` 私有包 + 美股回测薄驱动 | RD-Agent 的 fin_* 循环有 China-only/docker-SDK bug（§9.7）；薄驱动绕过它、直接 qrun 出美股回测 | `rdagent/custom/__init__.py`、`rdagent/custom/us_qlib_backtest.py`（均新增；后者支持 `--gpu`）| 否（纯新增私有目录）|
| 2026-06-14 | qlib 镜像升级 torch 到 cu128（Blackwell/sm_120）| 基底 cu121 torch 无 5090 kernel，神经网络上 GPU 报错；升 cu128 让 5090 可训练（§9.9）| `rdagent/scenarios/qlib/docker/Dockerfile`（`# [FORK]` 一行 pip）| **是**（1 行，需重建镜像）|

> 注：上游 `.gitignore` 第 190 行 ignore 了整个 `scripts/`，故 `scripts/setup-hooks.sh` 是
> **`git add -f` 强制追踪**的（刻意不改上游 `.gitignore`，避免无谓的差异/合并冲突）。
> 该文件已被追踪后，ignore 规则对它不再生效；但**新增到 `scripts/` 的其它文件仍会被忽略**，
> 需要时同样用 `git add -f`。

<!--
登记模板：
| 2026-06-XX | 加了 XXX 场景 | 上游不支持 A 股因子 | rdagent/scenarios/xxx/（新增）+ rdagent/app/xxx 配置 | 否 |
| 2026-06-XX | 改了 runner 超时逻辑 | 本地单卡更慢 | rdagent/custom/runner_patch.py + utils/env.py 一行调用 [FORK] | 是 |
-->

---

## 7. 冒烟测试（同步上游后/改动后跑一遍）

```bash
# 上游 CI 跑的离线测试（不需要 Docker / API key）—— 用 venv 里的工具
.venv/bin/pytest -m offline -q          # 或 make test-offline（需 conda/pipenv）
.venv/bin/ruff check rdagent/core

# 环境自检：先起两个 llama.cpp（见 §5.2），再
.venv/bin/rdagent health_check
#   ⚠️ embedding 子测试会误报红叉（health_check 的 bug，见 §9.1）；chat/Docker/端口绿即可。
#   真要确认 embedding 通：curl http://localhost:8081/v1/embeddings（见 §9.1）。

# 端到端最小验证（需 Docker + 双 server）：跑一个最便宜的场景确认没被上游改动弄坏
# 例如最少迭代数的 fin_factor / data_science（具体命令实跑后补到 §9）
```

---

## 8. 维护本文件

- **新增/修改定制** → 更新 §6 差异清单（必要时 §2 原则）。
- **同步一次上游** → 更新 §1 的"Fork 基点 commit" + 跑 §7 冒烟测试。
- **改了本地运行方式/端口/模型** → 更新 §5。
- **改了 commit 规范或门禁** → 更新 §3 + `.githooks/commit-msg`。
- **跑出新的本地运行经验/坑** → 记到 §9。
- 每次改完，更新顶部"最后更新"日期。

---

## 9. 本地运行的已知问题与经验

> 实测记录。2026-06-14：环境配置 + LLM 双端点已跑通；**fin_model 美股循环已跑到 qlib 回测的
> 数据加载阶段**（提案→编码→docker 验证→qrun 启动全通），仅剩一个 qlib 配置/版本问题（见 §9.6）。
> fin_factor 被 conda 硬编码挡住（§9.5）。下面是逐项踩的坑。

### 9.0 跑 qlib 场景需要的本地配置（`.env`，已 gitignore）
除 §5 的 LLM 配置外，跑 fin_model 还需：
```bash
MODEL_CoSTEER_ENV_TYPE=docker     # 模型代码执行走 docker(local_qlib)，否则默认 conda 崩
QLIB_DOCKER_ENABLE_GPU=True        # 镜像已装 cu128 torch(sm_120)，5090 可用（见 §9.9）
```
- **GPU 已可用**：镜像现装 **torch 2.11.0+cu128**（带 Blackwell/sm_120 kernel），5090 能在容器里
  训练 PyTorch 模型。详见 §9.9。（历史：原 cu121 torch 无 sm_120 kernel，曾报
  `CUDA error: no kernel image is available`、被迫关 GPU 走 CPU；现已升级解决。）

### 9.1 `health_check` 的 embedding 子测试在"分离端点"setup 下会误报失败（不是真问题）
- 现象：`rdagent health_check` 报 `❌ Embedding test failed: ... 501 This server does not support
  embeddings`，但 chat ✅ / Docker ✅ / 端口 ✅。
- 根因：`rdagent/app/utils/health_check.py:env_check()` 在 `OPENAI_API_KEY` 分支里**硬把
  `embedding_api_base = chat_api_base`**（只有 DeepSeek 分支才读 `LITELLM_PROXY_API_BASE`）。
  于是它把 embedding 请求发到了 chat server(8080)，而 8080 没开 `--embeddings` → 501。
- **真实运行路径不受影响**：默认 LiteLLM 后端 `_create_embedding_inner_function` 调
  `embedding(model=..., input=...)` **不传 api_base**，由 litellm 按 `litellm_proxy/` 前缀读
  `LITELLM_PROXY_API_BASE`(=8081) 正确路由。已用 `APIBackend().create_embedding([...])` 实测返回 1024 维向量。
- 结论：**health_check 的 embedding 红叉可忽略**；要确认 embedding 真的通，用：
  ```bash
  curl -s http://localhost:8081/v1/embeddings -H "Content-Type: application/json" \
    -d '{"input":"hi","model":"qwen3-embedding"}' | head -c 80
  ```

### 9.2 embedding server 的 batch 必须压小，否则显存爆
- `--ub/-b 8192` 会让 Qwen3-Embedding-0.6B 的 compute buffer 膨胀到 **~9GB**（0.6B 模型！），
  和 chat 一起必 OOM。`-ub 2048 -b 2048` 时只占 ~2.6GB。见 §5.2。

### 9.3 chat 上下文要为 embedding 让显存
- qwen 满 96K ≈ 29GB，加 embedding ~2.6GB 超 32GB。chat 用 `CTX=32768` 起，总占 ~28.4GB，稳。

### 9.4 装环境的坑
- 系统只有 Python 3.12（上游 CI 只测 3.10/3.11）→ 用 `uv venv --python 3.11`。
- `uv venv` 默认**不装 pip**，别 `python -m pip`（会 `No module named pip`），全程 `uv pip`。

### 9.5b 模型选型实测（2026-06-14）—— 当前默认 = granite8b + Jina v5
- **chat 从 qwen-27B 换 granite8b**：qwen 27B 太占显存（+emb 后 ~28.4GB），granite8b 8B 仅 ~12GB@32K，
  两 server 共存只 ~17.7GB，宽松。代价：8B 对复杂代码/提案质量弱，仅用于先跑通；要效果再换回 qwen。
- **embedding 从 Qwen3-Embedding-0.6B 换 Jina v5 small-retrieval**：用户要 2026 最新轻量款。Jina v5
  （2026-02）是当前轻量 SOTA，官方 GGUF 在你这版 llama.cpp 能加载，1024 维，跨语言语义正确
  （实测 cos(你好世界,hello world)=0.69、cos(你好世界,代码)=0.07）。
- **⚠️ Jina v5 不要手动 `--pooling`**：GGUF 自带 pooling_type=[3](last)，指 `--pooling mean` 会被覆盖
  并降质（日志报 `model default pooling_type is [3], but [1] was specified`）。不传 `--pooling` 即用默认。
- embedding 对量化敏感 → 用 **F16**（1.2GB，显存现在不缺）；要更省可换 Q8_0(639MB)。

### 9.5c fin_factor 被 conda 硬编码挡住（暂缓）
- `rdagent/components/coder/factor_coder/config.py:get_factor_env()` **写死** `LocalEnv(CondaConf(...))`，
  无 docker 分支，`CONDA_DEFAULT_ENV=None`（我们用 uv venv）→ 场景构造即崩。且因子源数据
  `git_ignore_folder/factor_implementation_source_data` 也不存在。→ 暂用 **fin_model**（不调 get_factor_env）。

### 9.7 ⚠️ 真正的根因：RD-Agent docker-SDK 包装层（不是数据/配置/qlib）
**2026-06-14 深入排查定论**：把 RD-Agent 的**确切 docker 调用手动复刻**——同镜像(fork qlib)、
同 conf、同 working_dir `/workspace/qlib_workspace`、同挂载(含 `/tmp/full→workspace_cache` 那个
泄漏进来的 data_science 缓存卷)、同 env(`PYTHONPATH=./` + 完整 20 特征 + TSDatasetH/step_len 等)
——`qrun` **完全跑通**：`Loading data Done`、`Train samples: 708182`、Epoch0 训练完成
(train 0.998/valid 0.999)。**但 RD-Agent 自己的循环跑同一份 conf 却 ~2 秒崩在 instrument freq 查找。**
- 已逐一排除：qlib 版本(升 fork d5379c52→f94643c0 无效)、Massive/AV 数据(RD-Agent 用标准 us_data
  不碰 us_data_massive)、数据质量(你 LightGBM 跑通过)、handler/TSDatasetH/processors(单独复刻全 OK)、
  working_dir/挂载/env(精确复刻全 OK)。
- → **根因在 RD-Agent 经 Python docker-SDK `client.containers.run(detach=True,...)` 发起容器的细节**
  (疑似挂载就绪时序竞态，或 SDK 传 env/卷的微妙差异)，而非 CLI。属 **RD-Agent 内部 bug**，可考虑给上游提 issue。
- **整条 RD-Agent 机器已证明在美股数据上可用**：提案→granite8b 编码→docker 验证→qrun→US Alpha158→
  GRU 训练全部跑通；只差 RD-Agent 这个包装层 bug。
- 候选下一步：(a) 给 RD-Agent 提 issue；(b) 深挖 DockerEnv 的 SDK 调用(env.py:1450 `containers.run`)；
  (c) 接受"机器已验证可用"，绕过其循环、直接用我们自己的脚本驱动 qrun 跑美股回测。**← 已选 (c)，见 §9.8。**

### 9.8 ✅ 绕过循环，直接跑出美股回测结果（已交付）
用 `rdagent/custom/us_qlib_backtest.py` 在 `local_qlib` 容器里直接 `qrun`（挂 us_data、无 LLM、不碰 RD-Agent 循环）。
一行命令：
```bash
.venv/bin/python -m rdagent.custom.us_qlib_backtest \
  --config examples/fork/workflow_config_lightgbm_alpha158_us.yaml
```
**首个美股回测结果（2026-06-14，LightGBM+Alpha158，S&P500，TopkDropout top50，测试期 2017-01~2020-08）：**

| 指标 | 基准(^GSPC) | 超额·无成本 | 超额·含成本 |
|---|---|---|---|
| 年化收益 | +12.08% | +1.24% | −1.94% |
| 信息比率 | 0.596 | 0.102 | −0.159 |
| 最大回撤 | −38.25% | −25.70% | −26.38% |

信号 IC=0.0066（弱）。**引擎全链路在美股跑通、出真实数字**；策略本身≈追平大盘、扣成本小幅跑输——
预期内（vanilla Alpha158 + CN 超参，非真 alpha；与姊妹 qlib fork Phase 2 结论一致）。
驱动也支持喂 RD-Agent 生成的模型工作区（`--workspace <dir> --config conf_*.yaml --env-json '{...}'`）。

**第二份：最新真实数据（Massive 自采，2026-06-14）**——`...us_massive.yaml`（`us_data_massive`，
market=all 734 只，benchmark=SPY，**回测期 2021-01~2026-06**，约 5.5 年）：

| 指标 | 基准(SPY) | 超额·无成本 | 超额·含成本 |
|---|---|---|---|
| 年化收益 | +13.75% | +0.91% | −0.07% |
| 信息比率 | 0.837 | 0.083 | −0.007 |
| 最大回撤 | −26.96% | −36.65% | −38.36% |

信号 IC=0.0013（极弱）。SPY 这 5.5 年年化 +13.75%（牛市），策略**几乎完全贴着大盘**走。
**含成本超额 −0.07%/年 与姊妹 qlib fork Phase 2 记录一字不差**——证明本驱动这条路精确复现了直接跑 qlib 的结果。

**第三份：RD-Agent 生成的 GRU 模型 + GPU 训练（2026-06-14）**——`--workspace <RD-Agent 生成的工作区>
--config conf_baseline_factors_model.yaml --env-json '{...}' --gpu`（us_data，sp500，回测期 2017-01~2020-08）。
granite8b 生成的 `GRU_TimeSeries_Model`（2 层 GRU），在 5090 上训 17 epoch（best@9，early stop）：

| 指标 | 基准(^GSPC) | 超额·无成本 | 超额·含成本 |
|---|---|---|---|
| 年化收益 | +12.08% | +5.85% | **+1.31%** |
| 信息比率 | 0.596 | 0.552 | 0.124 |
| 最大回撤 | −38.25% | −15.55% | **−19.98%** |

信号 IC=0.0062。这一轮含成本超额 **+1.31%**（vs LightGBM −1.94%）、回撤 −19.98%。**但⚠️ run-to-run 噪声很大**：
同一 GRU/数据换随机种子重训，另一轮含成本超额是 **−1.90%**（IC 0.0032）。**所以 +1.31% 不是稳健 alpha，只是随机波动**
（与 IC 极弱一致）。真正证明的是**整条链路在美股可用**：LLM 生成 → GPU 训练 → 美股回测全通；要稳健 alpha 仍需
RD-Agent 多轮进化更好的因子/模型（vanilla Alpha158 + 单个 LLM 生成 GRU 都还不是 alpha）。

**三份对照**：us_data(标准 dump) 只到 2020-11；要 2021–2026 的近期美股必须用 Massive 自采的 `us_data_massive`。
引擎+美股全链路可用；vanilla Alpha158(LightGBM) 非 alpha，但 RD-Agent 生成的 GRU 已出正超额——真 alpha 要靠
RD-Agent 进化因子/模型（其循环现被 China-only bug 挡着，§9.7，走本驱动或修循环）。

### 9.9 ✅ GPU 镜像：让 5090 在容器里训练 PyTorch 模型（cu128）
**壁垒**：qlib 镜像基底 `pytorch:2.2.1-cuda12.1` 的 torch 没有 5090（Blackwell, **sm_120 / cc 12.0**）的
GPU kernel，神经网络（GRU 等）一上 GPU 就报 `CUDA error: no kernel image is available`。LightGBM 是 CPU
树模型、不受影响。
**修法（Dockerfile [FORK]）**：升级容器 torch 到 **cu128（CUDA 12.8）的 Blackwell 构建**：
```dockerfile
RUN pip install --index-url https://download.pytorch.org/whl/cu128 --upgrade torch
```
- torch wheel **自带 cu128 runtime**，覆盖基底的 cu121；**主机 CUDA-13.2 toolkit 与容器无关**，只需主机
  **驱动**够新（610.47 够）。
- 实测（2026-06-14，本镜像内 `--gpus all`）：`torch 2.11.0+cu128`、`sm_120 ∈ archs`、`cuda available: True`、
  `RTX 5090`、GPU matmul + **GRU 前向**均 OK。镜像 16.5GB→**29.6GB**。
- cu128 是**这台机器已验证可用**的 Blackwell torch（`~/vllm-venv` 的 2.11.0+cu128 也列 sm_120）。
- 启用：`.env` `QLIB_DOCKER_ENABLE_GPU=True`（RD-Agent 自己的 run）；custom 驱动用 `--gpu`（加 `--gpus all`）。
- ⚠️ OpenWhisper 在 Windows 侧共用这张卡(~10GB)，但小 NN 占显存少，够用。
- **提速实测**：GRU 训练 **CPU ~15 分/epoch → GPU ~20–60 秒/epoch（约 45×）**。

**跑 PyTorch 模型时的两个容器坑（驱动已处理 / 需注意）：**
- **`--shm-size`**：PyTorch DataLoader 多 worker 用 `/dev/shm` 传张量，Docker 默认 64MB 会
  `unable to allocate shared memory`。驱动 `us_qlib_backtest.py` 已固定加 `--shm-size=16g`（同 RD-Agent QlibDockerConf）。
- **DataLoader worker 死锁（已根治）**：qlib `GeneralPTNN` 原本每 epoch 重 fork `n_jobs` 个 DataLoader
  worker，在容器里**验证阶段间歇性死锁**（fork-after-threads + qlib mmap 数据；进程全 0% CPU，即使 shm 够）。
  **根因 + 修法见姊妹 qlib fork 的 commit `51ba755a`**：给三个 DataLoader 加 `persistent_workers=self.n_jobs>0`
  （worker 只 fork 一次、跨 epoch 复用，消除每 epoch 重 fork 的竞态）。**实测（含此补丁的镜像）n_jobs=20
  顺畅训完、~15 秒/epoch、无死锁** —— 既快又稳，不必再设 0。（注：旧镜像/未打补丁时仍需 `n_jobs: 0` 兜底。）

### 9.6 fin_model 的数据加载报错链（已排查，根因见 §9.7）
现状：fin_model 前面全通（提案→granite8b 编码 GRU→docker 验证"Execution successful"→qrun 启动、
US Alpha158 特征、CPU 训练），但 qlib **数据 handler `setup_data` 阶段**报：
```
ValueError: instrument: {'__DEFAULT_FREQ': '/root/.qlib/qlib_data/us_data'} does not contain data for day
```
- 排除项：容器 qlib **能正常读 us_data**（单标的 AAPL $close ✅、sp500 池 724 标的 ✅、日历 ✅）。
- 失败的是 **RD-Agent 生成的 handler 配置**（`conf_baseline_factors_model.yaml`：NestedDataLoader +
  Alpha158DL + 自定义 20 特征 + `Ref($close,-2)` label），错误里 `instrument: {freq dict}` 是**畸形参数**。
- ~~曾猜根因是 qlib 版本（老 commit `2fb9380b`）~~ → **已证伪**：升级到 fork 的新 qlib（f94643c0）后报错依旧。
- **最终定论见 §9.7**：根因是 RD-Agent 的 docker-SDK 循环包装层（手动 qrun 同参数必通），不是数据/配置/qlib。
  **已绕过**：用 `rdagent/custom/us_qlib_backtest.py` 直接 qrun 出美股回测（§9.8）。

### 9.5 还没验证、预期可能遇到的（跑场景时填）
- **本地模型上下文撑爆**：某些场景把大量数据塞进 prompt → 换 `gemma-moe`(256K) 或缩数据。
- **structured-output / function-calling 偏弱**：本地模型弱于商业模型，留意框架是否优雅降级。
- **thinking 模型 `max_tokens`**：给太小会被思维链吃光，`content` 为空（qwen 是 thinking 模型）。

---

## 10. 路线图（本 fork 自己的方向）

> 跨 session 的持久路线图。当前未规划具体自建能力——先把框架在本地跑通（§5 / §9），
> 再决定要在 `rdagent/custom/` 或新 scenario 里加什么。进 session 先看这里。

| 阶段 | 内容 | 状态 | 验收标准 |
|---|---|---|---|
| 0 文档骨架 | FORK.md / CLAUDE.md / commit 门禁 | ☑ 完成 | 文档就位、门禁可启用 |
| 1 本地跑通 | 用 llama.cpp 跑通至少一个场景，沉淀 §5/§9 经验 | ☑ 完成 | env 实测通；RD-Agent 机器在美股上 提案→编码→训练 全跑通（仅其 fin_* 循环包装层有 China-only/SDK bug，§9.7）；**绕过它已出首个美股回测结果**（§9.8，`rdagent/custom/us_qlib_backtest.py`） |
| 2 美股评测驱动 | `rdagent/custom/` 薄驱动绕过 RD-Agent 循环、直接 qrun 出美股回测 | ☑ 完成 | LightGBM/Alpha158（§9.8）+ **RD-Agent 生成的 GRU**（§9.8 第三份）都出真实指标 |
| 3 GPU 加速 | 让 5090 在容器里训 PyTorch 模型（cu128/sm_120）| ☑ 完成 | §9.9；GRU 训练提速 ~45×；含成本 +1.31% 跑赢基线 |
| 4 待定 | 修 RD-Agent 循环 / 给上游提 issue / 更强模型(qwen)进化因子模型看真 alpha | ☐ 未规划 | — |
