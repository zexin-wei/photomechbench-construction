# AIE-DDxBench Raw-Case Construction

This is the canonical final code release for constructing and auditing
paper-derived AIE-DDxBench raw cases. It accepts either existing MinerU exports
or local main-article PDFs parsed through the MinerU Precision Extract VLM API.
Literature discovery and PDF acquisition remain upstream activities. Historical
directories are not runtime dependencies, and the confirmed 171 cases are
never modified by this package.

## Workflow

1. Import an existing MinerU export as canonical Markdown and image artifacts.
2. Catalog parsed figures, use Stage 1 caption analysis to recommend likely
   structure images, and use Stage 2 visual inspection to select images for
   each concrete molecule-level candidate.
3. Automatically promote concrete `make_case` and `human_review` candidates into structure resolution and record why other candidates are not promoted.
4. Propose a SMILES, validate and canonicalize it with RDKit, render it, compare it with source-paper structure evidence, and lock only confirmed identities.
5. Construct source-grounded evidence and diagnosis units around the locked target.
6. Run deterministic validation, independent three-artifact review, and bounded minor repair when required.
7. Audit identity and duplicates, then package accepted cases into JSON-only and internal-provenance sections.

## Invariants

- A retrieval mechanism is a discovery hint, not a final diagnosis.
- Stage 1 does not generate SMILES; Stage 2 does not finalize them.
- RDKit validity is necessary but is not proof of molecular identity.
- Only `confirmed_match` creates `locked_structure.json`.
- Reference generation and repair preserve the locked SMILES exactly.
- Evidence quotations must occur in the parsed source.
- Ordinary diagnosis mechanisms belong to the fixed 11-family vocabulary.
- `FINAL_EVIDENCE_GROUNDED_DIAGNOSIS` is a reserved synthesis label, not a twelfth family.
- Independent review receives only `final_reference_alignment.json`, `source.md`, and `structure_match.png`.
- Only `PASS` and non-blocking `PASS_WITH_CAVEAT` cases are eligible for release.

## Installation

The reference environment uses Python 3.10 and RDKit 2022.09.5.

```powershell
conda env create -f environment.yml
conda activate aie-ddxbench-construction
```

For development in an existing Python environment:

```powershell
python -m pip install -e ".[test]"
```

### Fresh-Clone Verification

After cloning the repository into a new directory, run the following commands
from the repository root. These checks do not call a model API:

```powershell
conda env create -f environment.yml
conda activate aie-ddxbench-construction
python -m pytest -q
aie-ddxbench --help
aie-ddxbench audit-json `
  --case-root tests\fixtures\valid_case.json `
  --out work\fresh_clone_schema_audit.json
```

The expected test result for release `0.1.0` is `52 passed`. The schema smoke
test should report one valid file and no invalid files. Model-dependent and
MinerU API tests require credentials supplied through environment variables.

If RDKit is installed in another environment, set one of:

```powershell
$env:AIE_DDX_RDKIT_CONDA_ENV = "your-rdkit-environment"
$env:AIE_DDX_RDKIT_PYTHON = "C:\path\to\rdkit-python.exe"
```

These settings are optional. They are only needed when the active Python
environment cannot import RDKit and an existing external RDKit runtime should
be reused.

Model-dependent commands use an OpenAI-compatible API but have no provider-specific endpoint or credential default:

```powershell
$env:OPENAI_API_KEY = "<set outside the repository>"
$env:OPENAI_BASE_URL = "https://provider.example/v1"
```

See `.env.example` for variable names only.

## Ready-to-Use Examples

The release includes four user-facing starting points:

- `examples/run_pipeline.template.ps1`: a provider-configurable PowerShell
  command template for the complete automated pipeline.
- `examples/mineru_paper_manifest.example.json`: a paper-only manifest template
  for an imported MinerU export. Its `cases` array is intentionally empty so
  eligible molecule candidates are promoted automatically.
- `examples/mineru_vlm_pdf_manifest.example.json`: a paper-only manifest that
  starts from a local PDF and invokes the MinerU VLM API automatically.
- `examples/pipeline_manifest.example.json`: a runnable, redistributable
  synthetic manifest with local fixture files. It is intended for interface and
  plumbing checks, not scientific validation.
- `examples/real_mineru_smoke/`: a local real-paper smoke-test manifest and
  instructions that start from a user-supplied PDF. Article content is not
  included.

Copy `.env.example` to a local environment file only if the user's shell or
environment manager loads it. The CLI does not load `.env` files implicitly;
the selected API key variable must be present in the process or user
environment.

After installation, the generic command template can be invoked as follows:

