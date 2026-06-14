# FORK.md — 本 Fork 的定制规范与维护手册

> **这是什么**：本仓库是从 [microsoft/RD-Agent](https://github.com/microsoft/RD-Agent)
> fork 而来的**自用定制版**。本文件是本 fork 的"单一事实来源"——记录我们和上游的差异、
> 定制规范、同步上游的操作流程、以及本地（WSL + llama.cpp）运行配置。
>
> **读者**：未来的我，以及任何进入本仓库的 agent（Claude Code / Codex 等）。
> **维护**：每次新增/修改定制，或同步一次上游，都要回来更新对应章节 + 底部"最后更新"。
>
> **最后更新**：2026-06-14（环境跑通；默认模型定为 granite8b + Jina Embeddings v5；见 §5/§9）

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

> 实测记录。2026-06-14：环境配置 + LLM 双端点已跑通（chat+embedding via rdagent APIBackend），
> **但尚未实跑任何完整场景**（fin_factor / data_science 等），下面是配置阶段踩的坑。

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

### 9.5 还没验证、预期可能遇到的（跑场景时填）
- **本地模型上下文撑爆**：某些场景把大量数据塞进 prompt → 换 `gemma-moe`(256K) 或缩数据
  （参照 TradingAgents：基本面全量数据曾撑爆 qwen 96K）。注意还要给 embedding 留显存。
- **structured-output / function-calling 偏弱**：本地模型弱于商业模型，留意框架是否优雅降级。
- **Docker 坑**：镜像构建、GPU 透传、卷挂载、超时。
- **thinking 模型 `max_tokens`**：给太小会被思维链吃光，`content` 为空（qwen 是 thinking 模型）。

---

## 10. 路线图（本 fork 自己的方向）

> 跨 session 的持久路线图。当前未规划具体自建能力——先把框架在本地跑通（§5 / §9），
> 再决定要在 `rdagent/custom/` 或新 scenario 里加什么。进 session 先看这里。

| 阶段 | 内容 | 状态 | 验收标准 |
|---|---|---|---|
| 0 文档骨架 | FORK.md / CLAUDE.md / commit 门禁 | ☑ 完成 | 文档就位、门禁可启用 |
| 1 本地跑通 | 用 llama.cpp 跑通至少一个场景，沉淀 §5/§9 经验 | ◐ 进行中 | **env 已配好并实测**（uv 3.11 venv + chat/emb 双 server + Docker，rdagent APIBackend 端到端通，见 §5/§9）；**待办 = 实跑一个完整场景**（fin_factor/data_science 最小迭代） |
| 2 待定 | 我们自己的能力（视用途定） | ☐ 未规划 | — |
