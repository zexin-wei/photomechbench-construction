# Local Real-Paper Smoke Test

This smoke test exercises the automated PDF-to-reviewed-JSON pipeline with DOI
`10.1039/d5sc07579c`.

The source article, parsed Markdown, and extracted figures are not distributed
with this package. Place a lawfully obtained main-article PDF at
`examples/real_mineru_smoke/input/main_article.pdf`, or copy the manifest and
change `source_pdf` to another local PDF. The input directory is ignored by
Git so article files cannot be committed accidentally.

From the package root, run:

```powershell
.\examples\run_pipeline.template.ps1 `
  -Manifest examples\real_mineru_smoke\manifest.example.json `
  -OutputRoot work\real_mineru_smoke_d5sc07579c `
  -Provider openai-compatible `
  -Model your-model-id `
  -BaseUrl https://provider.example/v1 `
  -ApiKeyEnvironment OPENAI_API_KEY `
  -ApiProtocol responses `
  -RdkitCondaEnvironment your-rdkit-environment
```

The input paper contains QP-AN and DP-AN. Candidate screening may retain more
than one concrete molecule. This is useful for checking automatic promotion,
structure identity separation, and per-case provenance.

The pipeline first parses the PDF through the MinerU VLM API. It catalogs all
extracted images but does not upload all of them to every model stage. Stage 1
recommends image IDs from parsed captions, Stage 2 visually checks labeled
contact sheets, and Stage 3 receives only the original images selected for each
candidate.