```powershell
.\examples\run_pipeline.template.ps1 `
  -Manifest path\to\pipeline_manifest.json `
  -OutputRoot work\batch_001 `
  -Provider openai-compatible `
  -Model your-model-id `
  -BaseUrl https://provider.example/v1 `
  -ApiKeyEnvironment OPENAI_API_KEY `
  -ApiProtocol responses `
  -RdkitCondaEnvironment your-rdkit-environment
```

Provider names, endpoints, models, API-key variable names, and RDKit runtime
names are deployment settings rather than fixed pipeline values.

## MinerU VLM API

The integrated cloud adapter uses the official `mineru-open-sdk` Precision
Extract API with `model="vlm"`. Set the token outside the repository:

```powershell
$env:MINERU_API_TOKEN = [Environment]::GetEnvironmentVariable(
  "MINERU_API_TOKEN",
  "User"
)
```

Parse one PDF without running the benchmark stages:

```powershell
aie-ddxbench parse-mineru-vlm `
  --pdf path\to\main_article.pdf `
  --out-dir work\papers\P001\parsed `
  --language en `
  --timeout 1800 `
  --resume
```

The command writes the untouched API export under a unique `api_export_*`
directory and creates the canonical `source.md`, `images/`,
`image_catalog.json`, `parser_report.json`, `mineru_api_request.json`, and
`mineru_api_report.json`. The API token is never written to these records.

For a fully integrated PDF-to-case run, use `source_pdf` instead of `source_md`
in the paper row, as shown in
`examples/mineru_vlm_pdf_manifest.example.json`, then run the ordinary pipeline
command. `run-pipeline` reads `MINERU_API_TOKEN`, requests the VLM parser, and
continues through image selection and Stage 1--5 automatically:

```powershell
aie-ddxbench run-pipeline `
  --manifest examples\mineru_vlm_pdf_manifest.example.json `
  --out-root work\pdf_to_cases `
  --provider openai-compatible `
  --model your-model-id `
  --base-url https://provider.example/v1 `
  --api-key-env OPENAI_API_KEY `
  --api-protocol responses `
  --mineru-token-env MINERU_API_TOKEN `
  --mineru-language en `
  --mineru-timeout 1800 `
  --resume `
  --keep-going
```

Use `--mineru-ocr` for scanned documents. Formula and table recognition remain
enabled unless `--mineru-no-formula` or `--mineru-no-table` is supplied.

## Existing MinerU Export Contract

MinerU is an external parsing dependency. Export a paper with MinerU, then import the existing client export:

```powershell
aie-ddxbench import-mineru `
  --export-dir path\to\mineru_export `
  --out-dir work\papers\P001\parsed
```

The importer selects the largest Markdown file as `source.md`, copies available
PNG/JPEG/WebP images, and records hashes in `parser_report.json`. It also writes
`image_catalog.json`, which assigns stable image IDs and captures nearby caption
context. It does not redistribute the original article.

## MinerU-to-JSON Workflow

The default workflow is fully automated after the MinerU import. A Stage 2
candidate is promoted when it has `case_decision=make_case` or `human_review`, a
concrete molecule-level unit type, a non-empty molecule label, and at least one
valid official mechanism assignment. A `human_review` candidate is therefore
routed automatically to the stricter structure-resolution stage rather than
waiting for manual intervention. Structure identity confirmation remains a
blocking requirement.

First, import the MinerU export:

```powershell
aie-ddxbench import-mineru `
  --export-dir path\to\mineru_export `
  --out-dir work\papers\P001\parsed
```

Copy `examples/mineru_paper_manifest.example.json` and create a paper-phase
manifest with the imported `source.md`, imported image directory, verified DOI and title,
and an empty `cases` array. Relative paths are resolved from the manifest's own
directory. Then run the complete pipeline:

```powershell
aie-ddxbench run-pipeline `
  --manifest work\pipeline_manifest.json `
  --out-root work\batch_001 `
  --provider openai-compatible `
  --model your-model-id `
  --base-url https://provider.example/v1 `
  --api-key-env OPENAI_API_KEY `
  --api-protocol responses `
  --resume `
  --keep-going
```

The pipeline writes `candidate_manifest.json` and
`automatic_case_manifest.json`, then continues directly through structure
resolution, reference construction, independent review, and eligible minor
repair. The automatic manifest records both promoted candidates and skipped
candidates with machine-readable reasons.

For each paper, `00_image_catalog/image_catalog.json` records all available
images. Stage 1 reads their captions and recommends IDs. Stage 2 receives
labeled contact sheets for those recommendations and returns candidate-specific
`structure_image_ids`. Only the corresponding original image files are passed
to Stage 3. If Stage 1 returns no valid recommendation, the first 12 cataloged
images are shown to Stage 2 as a documented fallback.

For a case that passes without repair, the constructed JSON is written to:

```text
work/batch_001/cases/<case_id>/04_reference/delivery/final_reference_alignment.json
```

