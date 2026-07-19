# AIE-DDxBench Independent Reference-Alignment Review

Review only the three artifacts supplied in the current request. Do not browse, use remembered facts, consult prior conversations, or regenerate the case JSON.

The request provides:

1. `final_reference_alignment.json`: the candidate raw case;
2. `source.md`: the parsed source article;
3. `structure_match.png`: the source-paper structure evidence beside the RDKit depiction of the candidate SMILES.

Your task is to determine whether the candidate JSON is suitable as an AIE-DDxBench reference answer. The review concerns scientific correctness, molecular identity, source grounding, mechanism coverage, and internal consistency. It does not assess whether the hidden answer could be inferred from SMILES alone.

Use only facts present in the three artifacts. If an item cannot be verified, mark it `unclear`, `unverifiable`, or `UNVERIFIABLE` as appropriate. Do not reveal chain-of-thought. Return only the completed review template.

## 0. Canonical mechanism vocabulary

Ordinary `reference_diagnosis_units[].mechanism` values and core `mechanism_links` must use one of these 11 mechanism families:

```text
AGGREGATE_EXCITON_EXCIMER
ESIPT_PT
HOST_GUEST_INTERACTION
ICT_TICT_CT
PACKING_HOST_MATRIX_CONFINEMENT
PET_ET
RACI_CI_ACCESS
RADIATIVE_RATE_STATE_BALANCE
RIM_RIR_RIV
SOKR_ANTI_KASHA
TRIPLET_METAL_ENERGY_TRANSFER
```

The reserved label below is permitted only for the integrated final synthesis:

```text
FINAL_EVIDENCE_GROUNDED_DIAGNOSIS
```

Subtype terms such as TICT, RIR, TADF, RTP, TTA, J-aggregate, excimer, and PET belong in context, conclusions, or notes when a canonical family is required. A source-supported mechanism outside the 11-family vocabulary must be described as out of scope rather than forced into an incorrect family. Do not mark an out-of-scope mechanism as rejected merely because it is outside the vocabulary.

If the source's central mechanism is outside the vocabulary and no in-scope primary or co-primary mechanism is adequately supported, the case is not usable for the current benchmark and should receive `CASE_NOT_USABLE` and `REBUILD_OR_DROP`. An out-of-scope secondary context does not invalidate an otherwise well-grounded in-scope case.

## 0A. Evidence boundaries for the 11 families

Use the following boundaries to identify overclaiming, omission, or misclassification.

### `AGGREGATE_EXCITON_EXCIMER`

Covers aggregate excitons, excimer or aggregate emission, J/H aggregation, excitonic coupling, and aggregation-induced new emissive states. Aggregation, concentration increase, solid-state emission change, red shift, or a new band alone does not establish this family. Stronger support normally requires a state assignment plus concentration dependence, excitation spectra, lifetime or kinetic evidence, close packing, or calculations.

### `ESIPT_PT`

Covers excited-state proton transfer, tautomeric emission, and enol/keto proton-transfer pathways. Dual emission, a large Stokes shift, hydrogen bonding, or solvent response is suggestive but not conclusive. Strong support normally requires tautomer or proton-transfer-state assignment, isotope effects, structural blocking, time-resolved evidence, or an excited-state potential-energy surface.

### `HOST_GUEST_INTERACTION`

Covers host-guest binding, inclusion, association, recognition, or supramolecular complexation that changes emission. Evidence must support both complex formation and a connection between binding and the photophysical change. Simple mixing, doping, matrix restriction, or brightening after host addition is insufficient.

### `ICT_TICT_CT`

Covers intramolecular charge transfer, TICT, competition between local and charge-transfer states, polarity-dependent emission, and donor-acceptor torsion. A donor-acceptor structure or solvent-polarity response may support general ICT/CT but does not by itself establish TICT. TICT requires evidence for torsion, rotational freedom, or a twisted-state assignment. PET, ESIPT, and generic aggregate emission must not be relabeled as ICT without support.

### `PACKING_HOST_MATRIX_CONFINEMENT`

Covers crystal packing, host or matrix effects, rigid environments, confinement, and related environmental control of emission. The source must connect a specific phase, packing arrangement, host, matrix, cavity, loading, or rigid environment to the photophysical change. Oxygen sensitivity, aggregation enhancement, or RIM alone is insufficient.

### `PET_ET`

