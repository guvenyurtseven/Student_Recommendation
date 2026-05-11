# METU Student Planner Web

This folder contains the React + Node.js web prototype.

The academic planner still lives in Python. Node.js is responsible for serving
the web UI and forwarding API requests to the Python bridge:

```text
React UI -> Node/Express API -> scripts/recommendation_api_bridge.py -> Python planner
```

Transcript PDFs are sent to Node as base64 JSON, forwarded to Python, parsed in
memory, and discarded. Raw PDF bytes and raw transcript text are not stored.

## Development

Install Node.js 20+ first, then:

```powershell
cd .\web
npm install
npm run dev
```

In another terminal, run the API server:

```powershell
cd .\web
npm run server
```

For a production-like local run:

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

## Current UI Inputs

- Department
- Target semester
- Difficulty preference
- Transcript PDF or planner JSON
- Technical elective, restricted elective, non-technical elective, free elective
  preferences
- Optional concrete elective course code for each selected category
