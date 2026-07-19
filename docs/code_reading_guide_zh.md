# AIE-DDxBench 构建代码中文导读

这份文档写给第一次阅读本项目代码的人。你不需要预先熟悉整个生成历史，
也不需要一开始就理解所有 Python 语法。目标不是让你一次记住每个函数，
而是让你能够回答下面五个问题：

1. 程序从哪里开始？
2. 一个输入文件经过哪些步骤变成一个 case？
3. 每一步读了什么、写了什么？
4. 哪些判断由模型完成，哪些判断由本地程序完成？
5. 出错时应该先看哪个文件？

建议按本文顺序操作。不要从最大的文件开始逐行硬读，也不要第一次就运行
几十篇论文。

## 1. 先建立一个最简单的认识

这套代码做的事情可以简化成下面一条链：

```text
论文解析结果 source.md
    -> 论文级筛选
    -> 候选分子提取
    -> 候选 SMILES 生成
    -> RDKit 化学检查
    -> 论文结构图与 RDKit 分子图对照
    -> 锁定 SMILES
    -> 构建 evidence 和 diagnosis
    -> 本地 gate
    -> 独立 Stage 5 审核
    -> 必要时 minor repair 和复审
    -> 数据集级去重
    -> 打包提交
```

这里最重要的对象是一个“具体分子的 case”，而不是一整篇论文。一篇论文
可能产生零个、一个或多个候选分子，但每个最终 case 只对应一个明确的目标
分子输入。

## 2. 先认识几个基础词

### 2.1 `source.md`

`source.md` 是论文经过 MinerU 等工具解析后得到的 Markdown 文本。模型从
这里读取正文、图注、表格和页码信息。它不是最终 benchmark JSON。

### 2.2 manifest

manifest 是一个 JSON 清单。它告诉程序：

- 有哪些论文；
- 每篇论文的 `source.md` 在哪里；
- 用哪个机制类别作为检索线索；
- 准备处理哪些目标分子；
- 每个分子的论文结构图在哪里；
- 最终 case 应使用哪个 ID。

可以把 manifest 理解成“批处理任务单”。示例位于：

```text
examples/pipeline_manifest.example.json
```

### 2.3 public input

public input 是评测时给被评测系统看的内容。当前格式只允许：

- 已确认的 SMILES；
- 一条固定的通用任务说明。

它不能包含 DOI、论文标题、分子简称、机制答案或论文观察。

### 2.4 hidden reference

hidden reference 是评测时隐藏的参考答案，包含：

- 来源论文和目标分子的身份信息；
- `reference_evidence_units`；
- `reference_diagnosis_units`；
- 最终综合诊断单元。

### 2.5 evidence unit

一个 evidence unit 表示一项可追溯到论文的实验或计算证据。它包含证据
陈述、机制解释、来源位置和论文原文引用 `paper_quote`。

### 2.6 diagnosis unit

一个 diagnosis unit 表示对某个机制的判断。它通过
`supporting_evidence_ids` 指向 evidence unit，并记录该机制是
`supported`、`weakened_or_rejected` 还是 `underdetermined`。

### 2.7 local gate

local gate 是确定性的本地检查。它不依赖语言模型。相同输入应得到相同
结果。它负责检查 schema、SMILES 锁定、ID 链接、原文引用和答案泄露等。

### 2.8 independent review

independent review 是独立语言模型审核。它只查看三个文件：

```text
final_reference_alignment.json
source.md
structure_match.png
```

审核结果是：

```text
PASS
PASS_WITH_CAVEAT
NEEDS_MINOR_FIX
FAIL_OR_REBUILD
```

### 2.9 `0.4`、`v0.4` 和 `v04`

它们不是三个版本。项目统一规定：

- JSON 字段写作 `"version": "0.4"`；
- 正文和说明文档写作 `v0.4`；
- 不便使用小数点的文件名或机器标识写作 `v04`。

例如 `raw_case_v04.schema.json` 就是 v0.4 case schema。