Covers photoinduced electron transfer, electron or hole transfer, charge-separated states, and redox-controlled quenching or recovery. Generic fluorescence quenching, donor-acceptor structure, CT character, or electron-density redistribution alone is insufficient. Strong support normally identifies transfer direction or redox feasibility and may include radical ions, transient signals, lifetime changes, structural controls, or gated recovery. Do not confuse electron transfer with emissive ICT or energy transfer.

### `RACI_CI_ACCESS`

Covers altered access to a conical intersection or closely related crossing that controls nonradiative decay. Strong support includes an explicitly located intersection, a potential-energy surface, dynamics, or a demonstrated structural coordinate controlling access. Low quantum yield, flexibility, or a small energy gap alone is insufficient.

### `RADIATIVE_RATE_STATE_BALANCE`

Covers radiative and nonradiative rates, oscillator strength, state population, branching, ISC/rISC, and related state balance. A lifetime, quantum yield, or statement that radiative decay increases does not by itself establish this family. Strong support normally includes paired quantum yield and lifetime, direct kinetic analysis, oscillator strength, state ordering, population branching, or ISC/rISC data. Do not equate an apparent lifetime with a microscopic rate. A downstream rate change caused by another mechanism should be labeled as a downstream readout or descriptor rather than automatically made primary.

### `RIM_RIR_RIV`

Covers restriction of intramolecular motion, rotation, vibration, or conformational freedom that suppresses nonradiative decay. Aggregation, crystallization, solid-state enhancement, or rigidity alone is insufficient. The source must connect the emission change to restricted motion through viscosity, temperature, rotor controls, structural comparisons, crystal geometry, kinetics, or calculations.

If the JSON marks `RIM_RIR_RIV` as `supported` but the supplied source evidence establishes only aggregation, crystallization, source-labeled AIE, or fluorescence turn-on without a motion-restriction link, treat this as a limited evidence overclaim requiring `NEEDS_MINOR_FIX`. Do not reduce it to a release-ready caveat unless another source passage provides the missing motion-specific connection.

### `SOKR_ANTI_KASHA`

Covers anti-Kasha or upper-state emission, including clearly assigned higher singlet or triplet emission. Reliable state assignment and evidence for a high-state radiative channel are required. A high-energy shoulder, hot band, vibronic band, unusual wavelength, or ordinary T1 phosphorescence is insufficient.

### `TRIPLET_METAL_ENERGY_TRANSFER`

Covers triplet pathways, RTP or phosphorescence, TADF/rISC, heavy-atom or metal-enhanced ISC, and triplet energy transfer or sensitization. Support may come from delayed emission, oxygen and temperature effects, transient absorption, EPR, state energetics, kinetics, or causal metal controls. Evidence for a generic triplet pathway does not automatically establish RTP, TADF, triplet energy transfer, or a metal-mediated pathway. A metal atom, heavy atom, long lifetime, small singlet-triplet gap, or delayed emission alone is insufficient.

## 1. Artifact correspondence

Confirm that all three artifacts describe the same source paper and target molecule, component, or material entity.

Check:

- whether the title, DOI, candidate identifier, molecule label, and case identity in JSON correspond to `source.md`;
- whether the current target can be distinguished from analogues, controls, isomers, metal complexes, host/guest components, counterions, or other entities in the same paper;
- whether `structure_match.png` compares the source-paper target structure with the RDKit depiction of the public SMILES;
- whether evidence is attached to the target rather than to another molecule, phase, sample, or condition.

Absence of a DOI string from `source.md` is not by itself a mismatch when title, target identity, structure, and experimental context correspond. If only the paper can be matched but not the target, use `SOURCE_UNCLEAR`. If the artifacts point to different targets, use `SOURCE_MISMATCH` or `SMILES_WRONG`.

Labels:

```text
SOURCE_MATCH
SOURCE_MATCH_WITH_DOI_MISSING
SOURCE_UNCLEAR
SOURCE_MISMATCH
```

## 2. JSON schema

Check the v0.4 raw-case structure. The top level should contain only:

```text
case_id
version
track
public_input
hidden_reference
```

`hidden_reference` should contain:

```text
source_article
reference_evidence_units
reference_diagnosis_units
```

The final synthesis must be one diagnosis unit with mechanism `FINAL_EVIDENCE_GROUNDED_DIAGNOSIS`, not an additional top-level field.

Labels:

