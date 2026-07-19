# AIE-DDxBench Independent Reference-Alignment Review

Review only the artifacts supplied in the current request. Do not browse, use remembered facts, consult prior conversations, or regenerate the case JSON.

The request supplies:

1. `final_reference_alignment.json`: the candidate raw case;
2. `source.md`: the parsed source article;
3. `structure_match.png`: source-paper structure evidence beside the RDKit depiction of the candidate SMILES;
4. the current archive mechanism as request metadata.

Determine whether the JSON is suitable as an AIE-DDxBench reference answer. Focus on scientific correctness, molecular identity, source grounding, mechanism coverage, and semantic consistency. Deterministic local checks already validate schema structure, identifier uniqueness, reference resolution, the locked SMILES, the canonical public task, and quotation anchoring. Report a visible structural issue if present, but do not make deterministic checks the main focus.

Use only facts in the supplied artifacts. Mark information that cannot be verified as `UNVERIFIABLE`. Do not reveal chain-of-thought. Return only the completed review template.

## 1. Mechanism vocabulary and evidential boundaries

Ordinary mechanisms and core evidence links must use one of these 11 families:

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

`FINAL_EVIDENCE_GROUNDED_DIAGNOSIS` is reserved for the integrated final synthesis. Subtype terms such as TICT, RIR, TADF, RTP, TTA, J-aggregate, excimer, and PET belong in context, conclusions, or notes when a canonical family is required. Describe a source-supported mechanism outside the vocabulary as out of scope rather than forcing it into an incorrect family.

The boundaries below are evidential guidelines, not mandatory checklists. A mechanism may be supported by other source-specific causal evidence of comparable strength. Do not reject a diagnosis solely because the paper lacks one example evidence type listed below.

### `AGGREGATE_EXCITON_EXCIMER`

Covers aggregate excitons, excimer or aggregate emission, J/H aggregation, excitonic coupling, and aggregation-induced emissive states. Aggregation, concentration increase, a solid-state change, a red shift, or a new band alone is insufficient without a state assignment or comparably direct causal evidence.

### `ESIPT_PT`

Covers excited-state proton transfer, tautomeric emission, and enol/keto proton-transfer pathways. Dual emission, a large Stokes shift, hydrogen bonding, or solvent response alone is insufficient without a proton-transfer or tautomer-state connection.

### `HOST_GUEST_INTERACTION`

Covers host-guest binding, inclusion, association, recognition, or supramolecular complexation that changes emission. Evidence must support both complex formation and its connection to the photophysical change.

### `ICT_TICT_CT`

Covers intramolecular charge transfer, TICT, competition between local and charge-transfer states, polarity-dependent emission, and donor-acceptor torsion. Donor-acceptor structure or polarity response may support general ICT/CT but does not establish TICT without evidence for torsion or a twisted-state assignment.

### `PACKING_HOST_MATRIX_CONFINEMENT`

Covers crystal packing, host or matrix effects, rigid environments, and confinement. The source must connect a specific phase, packing arrangement, host, matrix, cavity, loading, or rigid environment to the photophysical change.

### `PET_ET`

Covers photoinduced electron transfer, electron or hole transfer, charge-separated states, and redox-controlled quenching or recovery. Generic quenching, donor-acceptor structure, CT character, or electron-density redistribution alone is insufficient. Do not confuse electron transfer with emissive ICT or energy transfer.

### `RACI_CI_ACCESS`

Covers altered access to a conical intersection or related crossing that controls nonradiative decay. Low quantum yield, flexibility, or a small energy gap alone is insufficient without a located crossing, relevant potential-energy surface, dynamics, or a demonstrated structural coordinate controlling access.

### `RADIATIVE_RATE_STATE_BALANCE`

Covers radiative and nonradiative rates, oscillator strength, state population, branching, ISC/rISC, and related state balance. A lifetime, quantum yield, or statement that radiative decay increases does not by itself establish this family. Do not equate an apparent lifetime with a microscopic rate.