## 3. 先不要读代码，先看一个输入

打开：

```text
examples/pipeline_manifest.example.json
```

它有两个数组：`papers` 和 `cases`。

### 3.1 `papers` 行

示例：

```json
{
  "paper_id": "P001",
  "doi": "10.0000/synthetic.example",
  "title": "Synthetic molecular photophysics fixture",
  "retrieval_mechanism": "RIM_RIR_RIV",
  "source_md": "fixtures/source.md",
  "source_images": ["fixtures/source_structure.png"]
}
```

字段含义：

- `paper_id`：本次运行内部使用的论文 ID；
- `doi`：论文 DOI；
- `title`：论文标题；
- `retrieval_mechanism`：发现论文时使用的机制线索，不是最终答案；
- `source_md`：解析后的论文文本；
- `source_images`：论文中可能有用的图片。

### 3.2 `cases` 行

示例中的 case 行告诉程序，要从 `P001` 中处理候选 `P001_A`。

默认情况下，Stage 2 中满足自动晋级条件的 `make_case` 和 `human_review`
候选会被转换为确定性的 case 行，并直接进入后续结构身份审核。程序同时写出
`automatic_case_manifest.json`，记录晋级结果和所有跳过原因。manifest 中
仍可提供显式 `cases`；对于同一论文和归一化分子标签，显式 case 优先。

### 3.3 路径如何解析

manifest 中的相对路径，以 manifest 文件所在目录为基准，而不是以终端
当前目录为基准。相关代码在 `pipeline.py` 的 `_resolve()`。

## 4. 推荐的代码阅读顺序

下面不是按文件名排序，而是按“先理解规则，再理解流程”的顺序。

## 4.1 第一组：固定规则

### `vocabulary.py`

先读这个文件，因为它很短。

重点看：

```python
OFFICIAL_MECHANISMS
FINAL_SYNTHESIS_MECHANISM
REFERENCE_STATUSES
REVIEW_DECISIONS
ACCEPTED_REVIEW_DECISIONS
```

你应该得到三个结论：

1. 正式机制家族只有 11 类；
2. `FINAL_EVIDENCE_GROUNDED_DIAGNOSIS` 是综合诊断专用标签，不是第 12 类；
3. 最终可接受审核结果只有 `PASS` 和 `PASS_WITH_CAVEAT`。

### `public_input.py`

重点读：

```python
CANONICAL_SMILES_ONLY_TASK
check_smiles_only_public_input()
```

这个函数逐层检查：

```text
public_input
  -> molecule
    -> structure
      -> format == "smiles"
      -> value == 锁定 SMILES
  -> task == 固定任务文本
```

如果 public input 多出 DOI、名称或答案字段，就会成为 blocker。

### `schemas/raw_case_v04.schema.json`

这个文件不是 Python，而是 JSON Schema。它规定最终 JSON 必须有哪些字段、
字段是什么类型、哪些枚举值允许出现。

第一次不需要逐行读。先搜索这些词：

```text
public_input
hidden_reference
reference_evidence_units
reference_diagnosis_units
additionalProperties
```

`additionalProperties: false` 表示不允许模型随意添加未定义字段。

### `schema.py`

重点读 `validate_raw_case()`。它先调用 JSON Schema，然后补充跨字段检查：

- evidence ID 是否重复；
- diagnosis ID 是否重复；
- diagnosis 引用的 evidence ID 是否存在；
- 最终综合诊断是否恰好出现一次；
- evidence 中的机制链接是否属于正式 11 类。

## 4.2 第二组：程序总入口

### `cli.py`

终端命令首先进入这里。

阅读顺序：

1. `build_parser()`：有哪些命令和参数；
2. `main()`：不同命令分别调用哪个函数；
3. `_client_from_args()`：怎样创建 API 客户端；
4. `_load_release_manifest()`：怎样读取最终打包清单。

命令对应关系：