```text
SCHEMA_OK
SCHEMA_MINOR_ISSUE
SCHEMA_INVALID
```

## 3. Public-input boundary

Check that `public_input` contains only the verified SMILES structure and the canonical generic task. It must not reveal article metadata, molecule names, labels, isomer identity, mechanism labels, experimental findings, spectra, lifetimes, quantum yields, packing, binding, or other answer cues.

Labels:

```text
PUBLIC_INPUT_OK
PUBLIC_INPUT_LEAKAGE
PUBLIC_INPUT_UNCLEAR
```

## 4. Molecular identity and SMILES

Determine whether `public_input.molecule.structure.value` represents the exact target defined by the source. Use `structure_match.png`, labels, figures, schemes, captions, names, formulas, and surrounding text in `source.md`.

Check scaffold and bond connectivity, linker length, substituent identity and position, heteroatoms, formal charge, explicitly specified stereochemistry, protonation, tautomerism, salt form, coordination state, counterions, and required components. For metal-containing or multicomponent systems, distinguish the complete target from a ligand, host, guest, fragment, or dot-disconnected convenience representation.

Provide a target identity summary based only on the artifacts. A useful stable identity key combines normalized DOI, target label, visible or canonical SMILES, and target role. The key supports later duplicate auditing but must not replace the artifact-level identity review.

Labels:

```text
SMILES_OK
SMILES_OK_WITH_CAVEAT
SMILES_UNCLEAR_NEEDS_IMAGE_CHECK
SMILES_WRONG
```

## 5. Evidence units

Review every evidence unit used by a primary, co-primary, strong secondary, weakened/rejected, underdetermined, or final-synthesis diagnosis.

For each core unit, check:

- uniqueness of `evidence_id`;
- whether the central factual claim is supported by `source.md`;
- whether `paper_quote` can be located as a source anchor;
- whether the mechanistic interpretation matches the evidence strength;
- whether the claim belongs to the correct target molecule, species, sample, phase, host/guest ratio, solvent, temperature, excitation condition, or other context;
- whether analogue or family-level evidence is explicitly marked as indirect;
- whether omitted figures, tables, spectra, or numerical values make the claim unverifiable.

A quote is a source locator and need not contain every interpretive phrase in the claim. Nearby text, captions, tables, and other explicit source content may jointly support the claim. OCR, line-break, hyphenation, Unicode, superscript, and punctuation differences are not substantive errors.

Use `PARTLY_SUPPORTED` only when a material fact or conclusion is supported only in part. Use `NOT_FOUND` when the source lacks the claimed fact. Use `OVERCLAIMED` when a weak observation is upgraded to a specific or exclusionary mechanism without support. Use `UNVERIFIABLE` when the source refers to evidence that is absent from the supplied parsed material.

Per-unit labels:

```text
SUPPORTED
PARTLY_SUPPORTED
OVERCLAIMED
NOT_FOUND
UNVERIFIABLE
```

Overall labels:

```text
EVIDENCE_SUPPORTED
EVIDENCE_PARTLY_SUPPORTED
EVIDENCE_OVERCLAIMED
EVIDENCE_NOT_FOUND
EVIDENCE_UNVERIFIABLE_FROM_PROVIDED_FILES
```

## 6. Diagnosis units

Review every diagnosis unit, including the final synthesis.

Check:

- uniqueness of `diagnosis_id`;
- canonical mechanism membership or correct use of the final-synthesis label;
- target and condition scope in `context`;
- consistency between `reference_status`, `diagnosis_role`, `expert_conclusion`, and `supporting_evidence_ids`;
- whether supporting evidence exists and is relevant;
- whether a weak clue is overstated as strong support;
- whether primary, co-primary, secondary, contextual, downstream, weakened, rejected, and underdetermined roles are distinguished;
- whether important source-discussed competing mechanisms are omitted or misrepresented.

Allowed status values are:

```text
supported
weakened_or_rejected
underdetermined
```

`diagnosis_role` is free text. Do not flag harmless wording, length, underscore, spacing, or synonym differences when the role is semantically consistent with status and conclusion.

For ordinary mechanisms, `supported` must have a supported primary, co-primary, secondary, contextual, enabling, downstream, or descriptor meaning. `weakened_or_rejected` must express weakened, rejected, excluded, unsupported, contrastive, or not-supported meaning. `underdetermined` must express unresolved, follow-up, scope-limited, untested, or missing-evidence meaning.

