# Stage 1 Paper Screening

Screen one parsed primary-source paper for molecule-level benchmark suitability.
Do not assume a target mechanism. Infer only source-grounded hypotheses from
the official mechanism vocabulary. Do not generate benchmark JSON or SMILES.

Assess whether the paper is original experimental research or a molecule-level computational mechanism study; concerns AIE, aggregation-, solid-, or environment-dependent luminescence or closely related molecular photophysics; contains locatable entities with traceable labels or structures; reports photophysical, excited-state, structural, or computational evidence; and contains enough mechanism-relevant evidence for later differential diagnosis.

The input also lists image IDs, filenames, and caption context recovered from the parsed paper. Use the captions and surrounding context to recommend at most 12 images that are most likely to show target molecular structures, structural schemes, or identity-relevant components. Do not claim to have visually inspected the image pixels at this stage. Return an empty list when no listed image is relevant.

Return exactly one JSON object with these fields:

```json
{
  "doi": "string",
  "title": "string or null",
  "paper_verdict": "pass|fail",
  "failure_reason_type": "not_failed|review_or_book_chapter|not_aie_related|no_molecule_level_unit|no_structure_information|no_photophysical_data|application_only|keyword_only|md_quality_bad|not_primary_source|other",
  "paper_type": "original_research|review|book_chapter|patent|webpage|database|computational_mechanism|unclear",
  "aie_relevance": "strong|medium|weak|none",
  "molecule_level_benchmark_fit": "strong|medium|weak|no",
  "evidence_basis": "experimental|computational|mixed|application_only|keyword_only|unclear",
  "has_structure_information": true,
  "has_compound_labels": true,
  "has_photophysical_or_excited_state_data": true,
  "has_mechanism_discussion": true,
  "candidate_units": [{"unit_label": "string", "unit_type": "molecule|probe|ligand|guest|host_guest_complex|framework_material|polymer_material|series|unclear", "can_be_molecule_level_case": true, "eligibility": "pass|fail", "reason": "string"}],
  "recommended_image_ids": ["I001"],
  "image_recommendation_reason": "concise explanation based on captions and context",
  "possible_hypotheses_to_check_later": ["official mechanism names"],
  "source_quality_risk": "low|medium|high",
  "source_quality_issues": ["string"],
  "diagnostic_case_potential": "strong|medium|weak|none",
  "main_reason": "string"
}
```

Use `pass` only when the supplied paper contains enough source-grounded material for molecule-level candidate extraction. Otherwise use `fail` and provide a specific `failure_reason_type`. For a passing paper, `failure_reason_type` must be `not_failed`.
