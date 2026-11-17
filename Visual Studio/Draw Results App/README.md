# Matt's Working Projects Repository

This repository tracks active projects from Desktop while excluding unrelated Desktop shortcuts/files.

Tracked folders right now:
- 3D Print STL Files (includes golf ball marker files)
- Real Estate Investing (includes acquisition/deal spreadsheets)
- Contrarian Thinking

To add another Desktop folder later:
1. Add two lines in .gitignore:
   - !Folder Name/
   - !Folder Name/**
2. Run:
   git add .
   git commit -m "Add Folder Name"

## Draw Results Flask App

This folder now includes a Flask web app that shows:
- Live hunt/unit details scraped from ADF&G opportunities
- A dropdown to switch hunt codes
- In-page trend chart (permits, hunters, harvest, success %)

### Run Locally

1. Open a terminal in this folder:
   - C:\Users\mattr\OneDrive\Desktop\Visual Studio\Draw Results App
2. Create and activate a virtual environment (recommended):
   - python -m venv .venv
   - .\.venv\Scripts\Activate.ps1
3. Install dependencies:
   - pip install -r requirements.txt
4. Start the app:
   - python app.py
5. Open your browser:
   - http://127.0.0.1:5000

### Files

- app.py: Flask backend and API endpoints
- templates/index.html: main page
- static/app.js: frontend logic and chart rendering
- static/styles.css: page styling
- sheep_draw_by_area_raw.csv: local trend dataset for charting
