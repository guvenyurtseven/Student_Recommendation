# METU Student Planner

This project is evolving from standalone METU SAIS scrapers into a student
assistant/planner. The long-term goal is to recommend realistic next-semester
course plans from a student's department, completed courses, curriculum, course
offerings, and prerequisite graph.

Current state:

- Course offering CSV scrapers exist for METU SAIS.
- Prerequisite DAG extraction exists for two semester CSV inputs.
- Latest curriculum ingestion exists for 13 active Ankara-campus engineering
  undergraduate programs from METU Academic Catalog.
- Recursive prerequisite closure exists for the combined engineering curriculum
  and for each of the 13 active engineering programs.

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
```

Important outputs:

- `data/processed/curricula/*-latest.curriculum.json`
- `data/processed/curricula/*-latest.curriculum_requirements.csv`
- `data/processed/curricula/all_engineering_latest_curriculum_requirements.csv`
- `data/processed/curricula/curriculum_review_report.md`
- `data/processed/prerequisites/engineering-latest-prerequisite-closure.json`
- `data/processed/prerequisites/engineering-latest-prerequisite-closure-edges.csv`
- `data/processed/prerequisites/engineering-latest-prerequisite-closure-nodes.csv`
- `data/processed/prerequisites/engineering-latest-prerequisite-closure-unresolved.csv`
- `data/processed/reports/data_quality_report.md`
- `data/processed/reports/course_identity_review.md`
- `data/manual/corrections/*.json`
- `data/db/student_planner.sqlite`