A downstream or descriptor mechanism may be `supported` only when the source explicitly supports the stated photophysical relationship, rate change, state balance, or readout. It must not receive a primary or co-primary causal role or determine the primary archive mechanism without corresponding causal evidence.

### `RIM_RIR_RIV`

Covers restriction of intramolecular motion, rotation, vibration, or conformational freedom that suppresses nonradiative decay. Aggregation, crystallization, source-labeled AIE, rigidity, solid-state enhancement, or fluorescence turn-on alone is insufficient without a motion-specific connection.

If `RIM_RIR_RIV` is marked `supported` without that connection, mark the diagnosis `OVERCLAIMED`. The overall decision should normally be `NEEDS_MINOR_FIX` because the diagnosis requires a limited substantive correction. Use `FAIL_OR_REBUILD` only when unsupported RIM is central and the remaining evidence cannot support a reliable in-scope case.

### `SOKR_ANTI_KASHA`

Covers anti-Kasha or upper-state emission. A reliable state assignment and evidence for a higher-state radiative channel are required. A high-energy shoulder, hot band, vibronic band, unusual wavelength, or ordinary T1 phosphorescence alone is insufficient.

### `TRIPLET_METAL_ENERGY_TRANSFER`

Covers triplet pathways, RTP or phosphorescence, TADF/rISC, heavy-atom or metal-enhanced ISC, and triplet energy transfer or sensitization. A metal atom, heavy atom, long lifetime, small singlet-triplet gap, or delayed emission alone does not establish a specific triplet subtype or causal pathway.

## 2. Artifact correspondence and public boundary

Confirm that the artifacts describe the same paper and exact target molecule, component, or material entity. Check title, DOI, candidate identifier, molecule label, structure, target role, sample, phase, and experimental context. Distinguish the target from analogues, controls, isomers, complexes, hosts, guests, ligands, counterions, and other entities in the paper.

Absence of a DOI string from `source.md` is not a mismatch when title, structure, target identity, and context correspond. Use `SOURCE_UNCLEAR` when the paper but not the target can be matched. Use `SOURCE_MISMATCH` when the artifacts point to different targets.

`public_input` may contain only the verified SMILES structure and this exact generic task:

```text
Starting from the SMILES structure only, autonomously investigate possible AIE/photophysical mechanisms. Report generated evidence, supported mechanisms, weakened or rejected mechanisms, underdetermined mechanisms, necessary wet-lab follow-ups, and a final evidence-grounded mechanistic diagnosis.
```

It must not expose article metadata, molecule names, labels, mechanism labels, experimental findings, or other answer cues.

## 3. Molecular identity and SMILES

Determine whether `public_input.molecule.structure.value` represents the exact target. Use all supplied artifacts, including structure images, labels, schemes, captions, names, formulas, and surrounding text.

Check scaffold and bond connectivity, linker length, substituent identity and position, heteroatoms, formal charge, explicitly specified stereochemistry, protonation, tautomerism, coordination state, counterions, and required components. For metal-containing or multicomponent systems, distinguish the complete target from a ligand, host, guest, fragment, or convenience representation.

Use `SMILES_UNVERIFIABLE_FROM_PROVIDED_ARTIFACTS` only when the structure comparison image is missing, cropped, unreadable, or insufficient and the remaining supplied artifacts do not independently resolve identity. Record acceptable representation or source limitations under `Non-blocking limitations`; do not create a separate identity state for them.

## 4. Evidence review

Review every `reference_evidence_unit`, including units not referenced by a diagnosis. For each unit, check the factual claim, quotation anchor, mechanistic interpretation, evidence strength, target identity, sample and condition scope, and whether indirect analogue or family-level evidence is labeled appropriately.

A quotation is a source locator and need not contain every interpretive phrase. Nearby text, captions, tables, and other explicit source content may jointly support a claim. OCR, line-break, hyphenation, Unicode, superscript, and punctuation differences are not substantive errors.