| 命令 | 用途 | 是否调用模型 |
|---|---|---:|
| `audit-json` | 检查最终 JSON | 否 |
| `verify-pdf` | 核对本地 PDF 身份 | 否 |
| `import-mineru` | 导入 MinerU 解析结果 | 否 |
| `run-pipeline` | 执行 Stage 1--5 | 是 |
| `audit-release` | 数据集级审核与去重 | 否 |
| `package-release` | 打包提交 | 否 |

### `pipeline.py`

这是最重要的总流程文件。先只读公开函数：

```python
run_manifest_pipeline()
validate_pipeline_manifest()
```

`run_manifest_pipeline()` 可以分成两个大循环。

第一个循环处理 `manifest["papers"]`：

```text
run_paper_screen()
    -> run_candidate_screen()
    -> candidate_manifest.json
```

第二个循环处理 `manifest["cases"]`：

```text
run_structure_resolution()
    -> run_reference_construction()
    -> run_independent_review()
    -> NEEDS_MINOR_FIX 时 run_minor_repair()
    -> 修复成功后再次 run_independent_review()
```

不要一开始研究 `_finish()` 和 `_write_json()`。它们只是汇总和写文件。

## 4.3 第三组：Stage 1 和 Stage 2

### `screening.py`

阅读顺序：

1. `ParsedPaper`：论文输入对象；
2. `ScreeningResult`：阶段返回值；
3. `build_paper_screen_prompt()`；
4. `run_paper_screen()`；
5. `build_candidate_screen_prompt()`；
6. `run_candidate_screen()`；
7. `_run_screen()`；
8. 两个 `validate_*` 函数。

`build_*_prompt()` 不再把所有静态规则写死在 Python 中，而是从
`prompts/` 读取版本化模板，再附加本次论文的动态信息。

`_run_screen()` 展示了一个标准模型调用阶段的完整结构：

```text
生成 prompt
    -> 写 request.json 和 request.md
    -> client.complete()
    -> 写 raw_response.txt
    -> parse_json_object()
    -> 本地 validator
    -> 写 result.json 和 response.json
```

这是理解其他模型阶段的最好入口。

### Stage 1 与 Stage 2 的区别

Stage 1 回答：“这篇论文是否适合继续处理？”

Stage 2 回答：“这篇论文中有哪些能够单独对应一个 SMILES 的具体候选？”

Stage 1 不生成 SMILES，Stage 2 也不锁定 SMILES。

## 4.4 第四组：Stage 3 结构确认

### `structure.py`

这是最值得慢慢读的文件。

先看：

```python
StructureTask
StructureResult
run_structure_resolution()
```

`run_structure_resolution()` 的真实顺序是：

```text
模型提出 provisional SMILES
    -> _proposed_smiles()
    -> _validate_render_review()
        -> RDKit 验证和 canonicalization
        -> 渲染 RDKit 二维图
        -> compose_structure_match()
        -> 视觉模型身份审核
    -> 如果失败，最多进行一次 bounded repair
    -> 修复后完整重跑 RDKit、渲染和视觉审核
    -> 只有 confirmed 才写 locked_structure.json
```

重点理解这句方法原则：

```text
RDKit 能解析，不等于 SMILES 就是论文中的目标分子。
```

RDKit 只证明字符串能够表示一个化学结构。视觉身份审核才负责比较它是否
对应论文结构图中的确切目标。

### Stage 3 关键输出

```text
03_structure/
  task.json
  01_proposal/
  02_attempt/
  03_repair/              # 只有需要时出现
  04_repaired_attempt/    # 只有修复后出现
  structure_resolution_summary.json
  locked_structure.json   # 只有确认成功才出现
  structure_match.png     # 只有确认成功才成为最终版本
```

看到 `locked_structure.json` 才表示 Stage 3 真正成功。

### 相关辅助模块

- `chemistry.py`：RDKit 解析、sanitize、canonical SMILES；
- `depiction.py`：生成二维分子图；
- `identity.py`：生成 InChIKey 等数据集级身份键；
- `provider.py`：把文本和图片发送给模型。

