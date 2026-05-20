# Healthy Work App

Windows desktop MVP for healthier work habits.

This repository is currently in the project skeleton stage only. Functional logic will be added in later approved steps.

## Planned MVP

- Rest reminder interval setting
- Countdown timer with pause and restart
- Break reminder dialog
- Automatic break timing
- Break records with water intake and optional notes
- Today statistics
- End-of-day report
- Rule-based health score
- Local JSON storage

## Planned Tech Stack

- Python
- Tkinter
- JSON file storage
- Standard library only for the initial MVP

## Project Structure

```text
app/
  main.py
  ui/
    main_window.py
    reminder_dialog.py
    report_dialog.py
  core/
    timer.py
    scoring.py
    statistics.py
  data/
    models.py
    storage.py
data/
  .gitkeep
README.md
requirements.txt
```
