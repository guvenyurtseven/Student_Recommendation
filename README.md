# METU Student Planner

This project is evolving from standalone METU SAIS scrapers into a student
assistant/planner. The long-term goal is to recommend realistic next-semester
course plans from a student's department, completed courses, curriculum, course
offerings, and prerequisite graph.

Current state:

- A reusable METU SAIS source adapter and offering ingestion pipeline exist.
- Prerequisite DAG extraction exists for two semester CSV inputs.
- Latest curriculum ingestion exists for 13 active Ankara-campus engineering
  undergraduate programs from METU Academic Catalog.
- Recursive prerequisite closure exists for the combined engineering curriculum
  and for each of the 13 active engineering programs.
- Deterministic next-semester recommendation CLI exists, with conservative
  offering-aware filtering when offering data has been loaded.

Planned data layers:

- `data/raw`: source snapshots exactly as scraped.
- `data/processed`: normalized JSON/CSV artifacts generated from raw inputs.
- `data/db`: local SQLite database generated from normalized data.

Primary planning documents:

- [Architecture](docs/architecture.md)
- [Data Model](docs/data_model.md)
- [Curriculum Ingestion Plan](docs/curriculum_ingestion_plan.md)
- [Roadmap](docs/roadmap.md)
- [Project Retrospective](docs/project_retrospective.md)
- [Project Health Audit and Next Steps](docs/project_health_audit_and_next_steps.md)
- [Manual Corrections](docs/manual_corrections.md)
- [Registration Policy Layer](docs/registration_policy.md)
- [Grade Model](docs/grade_model.md)
- [Prerequisite Evaluator](docs/prerequisite_evaluator.md)
- [Detailed Next Steps Plan](docs/next_steps_detailed_plan.md)

## Current Curriculum Pipeline

Initialize and load the local database:

```powershell
python .\scripts\init_db.py
python .\scripts\load_programs.py
```

Scrape latest engineering curricula from METU Academic Catalog:

```powershell
python .\scripts\scrape_curricula.py
```

Load processed curriculum JSON files into SQLite:

```powershell
python .\scripts\load_curricula.py
```

Build recursive prerequisite closure from curriculum seed courses:

```powershell
python .\scripts\build_prerequisite_closure.py
python .\scripts\load_prerequisite_closure.py --clear-existing
```

Apply reviewed manual corrections:

```powershell
python .\scripts\apply_manual_corrections.py
```

Run data quality and review reports:

```powershell
python .\scripts\audit_data_quality.py
python .\scripts\generate_course_identity_review.py
python .\scripts\generate_offering_coverage_report.py --semesters 20252
```

Scrape and load the target-semester SAIS course offering snapshot:

```powershell
python .\scripts\scrape_offerings.py --semesters 20252
python .\scripts\load_offerings.py --semesters 20252 --clear-existing --prune-orphan-non-undergraduate-courses
```

Offerings are intended to be refreshed manually once per target semester after
METU SAIS publishes that semester's course list. The planner should use this
fresh target-semester snapshot as authoritative instead of predicting future
offerings from historical patterns. The default offering config is
`config/offering_departments.json`, which includes the 13 active engineering
programs plus high-impact service departments such as MATH, PHYS, CHEM, HIST,
TURK, ENG, OHS, IS, BA, ES, ECON, and BIOL.

Run the deterministic planner CLI:

```powershell
python .\scripts\recommend_next_semester.py --input .\examples\students\ceng_sample_planning_input.json
```

Write a student-readable Markdown planning report:

```powershell
python .\scripts\recommend_next_semester.py `
  --input .\examples\students\ceng_sample_planning_input.json `
  --format markdown `
  --output .\data\processed\reports\ceng_sample_recommendation.md
```

Write the sanitized LLM handoff package for the narrative report layer:

```powershell
python .\scripts\recommend_next_semester.py `
  --input .\examples\students\ceng_sample_planning_input.json `
  --format llm-package `
  --output .\data\processed\reports\ceng_sample_llm_package.json
```