## 4.5 第五组：Stage 4 参考答案构建

### `reference.py`

阅读顺序：

1. `ReferenceTask`；
2. `run_reference_construction()`；
3. `build_reference_prompt()`；
4. `_validated_lock()`；
5. `_immutable_and_schema_errors()`；
6. `_valid_delivery()`。

`run_reference_construction()` 先读取并验证 `locked_structure.json`，然后才让
模型生成 case。模型生成后会执行：

```text
schema 和锁定字段检查
    -> local gate
    -> gate 不通过时最多进行一次定向 repair
    -> 再次 schema、锁定字段和 local gate 检查
    -> 通过后写入 delivery/
```

### Stage 4 最重要的不变量

下列内容不能被模型或 repair 改动：

```text
case_id
version
track
public_input
hidden_reference.source_article
locked SMILES
```

### Stage 4 可交付三件套

```text
04_reference/delivery/
  final_reference_alignment.json
  source.md
  structure_match.png
  locked_structure.json
```

前三个文件会进入独立审核。`locked_structure.json` 用于本地锁定和 provenance。

## 4.6 第六组：本地 gate

### `local_gate.py`

这个文件较长，不要从头逐行读。先看入口：

```python
run_local_gate()
```

然后按它调用的检查函数跳转：

- `_check_schema_and_links()`；
- `_check_text_quality()`；
- `_check_cross_candidate_identity()`；
- quote grounding 检查。

报告中有两种问题：

- `blocking_issues`：必须修复，否则不能前进；
- `warnings`：需要注意，但不一定阻断。

当你看到一个 local gate 报告时，先看：

```json
{
  "gate_passed": false,
  "blocking_issue_count": 1,
  "blocking_issues": []
}
```

不要先读完整 Markdown 报告，先根据 `issue_type` 搜索对应检查函数。

## 4.7 第七组：Stage 5 审核和修复

### `review.py`

重点看：

```python
ReviewCase.from_directory()
run_independent_review()
parse_review_decision()
load_valid_review_result()
```

`ReviewCase.from_directory()` 会确认三件套是否存在。

`run_independent_review()` 会记录：

```text
request.json
request.md
raw_response.txt
raw_response.json
review.md
review_summary.json
```

`--resume` 不只是看文件是否存在，而是检查已有审核状态和输入 hash 是否仍然
有效。失败结果不会被误当成成功而跳过。

### `repair.py`

只有 `NEEDS_MINOR_FIX` 可以进入 `run_minor_repair()`。

修复流程：

```text
读取原 JSON、review.md 和 source.md
    -> 模型按审核意见作最小修改
    -> 保护身份字段和 public input
    -> 清除非法内部顶层字段
    -> schema/link 检查
    -> local gate
    -> 必要时进行一次 gate repair
    -> 通过后写 rereview_input/
```

`PASS` 不需要修，`FAIL_OR_REBUILD` 也不会被这个函数自动修。

## 4.8 第八组：数据集审核和打包

### `dataset.py`

重点看：

```python
ReleaseCase
audit_release_cases()
package_accepted_cases()
_duplicates()
```

`audit_release_cases()` 检查：

- 三件套是否存在；
- JSON 是否符合 schema；
- review 是否为可接受结果；
- 归档机制是否属于 11 类；
- SMILES 是否能生成结构身份键；
- JSON DOI 与 `source.md` 是否冲突；
- 是否存在重复结构或同论文同标签。

`package_accepted_cases()` 只有在 audit 无 blocker 时才运行。它生成两部分：

```text
submission_json_N/                    # 只放提交 JSON
internal_provenance_and_reviews_N/    # 放来源、结构图和审核记录
```

输出目录非空时会直接拒绝，避免悄悄覆盖旧提交包。

## 5. 哪些步骤其实不在 `run-pipeline` 内

这是阅读代码时非常重要的一点。

`run-pipeline` 当前要求 manifest 已经提供 `source_md`。也就是说，下列步骤
由独立 CLI 或工具完成，而不是在 `pipeline.py` 中自动串起来：

