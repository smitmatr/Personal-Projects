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

## Deploy to a Public URL (Render)

This repo now includes a deployment blueprint file at the repo root:
- render.yaml

That file is already configured to deploy this app from:
- Visual Studio/Draw Results App

### One-time setup

1. Log into Render:
   - https://render.com/
2. Click New + and choose Blueprint.
3. Connect your GitHub account/repository:
   - smitmatr/Personal-Projects
4. Render will detect render.yaml automatically.
5. Click Apply and wait for deployment to finish.

### Share with your friend

After deploy succeeds, Render gives you a URL like:
- https://alaska-draw-results-app.onrender.com

Email that URL to your friend. They can use the app in a browser with no local setup.

### Notes

- Free plans may sleep after inactivity; first load can take a moment.
- If you push new changes to main, Render can auto-redeploy.
