# AIE-DDxBench Raw-Case Construction

This repository contains the final code used to construct paper-derived
AIE-DDxBench raw cases. The public interface is a single manifest-driven
pipeline that starts from either a local main-article PDF or an existing MinerU
export and produces reviewed JSON cases with retained intermediate artifacts.

Literature discovery and lawful PDF acquisition are upstream activities. The
repository does not include article PDFs, API credentials, or historical model
responses.

## Pipeline

The pipeline performs the following stages:

1. Parse a local PDF through the MinerU VLM API, or import existing MinerU
   Markdown and image artifacts.
2. Screen the paper and extract molecule-level candidates.
3. Propose candidate SMILES, validate and canonicalize them with RDKit, render
   two-dimensional depictions, and review molecular identity against source
   structure images.
4. Construct source-grounded evidence units, mechanism diagnosis units, and a
   final synthesis around the locked molecular structure.
5. Run deterministic validation, independent review, and bounded minor repair
   when required.

Only a confirmed molecular identity can create a locked structure. Reference
construction and repair must preserve the locked SMILES.

## Installation

The reference environment uses Python 3.10 and RDKit 2022.09.5.

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

`MINERU_API_TOKEN` is required only when a manifest uses `source_pdf`. It is not
required when the manifest points to an existing `source_md` and image
directory. `.env.example` lists supported variable names but is not loaded
automatically.

## Manifest

Copy `examples/pipeline_manifest.example.json` and replace the DOI, title,
retrieval mechanism, and local PDF path. The retrieval mechanism is only a
screening hypothesis; it is not used as the final diagnosis.

For an existing MinerU export, replace `source_pdf` with:

```json
"source_md": "path/to/source.md",
"source_image_dir": "path/to/images"
```

Keep `cases` empty to allow eligible molecule candidates to be promoted
automatically.

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
resolution, reference construction, review, and repair artifacts. A case that
passes without repair writes its final JSON to:

```text
work/batch_001/cases/<case_id>/04_reference/delivery/final_reference_alignment.json
```

Cases that require a minor repair are revalidated and rereviewed under the
later repair and review directories. `pipeline_summary.json`,
`candidate_manifest.json`, and `automatic_case_manifest.json` summarize the
batch.

`--resume` reuses only outputs whose recorded hashes and validation state remain
valid. `--keep-going` allows later papers or cases to continue after an isolated
failure.

## Runtime Assets

The package includes the versioned prompts, 11 mechanism profiles, and the v0.4
raw-case schema required by the pipeline. These files are runtime assets and
must remain installed with the Python package.

## Scope

- RDKit validity is necessary but does not establish molecular identity.
- MinerU parsing can omit or reorder source content.
- Visual model review supports identity auditing but does not replace expert
  inspection for unresolved structures.
- The package implements the final documented workflow for future cases. It
  does not claim byte-for-byte reproduction of every historical request.