```text
Tavily/Crossref 文献发现
PDF 下载
PDF 身份核对
MinerU 实际解析
MinerU 结果导入
```

相关代码：

- `literature.py`：检索、DOI、Crossref、PDF 身份和下载工具；
- `parsing.py`：把已有 MinerU export 导入成统一目录；
- `cli.py verify-pdf`；
- `cli.py import-mineru`。

因此，完整方法层面是“文献到 case”，但 `run-pipeline` 命令的直接输入起点
是已经解析好的论文材料。

## 6. 第一次运行：只运行本地测试

在 PowerShell 中执行：

```powershell
cd path\to\aie_ddxbench_construction

$env:PYTHONPATH = (Resolve-Path "src").Path
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:AIE_DDX_RDKIT_CONDA_ENV = "your-rdkit-environment"

python -B -m pytest -q
```

预期结果：

```text
40 passed
```

如果这里失败，不要先调用 API。先解决本地环境或测试问题。

### 6.1 按阶段运行测试

```powershell
python -B -m pytest tests\test_screening.py -vv
python -B -m pytest tests\test_structure.py -vv
python -B -m pytest tests\test_reference.py -vv
python -B -m pytest tests\test_local_gate.py -vv
python -B -m pytest tests\test_review.py -vv
python -B -m pytest tests\test_repair.py -vv
python -B -m pytest tests\test_dataset.py -vv
```

测试使用 fake client 或合成数据，不会调用付费 API。

### 6.2 测试代码应该怎样读

以 `tests/test_structure.py` 为例：

1. 先看 fake client 返回了什么 JSON；
2. 再看测试如何构造 `StructureTask`；
3. 看它调用哪个公开函数；
4. 最后看 `assert` 要求哪些输出必须存在。

测试往往比正式实现更容易说明“输入是什么、正确输出是什么”。

## 7. 第二次运行：不调用 API，检查真实 171 JSON

```powershell
python -B -m aie_ddxbench_construction.cli audit-json `
  --case-root path\to\submission_json `
  --out work\manual_schema_audit.json
```

预期：

```text
file_count: 171
valid_count: 171
invalid_count: 0
```

然后打开：

```text
work/manual_schema_audit.json
```

每一行都有：

```json
{
  "path": "...",
  "valid": true,
  "issues": []
}
```

## 8. 第三次运行：观察 MinerU 导入的输入输出

使用合成 fixture，不涉及真实论文：

```powershell
python -B -m aie_ddxbench_construction.cli import-mineru `
  --export-dir examples\fixtures `
  --out-dir work\manual_mineru_import
```

查看：

```text
work/manual_mineru_import/source.md
work/manual_mineru_import/images/
work/manual_mineru_import/parser_report.json
```

`parser_report.json` 记录输入文件、输出文件和 SHA-256。SHA-256 可以理解成
文件指纹，用来判断内容是否发生变化。

## 9. 第四次运行：只调用一次模型做 Stage 1

先设置 API：

```powershell
$env:OPENAI_API_KEY = "在终端中设置，不写进仓库"
$env:OPENAI_BASE_URL = "你的 OpenAI-compatible API 地址"
```

然后运行：

```powershell
python -B -m aie_ddxbench_construction.cli run-pipeline `
  --manifest examples\pipeline_manifest.example.json `
  --out-root work\manual_pipeline_smoke `
  --provider openai-compatible `
  --model gpt-5.5 `
  --stop-after paper_screen `
  --keep-going
```

合成论文很短，因此模型可能给出 `reject`、`reserve` 或 `needs_review`。这不
代表程序错误。这个 smoke test 的目的只是确认请求、响应和文件写入流程。

## 10. 怎样检查一次模型调用的完整输入输出

打开：

```text
work/manual_pipeline_smoke/papers/P001/01_paper_screen/
```

按下面顺序读：

### `request.md`

这是最终展开后发送给模型的用户 prompt。先确认它包含：

