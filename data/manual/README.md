# Manual Review and Corrections

This directory contains human-reviewed corrections that are applied after
automatic scraping and DB loading.

The guiding rule is:

```text
raw scrape + parser + manual corrections = reproducible reviewed data
```

Do not edit generated CSV, JSON, or SQLite rows by hand. Add reviewed changes to
`data/manual/corrections/*.json`, then run:

```powershell
python .\scripts\apply_manual_corrections.py
python .\scripts\audit_data_quality.py
python .\scripts\generate_course_identity_review.py
```

## Directories

- `corrections/`: structured correction files that can be applied by scripts.
- `reviews/`: human review notes and queue files that may not be directly applied.

## Review Status

Use these values consistently:

- `needs_review`: known issue, not yet approved for application.
- `reviewed`: checked and accepted as-is.
- `corrected`: checked and intentionally changes scraped data.
- `deprecated`: old correction kept only for history.

By default, `apply_manual_corrections.py` applies only `reviewed` and
`corrected` entries.