Review unreferenced evidence separately. An unreferenced unit is not automatically an error. Require a change only when it is redundant, irrelevant, misleading, or should materially support an existing diagnosis.

Only evidence that materially supports or affects a primary, co-primary, supported secondary, weakened-or-rejected, underdetermined, or final diagnosis may determine the overall evidence label and overall decision. A minor issue in non-material background evidence must not by itself downgrade the case.

Per-unit labels:

```text
SUPPORTED
PARTLY_SUPPORTED
OVERCLAIMED
NOT_FOUND
UNVERIFIABLE
```

For the overall evidence label, use the most severe material result:

```text
EVIDENCE_NOT_FOUND
> EVIDENCE_OVERCLAIMED
> EVIDENCE_UNVERIFIABLE_FROM_PROVIDED_FILES
> EVIDENCE_PARTLY_SUPPORTED
> EVIDENCE_SUPPORTED
```

## 5. Diagnosis review

Review every diagnosis unit, including the final synthesis. Check canonical mechanism membership, target and condition scope, consistency among `reference_status`, `diagnosis_role`, `expert_conclusion`, and `supporting_evidence_ids`, the relevance and strength of supporting evidence, and omission or misrepresentation of important source-discussed mechanisms.

Allowed statuses are `supported`, `weakened_or_rejected`, and `underdetermined`. `diagnosis_role` is free text; accept harmless wording and synonym differences when the role is semantically consistent with status and conclusion.

For ordinary mechanisms, `supported` may express primary, co-primary, secondary, contextual, enabling, downstream, or descriptor meaning, subject to the causal restrictions above. `weakened_or_rejected` must express a weakened, rejected, excluded, unsupported, or contrastive meaning. `underdetermined` must express unresolved, scope-limited, untested, or missing-evidence meaning.

The final unit must use `FINAL_EVIDENCE_GROUNDED_DIAGNOSIS` and summarize only the role categories actually present or materially relevant. It need not mention absent categories.

Per-unit labels:

```text
OK
MINOR_ISSUE
OVERCLAIMED
INCOMPLETE
INCONSISTENT
```

For the overall diagnosis label, use the most severe material result:

```text
DIAGNOSIS_UNITS_INCONSISTENT
> DIAGNOSIS_UNITS_OVERCLAIMED
> DIAGNOSIS_UNITS_INCOMPLETE
> DIAGNOSIS_UNITS_MINOR_ISSUE
> DIAGNOSIS_UNITS_OK
```

## 6. Mechanism set, archive assignment, and final synthesis

Check whether all materially source-discussed mechanisms and remaining uncertainties are represented at the correct status and role. `MECHANISM_SET_COMPLETE` does not mean every mechanistic question is resolved. It means the JSON represents all material source content correctly and requires no field change.

Compare the current archive mechanism supplied in the request with the strongest source-supported causal primary or co-primary diagnosis. A downstream, descriptor, contextual, weakened, rejected, underdetermined, or unsupported mechanism must not determine the primary archive assignment. Retrieval and screening labels are provenance, not final annotations.

Check that the final synthesis reflects the evidence and diagnosis units, separates supported conclusions from uncertainty, and preserves material target, sample, phase, environment, state-assignment, and kinetic scope. It need only distinguish roles that are present or materially relevant.

## 7. Overall decision

Apply this decision test:

1. If no JSON field must be changed for release, use `PASS`.
2. If limited field-level changes are required while molecular identity, core evidence, and the central interpretation remain reliable, use `NEEDS_MINOR_FIX`.
3. If reliability requires replacing the target identity, rebuilding core evidence, or substantially reconstructing the central mechanism diagnosis, use `FAIL_OR_REBUILD`.

Correctly represented uncertainty or source limitation is not a required field change. Stylistic role names, adequate short quotations, formatting or OCR variation, and appropriately qualified indirect evidence do not require a change.