- 固定 Stage 1 规则；
- DOI、标题和检索机制；
- `source.md` 内容。

### `request.json`

这是机器可读请求记录。它还包含：

- prompt 版本；
- provider 名称；
- model 名称；
- source hash；
- 图片名称。

### `raw_response.txt`

这是模型原样返回的文本。如果 JSON 解析失败，先看这里。

### `result.json`

这是成功解析和验证后的结构化结果。如果只有 `raw_response.txt` 而没有
`result.json`，通常表示模型调用成功但输出格式或本地验证失败。

### `response.json`

这里记录请求是否成功、响应模型、usage 和错误信息。API 超时、HTTP 错误
和 JSON 解析错误应优先从这里查看。

## 11. 怎样逐阶段运行

确认 Stage 1 请求链正常后，可以依次使用：

```text
--stop-after paper_screen
--stop-after candidate_screen
--stop-after structure
--stop-after reference
--stop-after review
```

推荐每次使用不同输出目录，避免自己分不清结果：

```text
work/read_test_01_paper
work/read_test_02_candidate
work/read_test_03_structure
work/read_test_04_reference
work/read_test_05_review
```

也可以使用同一目录加 `--resume`。但第一次学习时，分目录更直观。

## 12. `--resume` 和 `--keep-going` 是什么

### `--resume`

表示尝试复用已经成功且仍然有效的结果。

它不是简单地“看到文件就跳过”。程序还会检查状态、hash、schema、锁定
结构或 gate 结果。失败和不完整结果会重试。

### `--keep-going`

表示一个论文或 case 失败后继续处理后面的项目。

不用它时，遇到失败会较早停止，适合调试单个 case。批量运行时通常使用。

## 13. 一次完整运行后目录怎么看

```text
output_root/
  candidate_manifest.json
  pipeline_summary.json
  papers/
    P001/
      01_paper_screen/
      02_candidate_screen/
  cases/
    AIE_DDX_.../
      03_structure/
      04_reference/
        delivery/
      05_review/
      06_minor_repair/    # 需要 minor fix 时出现
      07_rereview/        # 修复后复审时出现
```

第一眼先打开 `pipeline_summary.json`。它告诉你每个项目在哪个 stage 成功或
失败。然后再进入具体 stage 目录。

## 14. 常见故障应该先看哪里

### API 调用失败

看当前 stage 的：

```text
response.json
raw_response.txt
```

检查 provider、model、HTTP 状态、timeout 和 error。

### 模型返回了内容，但程序说 failed

先看 `raw_response.txt`，再看 summary 中的 error。常见原因：

- 不是合法 JSON；
- 缺少必需字段；
- 使用了非法机制名称；
- decision 不在允许枚举中。

### SMILES 失败

看：

```text
03_structure/02_attempt/rdkit_report.json
03_structure/structure_resolution_summary.json
```

如果 RDKit 成功但没有 lock，再看视觉 identity review 和
`structure_match.png`。

### reference 失败

看：

```text
04_reference/reference_construction_summary.json
04_reference/01_draft/
04_reference/02_gate/
04_reference/03_gate_repair/
```

具体编号以实际目录为准。先找 `local_gate_report.json` 中的
`blocking_issues`。

### review 一直重试

看 `review_summary.json` 和 `raw_response.txt`。如果模型没有输出四种合法
decision 之一，`--resume` 会继续重试，而不是把失败结果跳过。

### package-release 拒绝运行

看 `prepackage_audit.json` 的 `blockers`。常见原因：

- review 不是 PASS 类；
- case 缺少三件套；
- schema 不通过；
- archive mechanism 非法；
- exact structure 重复；
- 输出目录非空。

## 15. 使用 VS Code 单步读代码

最简单的方法不是给所有地方打断点，而是只放五个：

1. `cli.py` 的 `main()`；
2. `pipeline.py` 的 `run_manifest_pipeline()`；
3. `screening.py` 的 `_run_screen()`；
4. `structure.py` 的 `run_structure_resolution()`；
5. `reference.py` 的 `run_reference_construction()`。

