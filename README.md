# PhotoMechBench Raw-Case Construction

This repository contains the final code used to construct paper-derived
PhotoMechBench raw cases. The public interface is a single automated pipeline
that starts from one local main-article PDF or a directory of PDFs and produces
reviewed JSON cases with retained intermediate artifacts. Users do not prepare
paper manifests or mechanism labels.

## Pipeline

The pipeline performs the following stages:

1. Discover PDFs recursively and parse each paper through the MinerU VLM API.
2. Recover source metadata, screen each paper without a preset mechanism label,
   and extract molecule-level candidates.
3. Retain candidates that pass molecule-level eligibility checks, then propose
   and validate their SMILES with RDKit and review molecular identity against
   source structure images. Candidates that fail these checks are excluded.
4. Construct source-grounded evidence units, mechanism diagnosis units, and a
   final synthesis around the locked molecular structure.
5. Run validation, independent review, and correction when required.

## Installation

The reference environment uses Python 3.10 and RDKit.

```powershell
conda env create -f environment.yml
conda activate photomechbench-construction
```

## Credentials

Set credentials outside the repository. The model endpoint must support an
OpenAI-compatible API.

```powershell
$env:OPENAI_API_KEY = "<your-model-api-key>"
$env:OPENAI_BASE_URL = "https://your-provider.example/v1"
$env:MINERU_API_TOKEN = "<your-mineru-token>"
```

`MINERU_API_TOKEN` is required to parse the input PDF. `.env.example` lists
supported variable names but is not loaded automatically.

## Run

Use the supplied PowerShell template:

```powershell
.\examples\run_pipeline.template.ps1 `
  -InputPath input `
  -OutputRoot work\batch_001 `
  -Model your-model-id `
  -BaseUrl https://your-provider.example/v1 `
  -ApiKeyEnvironment OPENAI_API_KEY `
  -ApiProtocol responses
```

The equivalent direct command is:

```powershell
photomechbench run-pipeline `
  --input input `
  --out-root work\batch_001 `
  --provider openai-compatible `
  --model your-model-id `
  --base-url https://your-provider.example/v1 `
  --api-key-env OPENAI_API_KEY `
  --api-protocol responses `
  --resume `
  --keep-going
```

Provider names, endpoints, model IDs, and credential variable names are
deployment settings. They are not fixed by the repository.

When `--input` is a directory, all PDF files below it are discovered
recursively. Byte-identical duplicate PDFs are processed once. Paper DOI,
title, and mechanism-discovery context are recovered after MinerU parsing and
saved in the generated internal manifest. The input should contain main-article
PDFs only; separate Supporting Information PDFs are not automatically merged
with a main article.

## Outputs

The output root retains paper-level screening, candidate extraction, structure
resolution, reference construction, review, correction, and final JSON
artifacts. `discovered_pdf_inputs.json` and `internal_paper_manifest.json` are
generated automatically for traceability. `pipeline_summary.json`,
`candidate_manifest.json`, `automatic_case_manifest.json`, and
`final_duplicate_report.json` summarize the batch. Cases accepted by
independent review and the exact final identity check are collected under
`final_json/`.
The pipeline summary separately reports technical failures and candidate cases
that did not reach an accepted final review decision.

`--resume` reuses only outputs whose recorded hashes and validation state remain
valid. `--keep-going` allows later papers or cases to continue after an isolated
failure.

## Runtime Assets

The package includes the versioned prompts and v0.4 raw-case schema required by
the pipeline. These files are runtime assets and must remain installed with the
Python package.

Existing `AIE_DDX_*` case identifiers remain unchanged so that previously
constructed cases and review artifacts stay compatible with the renamed
benchmark.