Cases with `NEEDS_MINOR_FIX` are repaired, locally validated, and reviewed again
under `06_minor_repair` and `07_rereview`. Only a final `PASS` or non-blocking
`PASS_WITH_CAVEAT` result is eligible for release packaging.

## Local Checks

Verify that a local PDF is a readable main-article candidate for the expected record:

```powershell
aie-ddxbench verify-pdf `
  --pdf path\to\paper.pdf `
  --doi 10.xxxx/example `
  --title "Expected title" `
  --out work\pdf_identity.json
```

Validate a directory of final v0.4 JSON files without API access:

```powershell
aie-ddxbench audit-json `
  --case-root path\to\submission_json `
  --out work\schema_audit.json
```

## Minimal Model-Dependent Example

The example manifest is synthetic and contains no copyrighted full paper. Supply local fixture paths, then stop after paper screening:

```powershell
aie-ddxbench run-pipeline `
  --manifest examples\pipeline_manifest.example.json `
  --out-root work\example `
  --model your-model-id `
  --stop-after paper_screen
```

## Full Automated Batch

```powershell
aie-ddxbench run-pipeline `
  --manifest path\to\pipeline_manifest.json `
  --out-root work\batch_001 `
  --provider openai-compatible `
  --model your-model-id `
  --base-url https://provider.example/v1 `
  --timeout 240 `
  --max-retries 2 `
  --keep-going
```

The manifest has a paper phase and a case phase. By default, eligible Stage 2 `make_case` units are converted into deterministic case rows automatically. Explicit `cases` rows remain supported and take precedence for the same paper and normalized molecule label.

## Resume

```powershell
aie-ddxbench run-pipeline `
  --manifest path\to\pipeline_manifest.json `
  --out-root work\batch_001 `
  --model your-model-id `
  --resume `
  --keep-going
```

Resume skips only outputs whose recorded status, hashes, schema, locked structure, and gate result remain valid. Failed or incomplete items are retried.

## Release Audit and Packaging

Prepare a release manifest using `examples/release_manifest.example.json` as the shape.

```powershell
aie-ddxbench audit-release `
  --manifest path\to\release_manifest.json `
  --out work\release_audit.json

aie-ddxbench package-release `
  --manifest path\to\release_manifest.json `
  --out-dir release\aie_ddxbench_cases
```

Packaging fails on schema, artifact, review, molecular-identity, or blocking duplicate issues. It creates:

```text
submission_json_N/<mechanism>/<case_id>.json
internal_provenance_and_reviews_N/
  cases/<mechanism>/<case_id>/
  stage5_reviews/<mechanism>/<case_id>/
  release_manifest.json
  identity_duplicate_audit.json
```

The output directory must be empty. Existing releases are never silently overwritten.

## Independent Review

Run the English three-artifact reviewer on one or more explicit case directories:

```powershell
aie-ddxbench review-cases `
  --case-dir path\to\MECHANISM\CASE_001 `
  --case-dir path\to\MECHANISM\CASE_002 `
  --out-root work\independent_review `
  --model your-model-id `
  --api-protocol responses `
  --max-output-tokens 8192 `
  --keep-going
```

Each case directory must contain `final_reference_alignment.json`, `source.md`,
and `structure_match.png`. The command records the expanded English request,
the raw response, the parsed decision, input hashes, and a batch summary.
Use `--api-protocol responses` for endpoints whose selected model does not
support Chat Completions.

## Tests

```powershell
python -m pytest -q
```

## Prompt and Schema Assets

All stable model policies are versioned under `src/aie_ddxbench_construction/prompts/`. Every request records the prompt version and expanded request. The v0.4 schema is `src/aie_ddxbench_construction/schemas/raw_case_v04.schema.json`. Mechanism search profiles are under `profiles/`.

Three independent version domains are used:

- Package releases use semantic versions such as `0.1.0` in `pyproject.toml`.
- Raw-case JSON stores schema version `"0.4"`; prose uses `v0.4`, and filenames
  or identifiers use `v04` when a decimal is unsuitable.
- Prompt assets use local template versions such as `paper_screen_v1`.

These version domains must not be substituted for one another.

## Scope and Limitations

- Search APIs and Crossref are discovery tools; their mechanism buckets are not annotations.
- Publisher access and PDF redistribution rights vary. Main PDFs must be obtained lawfully and are not included here.
- MinerU parsing may omit or reorder figure/table content; uncertain papers are routed to review.
- Visual model review supports identity auditing but does not replace expert inspection for ambiguous structures.
- This package reproduces the documented control flow for future cases. It does not claim byte-for-byte reproduction of every historical request or response.

## Method Traceability

- Final appendix-to-code map: `docs/method_traceability.md`
- Local release acceptance record: `docs/release_acceptance.md`
- Beginner-oriented Chinese code-reading guide: `docs/code_reading_guide_zh.md`