第一次只运行到 `paper_screen`。当程序停在 `_run_screen()` 时，观察：

```text
prompt
source_path
output_dir
client.model
image_paths
```

然后单步跨过 `client.complete()`，再观察：

```text
response.text
parsed
errors
```

不要进入 OpenAI SDK 内部单步执行，那会看到大量与你的项目无关的代码。

## 16. 阅读 Python 时常见符号

### `@dataclass`

表示这个类主要用于保存一组有名字的数据，例如 `StructureTask`。可以把它
理解成比普通字典更严格的任务表。

### `Path`

表示文件路径。例如：

```python
source = Path("source.md")
source.is_file()
source.read_text()
```

### `dict.get("name")`

安全地读取字典字段。字段不存在时返回 `None` 或给定默认值。

### 函数参数中的 `*`

例如：

```python
def run_x(task, *, output_dir, client):
```

表示 `output_dir` 和 `client` 必须写出参数名，避免调用时顺序混乱。

### 以下划线开头的函数

例如 `_write_json()`，表示它是模块内部辅助函数。第一次阅读优先看不以下划
线开头的公开函数。

### `try` / `except`

表示捕获错误。批处理代码通常把异常写入 summary，然后依据 `keep_going`
决定停止还是继续。

### type hint

例如：

```python
def normalize_doi(value: Any) -> str:
```

表示函数期望返回字符串。它帮助阅读和检查，但不是论文数据本身。

## 17. 推荐的七天阅读计划

不需要真的用七天，可以按七个阶段完成。

### 第一步

读 `vocabulary.py`、`public_input.py` 和一个真实 final JSON。

目标：知道公开输入和隐藏答案分别是什么。

### 第二步

读 `cli.py`、`pipeline.py` 和 example manifest。

目标：能画出主调用链。

### 第三步

读 `screening.py` 和对应 tests。

目标：理解论文筛选与候选分子提取的区别。

### 第四步

读 `structure.py`、`chemistry.py` 和 `test_structure.py`。

目标：理解“化学有效”和“身份正确”为什么是两件事。

### 第五步

读 `reference.py`、schema、`local_gate.py`。

目标：理解 evidence、diagnosis、锁定字段和 blocker。

### 第六步

读 `review.py`、`repair.py` 及其 tests。

目标：理解审核结果、最小修复和复审。

### 第七步

读 `dataset.py`，运行一次 `audit-json` 和合成打包测试。

目标：理解单案例成功为什么还不等于整个数据集可以提交。

## 18. 最后用这张清单检查自己是否读懂

如果你能回答以下问题，就已经掌握主流程：

- retrieval mechanism 为什么不是最终机制标签？
- Stage 1 和 Stage 2 为什么不应该锁定 SMILES？
- RDKit 通过为什么不能证明分子身份正确？
- 什么情况下会生成 `locked_structure.json`？
- reference 生成为什么不能修改锁定 SMILES？
- evidence unit 和 diagnosis unit 如何通过 ID 连接？
- `underdetermined` 为什么仍然可以链接 evidence？
- local gate 和 independent review 有什么区别？
- `PASS_WITH_CAVEAT` 为什么可以进入最终候选？
- `NEEDS_MINOR_FIX` 修复后为什么必须重新审核？
- `--resume` 为什么不能只检查文件是否存在？
- 为什么最终还要执行数据集级去重？
- JSON-only 提交目录和 internal provenance 目录分别放什么？

## 19. 最推荐的实际学习方法

不要只读，也不要只跑。对每个阶段都完成下面四步：

```text
看输入对象
    -> 看展开后的 request
    -> 看 raw response
    -> 看本地检查后的正式输出
```

始终沿着同一个合成 case 或一个真实 case 追踪，比同时浏览几十个文件更
容易建立整体理解。遇到不明白的字段，先在 schema 中搜索，再在生成 prompt
和 validator 中搜索，最后才去看历史代码。
