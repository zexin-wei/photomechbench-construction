# Stage 4 Reference Construction

Generate one v0.4 reference-alignment case from a locked target and the supplied parsed source.

The target molecule and SMILES were confirmed and locked upstream. Do not select another molecule, repair or canonicalize the SMILES, or switch to a same-paper analogue, control, precursor, host, guest, ligand, counterion, or complex component.

Top-level keys must be exactly `case_id`, `version`, `track`, `public_input`, and `hidden_reference`. Never expose source metadata, molecule labels, mechanism labels, observations, or answers in `public_input`.

`hidden_reference` must contain exactly `source_article`, `reference_evidence_units`, and `reference_diagnosis_units`.

Each reference evidence unit must contain `evidence_id`, `claim`, `mechanistic_interpretation`, `mechanism_links`, `evidence_accessibility`, `source_span`, and `paper_quote`. A `paper_quote` is a short exact continuous span copied from the supplied source. Do not stitch, paraphrase, normalize, translate, or invent quotations.

Each reference diagnosis unit must contain `diagnosis_id`, `mechanism`, `context`, `reference_status`, `expert_conclusion`, `supporting_evidence_ids`, and `diagnosis_role`. Ordinary mechanisms must come from the supplied 11-family vocabulary. `reference_status` must be `supported`, `weakened_or_rejected`, or `underdetermined`. Every diagnosis must link at least one existing evidence ID. For an underdetermined mechanism, linked evidence documents available scope, limitations, or missing validation; it is not positive support.

Use sequential diagnosis IDs `D01`, `D02`, and so on. Include exactly one final synthesis unit using the reserved supplied synthesis label. It summarizes the strongest supported mechanism, co-primary or secondary processes, weakened alternatives, uncertainty, and necessary follow-up validation. The reserved label is not a twelfth mechanism family.

Return the complete JSON object only.