The LLM package does not call an external model. It combines the versioned
preprompt, deterministic Markdown report, response contract, model policy, and
privacy/safety contract. Future API workers should send only this sanitized
package to the LLM; academic decisions must stay in the deterministic planner.
This feature is currently parked for product v1 so the default product can stay
free and deterministic.

Extract planner input from transcript text or PDF without storing the raw
transcript:

```powershell
python .\scripts\extract_transcript_planning_input.py `
  --transcript-text .\examples\students\ceng_sample_transcript_text.txt `
  --program CENG `
  --target-semester 20252 `
  --output .\data\processed\reports\ceng_sample_from_transcript_input.json
```

The PDF mode reads the file in memory and requires optional `pypdf` support. The
script writes only planner-ready JSON fields such as course code, grade,
semester, attempt order, credits, and ECTS. It does not persist the transcript
PDF or raw extracted text.

Run the first local web prototype:

```powershell
python .\scripts\run_web_app.py --port 8000
```

Then open:

```text
http://127.0.0.1:8000/
```

The current web prototype supports two input paths: transcript PDF upload and
planner JSON. Transcript PDFs are sent to the local backend as base64, decoded
in memory, parsed, and discarded. The backend returns the deterministic Markdown
recommendation report.

React + Node.js web prototype:

```powershell
cd .\web
npm install
npm run build
npm run server
```

Open:

```text
http://127.0.0.1:3000/
```

The React UI includes transcript PDF upload, planner JSON input, target semester
settings, difficulty preference, and elective category preferences. The Node
server calls the Python planner through `scripts/recommendation_api_bridge.py`,
so the academic decision engine remains shared and deterministic.
In transcript mode, the department/program is detected from the PDF; users do
not need to choose their department manually.

If offering data is missing, the planner keeps recommendations available but
emits an explicit warning. If target-semester offering coverage is loaded for a
subject, known not-offered courses are excluded from recommendation scenarios.
The SQLite loader currently keeps undergraduate offerings for the planner DB.
The planner also applies a deterministic METU undergraduate registration policy
layer: transcript-derived academic standing/CGPA, probation restrictions,
repeat-priority courses, and course-count load caps are enforced before the
final recommendation scenarios are returned.
For engineering curricula, Turkish language alternatives are normalized to
`TURK 303` for fall-side planning and `TURK 304` for spring-side planning; older
`TURK 105/106/201/202` alternatives are not recommended by the product layer.

Important outputs:

- `data/processed/curricula/*-latest.curriculum.json`
- `data/processed/curricula/*-latest.curriculum_requirements.csv`
- `data/processed/curricula/all_engineering_latest_curriculum_requirements.csv`
- `data/processed/curricula/curriculum_review_report.md`
- `data/processed/prerequisites/engineering-latest-prerequisite-closure.json`
- `data/processed/prerequisites/engineering-latest-prerequisite-closure-edges.csv`
- `data/processed/prerequisites/engineering-latest-prerequisite-closure-nodes.csv`
- `data/processed/prerequisites/engineering-latest-prerequisite-closure-unresolved.csv`
- `data/raw/sais/offerings/<semester>/<program>/...`
- `data/processed/offerings/<semester>/<program>.offerings.json`
- `data/processed/offerings/all_scraped_offerings.csv`
- `data/processed/reports/data_quality_report.md`
- `data/processed/reports/course_identity_review.md`
- `data/processed/reports/offering_coverage_report.md`
- `data/processed/reports/offering_missing_curriculum_courses.csv`
- `data/processed/reports/ceng_sample_recommendation.md`
- `data/processed/reports/ceng_sample_llm_package.json`
- `data/processed/reports/ceng_sample_from_transcript_input.json`
- `data/manual/corrections/*.json`
- `data/db/student_planner.sqlite`
