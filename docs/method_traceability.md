# Appendix Method-to-Code Traceability

| Appendix method statement | Final module or asset | Why it supports the statement |
|---|---|---|
| Mechanism-oriented queries retrieve candidate literature; retrieval labels are not final diagnoses. | `literature.py`, `profiles/*.json`, `prompts/paper_screen_v1.md` | Search hits retain a retrieval mechanism as provenance, while both screening prompts explicitly treat it as a hypothesis. |
| DOI records are normalized, deduplicated, supplemented through Crossref, and checked against local PDFs. | `literature.py` | Pure DOI normalization, visible-DOI grouping, title matching, targeted Crossref search, and PDF identity classification are separate functions. |
| Verified PDFs are converted by MinerU and source artifacts are retained. | `mineru_api.py`, `parsing.py` | The cloud adapter invokes MinerU Precision Extract with `model="vlm"`, saves the raw API export, and imports it into canonical `source.md`, image, catalog, and hash records. Existing MinerU exports remain supported. |
| Papers are screened before molecule candidates are extracted. | `screening.py`, `prompts/paper_screen_v1.md`, `prompts/candidate_screen_v1.md` | The pipeline runs paper screening first and only then identifies concrete molecule-like candidate units. |
| The model proposes, rather than confirms, a candidate SMILES. | `structure.py`, `prompts/smiles_proposal_v1.md` | Proposals cannot create a lock until deterministic chemistry and visual identity checks pass. |
| RDKit parses, sanitizes, canonicalizes, and renders the candidate. | `chemistry.py`, `depiction.py` | Both current-Python and configured external/conda RDKit runtimes are supported and recorded. |
| The RDKit depiction is compared with a source-paper molecular figure. | `structure.py`, `prompts/structure_identity_review_v1.md` | `compose_structure_match` creates the side-by-side artifact and the visual reviewer checks target identity and analogue confusion. |
| Failed structures receive bounded repair and full revalidation. | `structure.py`, `prompts/smiles_repair_v1.md` | One repair is permitted; repaired output reruns RDKit, rendering, and visual review. |
| Confirmed SMILES are locked before reference construction. | `structure.py`, `reference.py` | Only explicit confirmed identity writes `locked_structure.json`; Stage 4 validates and preserves this lock. |
| Hidden references contain source metadata, evidence units, diagnosis units, and final synthesis. | `reference.py`, `prompts/reference_construction_v1.md`, `schemas/raw_case_v04.schema.json` | The prompt defines the semantic contract and the schema plus cross-field checks enforce it. |
| Quotations and evidence links are checked locally. | `grounding.py`, `local_gate.py`, `schema.py` | Missing exact source quotations, unknown evidence IDs, invalid mechanism labels, and malformed public input block progression. |
| An independent model audits only the case JSON, source, and structure image. | `review.py`, `prompting.py`, `prompts/independent_review_v1.md` | The request constructor accepts exactly these three artifacts and explicitly disables browsing or outside knowledge. |
| Minor fixes preserve identity and are rechecked. | `repair.py`, `prompts/minor_repair_v1.md`, `prompts/gate_repair_v1.md` | Protected fields and source metadata cannot change; schema and local gate rerun before packaging for re-review. |
| Final cases pass review, identity, and duplicate checks. | `dataset.py` | Packaging accepts only `PASS` or `PASS_WITH_CAVEAT`, computes RDKit identity keys, reports duplicate groups, and blocks invalid releases. |
| Batch execution supports selected stages, resume, and failure isolation. | `pipeline.py`, `cli.py` | Manifest stages are explicit; hash-valid outputs are reused and failed items remain retryable. |

## Historical Compatibility Boundary

The final package consolidates the strongest verified logic that is compatible with accepted-case provenance. It does not claim that every historical batch used identical prompt wording, provider configuration, or directory layout. The frozen 171 cases are regression inputs only and are not rewritten.
