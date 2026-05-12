# Current Execution Plan

Last updated: 2026-05-12

## Product Direction

The target product is a student-facing semester planning assistant. The user
uploads a transcript PDF, the system extracts the department and academic
history, and the planner returns academically valid route options for the active
operation semester.

The core output is a semester roadmap:

- which courses are available now,
- which courses should be prioritized because they unlock later courses,
- which repeat courses must be handled,
- which zero-credit/easy required courses can be included without affecting
  credit-bearing load,
- how elective slots are progressing,
- and which route best matches the student's preferred workload.

Weekly schedule generation is no longer part of the product scope. The app
must not call an external schedule source, and the student UI must not show a
weekly schedule panel.

## Decisions From Latest Review

- Manual data correction hardening is postponed to the end.
- Current course identity handling is acceptable for this phase.
- Official elective pool scraping is out of scope for now.
- Difficulty index improvements are postponed until an official or credible
  historical dataset exists.
- LLM narrative generation is shelved for now because a high-traffic free
  product cannot depend on paid per-request inference.
- Deployment/CI/E2E hardening is important, but should come after the planner
  and UI produce the desired product output.
- Schedule integration is cancelled for product v1. Keep the recommendation
  engine focused on academically valid semester routes.

## Immediate Roadmap

1. Keep testing transcript parsing with the four local PDF fixtures.
2. Keep the active semester as an operation-level setting in
   `config/operation.json`.
3. Keep `/admin` as the owner workflow for refreshing the new semester offering
   snapshot after METU SAIS updates.
4. Keep the offering refresh job explicit and operator-triggered:
   scrape current SAIS offerings, load SQLite, regenerate coverage, then set the
   active operation semester.
5. Continue polishing the React UI around the actual output: route cards,
   course explanations, elective status, warnings, feedback, and admin controls.
6. Hide internal scores and ECTS from the student-facing route cards unless a
   future UX pass decides they are useful.

## Implemented Product Infrastructure

- `config/operation.json`
- `student_planner.services.operation_semester`
- `scripts/admin_refresh_operation_semester.py`
- Transcript recommendation API defaults missing target semester to the active
  operation semester.
- Node admin endpoints:
  - `GET /api/admin/operation-semester`
  - `POST /api/admin/refresh-operation-semester`
  - `GET /api/admin/refresh-job`
- React student UI:
  - no target semester input for students,
  - transcript PDF upload,
  - difficulty preference,
  - elective category preferences,
  - stacked route cards,
  - orange visual theme,
  - locked submit button while a plan is being generated.
- Course-level student summaries in the `student_view` API contract.

## Feedback/Admin Layer

The product has a lightweight feedback loop:

- Student home page includes a feedback button.
- The feedback form stores submitted text in SQLite.
- Admin page requires sign-in before protected admin controls are shown.
- Admin sign-in uses username, password, and a short arithmetic captcha.
- Admin sessions are held by the Node server with bearer tokens.
- Admin feedback panel lists feedback items from SQLite.
- Favorite feedback is shown first, preserving existing favorite order.
- Remove deletes the feedback row from the database.

SQLite tables:

- `admin_users`
- `user_feedback`

Python bridge/service:

- `student_planner.web.app_data`
- `scripts/web_app_api_bridge.py`

The default admin account is seeded as a hashed PBKDF2 credential, not a
plaintext password.

## Latest Cleanup

The external schedule experiment and weekly schedule UI were removed:

- no external schedule provider,
- no schedule domain model,
- no schedule API endpoint,
- no weekly schedule React components,
- no schedule-specific tests,
- no external schedule plan document.

Course colors remain as a local UI affordance for route readability; they are
not connected to any external schedule source.
