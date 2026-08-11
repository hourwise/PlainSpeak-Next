# Validation Corpus

Independent text samples for evaluating PlainSpeak's analysis quality.
These texts were NOT written to satisfy PlainSpeak's tests.

## Methodology

### Selection criteria
- Real-world texts from diverse domains
- Not authored by the PlainSpeak development process
- Prefer openly licensed or public-domain material
- Include both clearly accessible and clearly difficult examples
- Include texts where known readability issues exist independently

### Review process
Each sample can be evaluated using the scoring formats in `SCORING_FORMAT.md`.
Results should be recorded per-sample and aggregated to identify systematic
strengths and weaknesses in PlainSpeak's analysis.

### Corpus structure
```
validation/
  SCORING_FORMAT.md       — Human-review scoring templates
  samples/
    gov_uk_*.txt           — UK government/public services
    nhs_*.txt              — NHS/health information
    housing_*.txt          — Housing/tenancy
    insurance_*.txt        — Insurance
    finance_*.txt          — Consumer finance
    education_*.txt        — Education
    legal_*.txt            — Legal/public legal information
    academic_*.txt         — Scientific/academic
    general_*.txt          — Everyday writing
    plain_good_*.txt       — Deliberately clear examples
    plain_poor_*.txt       — Deliberately difficult examples
  metadata.json            — Corpus metadata index
```

### Domain targets (50+ passages)
| Domain | Target | Status |
|---|---|---|
| UK government/public services | 8 | ✅ |
| NHS/health information | 8 | ✅ |
| Housing/tenancy | 6 | ✅ |
| Insurance | 5 | ✅ |
| Consumer finance | 5 | ✅ |
| Education | 5 | ✅ |
| Legal/public legal information | 5 | ✅ |
| Scientific/academic | 4 | ✅ |
| Everyday writing | 4 | ✅ |
| Plain-language exemplars | 3 | ✅ |
| Deliberately difficult | 3 | ✅ |
| **Total** | **56** | ✅ |

### Provenance notes
- UK government and NHS texts: Open Government Licence v3.0
- Other texts: short excerpts used for evaluation purposes
- No copyrighted material reproduced beyond fair dealing/fair use
- Where possible, URLs to original sources are provided in metadata

### Expected concerns (independently known)
- gov_uk samples: known to vary in readability; some legacy content is very complex
- nhs samples: patient information leaflets — legally required but often written above
  recommended reading levels
- housing samples: tenancy agreements known to be inaccessible to many tenants
- insurance samples: policy wordings studied as examples of unnecessarily complex prose
- academic samples: written for specialist audiences; complexity is intentional
- plain_good samples: deliberately written to be accessible
- plain_poor samples: deliberately written to demonstrate common barriers