For `PASS` and `NEEDS_MINOR_FIX`, every entry under `Blocking issues` must be `None`. Limited mandatory corrections belong under `Required field changes`. Blocking issues are reserved for `FAIL_OR_REBUILD` and must identify what prevents reliability through limited field-level correction.

The decision, usability, and disposition must follow one of these combinations:

```text
PASS             -> CASE_USABLE             -> KEEP
NEEDS_MINOR_FIX  -> CASE_NEEDS_MINOR_FIX    -> MINOR_FIX_THEN_KEEP
FAIL_OR_REBUILD  -> CASE_NEEDS_MAJOR_REPAIR -> MAJOR_REPAIR
FAIL_OR_REBUILD  -> CASE_NOT_USABLE         -> REBUILD_OR_DROP
```

## Required output template

Review every evidence unit and diagnosis unit. Repeat item blocks as needed. List only mandatory JSON changes under `Required field changes`; place accurately represented source limitations and uncertainty under `Non-blocking limitations`.

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
SMILES_OK / SMILES_UNVERIFIABLE_FROM_PROVIDED_ARTIFACTS / SMILES_WRONG
target_identity_summary:
notes:

5. Evidence units overall:
EVIDENCE_SUPPORTED / EVIDENCE_PARTLY_SUPPORTED / EVIDENCE_OVERCLAIMED / EVIDENCE_NOT_FOUND / EVIDENCE_UNVERIFIABLE_FROM_PROVIDED_FILES
notes:

6. Evidence-unit review:
- evidence id:
  status: SUPPORTED / PARTLY_SUPPORTED / OVERCLAIMED / NOT_FOUND / UNVERIFIABLE
  materially_used: yes / no
  used_by_diagnosis:
  notes:
- repeat until every evidence unit has been reviewed

7. Unreferenced evidence units:
- evidence id: None / ...
  materiality:
  required_action: None / ...
  notes:

8. Diagnosis-unit review:
- diagnosis id:
  mechanism:
  reference_status:
  diagnosis_role:
  status: OK / MINOR_ISSUE / OVERCLAIMED / INCOMPLETE / INCONSISTENT
  notes:
- repeat until every diagnosis unit, including the final synthesis, has been reviewed

9. Diagnosis units overall:
DIAGNOSIS_UNITS_OK / DIAGNOSIS_UNITS_MINOR_ISSUE / DIAGNOSIS_UNITS_OVERCLAIMED / DIAGNOSIS_UNITS_INCOMPLETE / DIAGNOSIS_UNITS_INCONSISTENT
notes:

10. Mechanism-set completeness:
MECHANISM_SET_COMPLETE / MECHANISM_SET_MINOR_ISSUE / MECHANISM_SET_INCOMPLETE / MECHANISM_SET_WRONG
current_archive_mechanism:
archive_assignment_assessment:
recommended_primary_archive_mechanism:
notes:

11. Mechanism vocabulary:
MECHANISM_VOCAB_OK / MECHANISM_VOCAB_MINOR_ISSUE / MECHANISM_VOCAB_OUT_OF_SCOPE_HANDLED / MECHANISM_VOCAB_INVALID
notes:

12. Final synthesis:
FINAL_SYNTHESIS_OK / FINAL_SYNTHESIS_OVERCLAIMED / FINAL_SYNTHESIS_INCOMPLETE / FINAL_SYNTHESIS_INCONSISTENT
notes:

13. Overall case usability:
CASE_USABLE / CASE_NEEDS_MINOR_FIX / CASE_NEEDS_MAJOR_REPAIR / CASE_NOT_USABLE
notes:

14. Blocking issues:
- blocker: None / ...

15. Required field changes:
- JSON path: None / ...
  current value:
  current problem:
  recommended replacement:
  reason:
- repeat for every mandatory field change

16. Non-blocking limitations:
- limitation: None / ...
  affected scope:
  notes:

17. Disposition:
KEEP / MINOR_FIX_THEN_KEEP / MAJOR_REPAIR / REBUILD_OR_DROP
notes:

18. One-sentence summary:
```