The final unit must use mechanism `FINAL_EVIDENCE_GROUNDED_DIAGNOSIS` and a role that clearly expresses final, integrated, synthesis, or overall diagnosis. Its role need not equal the literal string `final_synthesis`.

Per-unit labels:

```text
OK
MINOR_ISSUE
OVERCLAIMED
INCOMPLETE
INCONSISTENT
```

Overall labels:

```text
DIAGNOSIS_UNITS_OK
DIAGNOSIS_UNITS_MINOR_ISSUE
DIAGNOSIS_UNITS_OVERCLAIMED
DIAGNOSIS_UNITS_INCOMPLETE
DIAGNOSIS_UNITS_INCONSISTENT
```

## 7. Mechanism-set completeness and archive assignment

Check whether the JSON covers the important mechanisms that the source explicitly supports, weakens, rejects, compares, or leaves unresolved. Do not demand every theoretically plausible mechanism, and do not infer new diagnoses from structure alone.

The archive mechanism supplied in the request must be compared with the source-supported diagnosis. Retrieval, download, folder, and screening labels are discovery provenance, not final annotations. Recommend the best primary archive mechanism based on the strongest source-supported causal primary or co-primary mechanism. If several mechanisms are co-primary, any one may be used for archive placement provided that the multi-mechanism relationship remains explicit.

If the current archive mechanism is only contextual, downstream, weakened/rejected, underdetermined, or unsupported, state the recommended canonical destination. Cross-case duplication is handled separately and is not required in this single-case review.

Labels:

```text
MECHANISM_SET_COMPLETE
MECHANISM_SET_COMPLETE_WITH_CAVEAT
MECHANISM_SET_MINOR_ISSUE
MECHANISM_SET_INCOMPLETE
MECHANISM_SET_WRONG
```

Vocabulary labels:

```text
MECHANISM_VOCAB_OK
MECHANISM_VOCAB_MINOR_ISSUE
MECHANISM_VOCAB_OUT_OF_SCOPE_HANDLED
MECHANISM_VOCAB_INVALID
```

## 8. Final synthesis

Check that the integrated diagnosis accurately summarizes the evidence and diagnosis units. It should distinguish primary, co-primary, secondary, contextual, downstream, weakened, rejected, and underdetermined mechanisms; separate demonstrated conclusions from unresolved interpretations; avoid unsupported strong claims; and preserve sample, phase, environment, state-assignment, or kinetic caveats when they materially limit the conclusion.

Labels:

```text
FINAL_SYNTHESIS_OK
FINAL_SYNTHESIS_OVERCLAIMED
FINAL_SYNTHESIS_INCOMPLETE
FINAL_SYNTHESIS_INCONSISTENT
```

## 9. Overall usability and decision calibration

Use `FAIL_OR_REBUILD` when the case cannot be made reliable through a limited correction. Examples include a source mismatch, an incorrect molecular identity or SMILES, fabricated or missing core evidence, a severely incorrect mechanism set, an internally contradictory synthesis, unrecoverable answer leakage, or artifacts that are too incomplete to verify.

Use `NEEDS_MINOR_FIX` when the case is fundamentally recoverable but requires a limited substantive correction. Examples include removable leakage, an evidence overclaim, an incorrect evidence status or diagnosis role, a missing material limitation, an inaccurate quotation or evidence link, or a secondary mechanism incorrectly assigned as primary.

Do not assign `NEEDS_MINOR_FIX` merely for stylistic role names, short but adequate quotes, explanations placed in a different evidence field, formatting or OCR variation, or clearly marked indirect analogue evidence used at an appropriate strength.

Use `PASS` when the molecular identity, core evidence, evidence links, mechanism diagnoses, and final synthesis are reliable and no mandatory correction is required. A passing case may still contain source limitations, condition-specific scope, or uncertainty in secondary and alternative mechanisms. Record these limitations in the review notes. They do not create a separate overall decision when the reference already represents them accurately.

Do not assign `NEEDS_MINOR_FIX` merely because the source does not test every alternative mechanism, because a secondary mechanism remains underdetermined, or because the molecular representation omits a component that is not part of the defined target molecule. Use `PASS` when these limitations are already represented at the correct evidential strength and do not require a change to the benchmark reference.

The decision, usability, and disposition must follow one of these combinations:

