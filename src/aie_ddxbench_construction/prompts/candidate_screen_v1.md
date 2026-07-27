# Stage 2 Molecule Candidate Screening

Identify molecule-level candidates for later SMILES resolution. Do not generate
final benchmark JSON. Do not invent or finalize SMILES. Infer source-grounded
assignments across the official mechanism vocabulary without assuming a target
mechanism.

You are given labeled contact sheets for the image records selected from Stage 1 caption analysis. Visually inspect those images. For each candidate, select only image IDs that actually show the candidate's molecular structure or identity-relevant components. Do not select a graph, spectrum, packing diagram, or unrelated molecule merely because its caption mentions the candidate. Use an empty image list if no displayed image supports exact structure identity.

Candidate policy:

- A candidate unit must be one concrete molecule, probe, ligand, or guest that can later receive one SMILES.
- Record each concrete candidate as `pass` or `fail`. A candidate passes only when it is a locatable concrete molecule and the supplied source contains enough identity information for Stage 3. Do not emit separate records for series, families, host-guest assemblies, frameworks, polymers, experimental media, instruments, crystal states, or other non-molecular context.
- Distinguish molecule-specific evidence from series-level, comparator-only, application-only, and keyword-only statements.
- Keep official mechanism assignments inside the supplied 11-family vocabulary. Non-official concepts belong in contextual notes.
- In `structure_image_ids`, return at most two IDs from the supplied contact sheets, ordered from strongest to weaker identity evidence. These IDs are resolved deterministically to the original high-resolution files for Stage 3.
- In `structure_text_sources`, identify only text, captions, schemes, or tables actually present in the supplied parsed source. Do not request unavailable supporting information, databases, CCDC records, or unsupplied figures. Record missing-source, analogue, isomer, metal-complex, and multicomponent concerns in `stage3_risk_flags`.

Return exactly one JSON object with this structure:

```json
{
  "paper_title": "string or null",
  "target_discovery_mechanism": "one official mechanism",
  "candidate_units": [
    {
      "unit_label": "string",
      "unit_type": "molecule|probe|ligand|guest|unclear",
      "eligibility": "pass|fail",
      "stage3_risk_flags": ["string"],
      "structure_image_ids": ["I001"],
      "structure_text_sources": ["available supplied textual or caption source"],
      "official_mechanism_assignments": [
        {
          "mechanism": "one official mechanism",
          "role": "primary|co_primary|secondary|contextual",
          "evidence_strength": "strong|moderate|weak|unsupported"
        }
      ],
      "confidence": "high|medium|low",
      "reason": "concise molecule-specific justification"
    }
  ]
}
```

Allowed values:

- `unit_type`: `molecule|probe|ligand|guest|unclear`
- `eligibility`: `pass|fail`

Official assignments must use a supplied official mechanism and include a role and evidence strength. Keep `reason` concise and do not reproduce long evidence summaries that the downstream reference stage will reconstruct from the source.
