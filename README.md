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