```text
PASS             -> CASE_USABLE             -> KEEP
NEEDS_MINOR_FIX  -> CASE_NEEDS_MINOR_FIX    -> MINOR_FIX_THEN_KEEP
FAIL_OR_REBUILD  -> CASE_NEEDS_MAJOR_REPAIR -> MAJOR_REPAIR
FAIL_OR_REBUILD  -> CASE_NOT_USABLE         -> REBUILD_OR_DROP
```

## Required output template

Review all core evidence units and every diagnosis unit. Repeat the item blocks as needed. Do not fabricate an evidence identifier when a diagnosis has no supporting evidence.

```text
overall_decision:
PASS / NEEDS_MINOR_FIX / FAIL_OR_REBUILD

0. Artifact access status:
FILE_ACCESS_COMPLETE / FILE_MISSING_OR_UNREADABLE / FILE_CONTENT_POSSIBLY_TRUNCATED
notes:

1. Artifact correspondence:
SOURCE_MATCH / SOURCE_MATCH_WITH_DOI_MISSING / SOURCE_UNCLEAR / SOURCE_MISMATCH
notes:

2. JSON schema:
SCHEMA_OK / SCHEMA_MINOR_ISSUE / SCHEMA_INVALID
notes:

3. Public input:
PUBLIC_INPUT_OK / PUBLIC_INPUT_LEAKAGE / PUBLIC_INPUT_UNCLEAR
notes:

4. SMILES and target identity:
SMILES_OK / SMILES_OK_WITH_CAVEAT / SMILES_UNCLEAR_NEEDS_IMAGE_CHECK / SMILES_WRONG
target_identity_summary:
stable_identity_key:
duplicate_relevance_notes:
notes:

5. Evidence units overall:
EVIDENCE_SUPPORTED / EVIDENCE_PARTLY_SUPPORTED / EVIDENCE_OVERCLAIMED / EVIDENCE_NOT_FOUND / EVIDENCE_UNVERIFIABLE_FROM_PROVIDED_FILES
notes:

6. Core evidence review:
- evidence id:
  status: SUPPORTED / PARTLY_SUPPORTED / OVERCLAIMED / NOT_FOUND / UNVERIFIABLE
  used_by_diagnosis:
  notes:
- repeat until all core evidence has been reviewed

7. Diagnosis-unit review:
- diagnosis id:
  mechanism:
  reference_status:
  diagnosis_role:
  status: OK / MINOR_ISSUE / OVERCLAIMED / INCOMPLETE / INCONSISTENT
  notes:
- repeat until every diagnosis unit, including the final synthesis, has been reviewed

8. Diagnosis units overall:
DIAGNOSIS_UNITS_OK / DIAGNOSIS_UNITS_MINOR_ISSUE / DIAGNOSIS_UNITS_OVERCLAIMED / DIAGNOSIS_UNITS_INCOMPLETE / DIAGNOSIS_UNITS_INCONSISTENT
notes:

9. Mechanism-set completeness:
MECHANISM_SET_COMPLETE / MECHANISM_SET_COMPLETE_WITH_CAVEAT / MECHANISM_SET_MINOR_ISSUE / MECHANISM_SET_INCOMPLETE / MECHANISM_SET_WRONG
recommended_primary_archive_mechanism:
notes:

10. Mechanism vocabulary:
MECHANISM_VOCAB_OK / MECHANISM_VOCAB_MINOR_ISSUE / MECHANISM_VOCAB_OUT_OF_SCOPE_HANDLED / MECHANISM_VOCAB_INVALID
notes:

11. Final synthesis:
FINAL_SYNTHESIS_OK / FINAL_SYNTHESIS_OVERCLAIMED / FINAL_SYNTHESIS_INCOMPLETE / FINAL_SYNTHESIS_INCONSISTENT
notes:

12. Overall case usability:
CASE_USABLE / CASE_NEEDS_MINOR_FIX / CASE_NEEDS_MAJOR_REPAIR / CASE_NOT_USABLE
notes:

13. Blocking issues:
- blocker 1: None / ...
- blocker 2: None / ...

14. Required field changes:
- JSON path: None / ...
- current problem: None / ...
- recommended fix: None / ...

15. Disposition:
KEEP / MINOR_FIX_THEN_KEEP / MAJOR_REPAIR / REBUILD_OR_DROP
notes:

One-sentence summary:
```
