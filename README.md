# AIE-DDxBench Raw-Case Construction

This repository contains the final code used to construct paper-derived
AIE-DDxBench raw cases. The public interface is a single manifest-driven
pipeline that starts from a local main-article PDF and produces reviewed JSON
cases with retained intermediate artifacts.

## Pipeline

The pipeline performs the following stages:

1. Parse a local PDF through the MinerU VLM API.
2. Screen the paper and extract molecule-level candidates.
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
conda activate aie-ddxbench-construction
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

## Manifest

Copy `examples/pipeline_manifest.example.json` and replace the DOI, title,
retrieval mechanism, and local PDF path. The retrieval mechanism is only a
screening hypothesis; it is not used as the final diagnosis. Eligible cases
are generated automatically from candidates that pass screening.

## Run

Use the supplied PowerShell template:

```powershell
.\examples\run_pipeline.template.ps1 `
  -Manifest examples\pipeline_manifest.example.json `
  -OutputRoot work\batch_001 `
  -Model your-model-id `
  -BaseUrl https://your-provider.example/v1 `
  -ApiKeyEnvironment OPENAI_API_KEY `
  -ApiProtocol responses
```

The equivalent direct command is:

```powershell
aie-ddxbench run-pipeline `
  --manifest examples\pipeline_manifest.example.json `
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

## Outputs

The output root retains paper-level screening, candidate extraction, structure
resolution, reference construction, review, correction, and final JSON
artifacts. `pipeline_summary.json`, `candidate_manifest.json`, and
`automatic_case_manifest.json` summarize the batch.

`--resume` reuses only outputs whose recorded hashes and validation state remain
valid. `--keep-going` allows later papers or cases to continue after an isolated
failure.

## Runtime Assets

The package includes the versioned prompts, 11 mechanism profiles, and the v0.4
raw-case schema required by the pipeline. These files are runtime assets and
must remain installed with the Python package.
