# Release Acceptance Record

## Verified locally

- A fresh `aie-ddxbench-construction` conda environment was created from
  `environment.yml` with Python 3.10.20 and RDKit 2022.09.5.
- 52 automated tests passed in both the project virtual environment and the
  conda release environment.
- 45 Python source and test files passed AST parsing.
- The command-line interface loaded and exposed all nine public commands.
- All 171 frozen submission JSON files passed the final v0.4 schema and
  cross-field validator (`171 valid, 0 invalid`).
- The release tree contained no private endpoint, provider-specific endpoint,
  machine-specific project path, financial-record term, API key, or bearer-token
  match under the release security patterns.
- The synthetic MinerU-import fixture and two-part release packager passed
  provider-free tests.
- Stable model instructions are stored as versioned prompt assets; Python
  builders append only run-specific context.
- A wheel was built successfully and installed into a separate clean virtual
  environment. It contains all 11 mechanism profiles, all 10 versioned model
  prompts, the prompt documentation, and the v0.4 schema.
- The installed wheel completed CLI loading, resource checks, and a
  provider-free `audit-json` smoke test (`1 valid, 0 invalid`).

## Deliberately not claimed

- No paid model API was invoked solely for release acceptance.
- On this Windows installation, importing the in-process RDKit drawing module
  can emit a DLL loading warning. The configured isolated RDKit runtime path
  remains covered by the passing test suite.
- The package reproduces the final documented method for future construction;
  it does not claim byte-for-byte replay of every historical request.
- The frozen 171-case directory is untracked by Git, so Git cannot provide a
  before-and-after tree proof. The release workflow treated it as a read-only
  regression input and wrote the audit report elsewhere.

The machine-readable 171-case schema report was retained with the internal
release records and is not distributed with this source package.
