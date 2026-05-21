# Healthy Work App

Windows desktop MVP for healthier work habits.

This repository has the project skeleton, data layer, pure statistics/scoring logic, pure timer state machine, the PyQt5 main window, break-record persistence, and the end-of-day report dialog.

## Planned MVP

- Rest reminder interval setting
- Countdown timer with pause and restart
- Early break from the working or paused state
- Break reminder dialog
- Automatic break timing
- Break records with water intake and optional notes
- Today statistics
- End-of-day report
- Rule-based health score
- Local JSON storage

## Planned Tech Stack

- Python
- PyQt5
- JSON file storage

## Run The Current UI

From the repository root:

```powershell
pip install -r requirements.txt
python -m app.main
```

The current UI is connected to `WorkTimer`, can save completed break records to `data/daily_records.json`, and can generate/save an end-of-day `DailySummary`.
On startup, the UI loads today's saved break records and work minutes once, initializes the timer as `Idle`, and displays today's totals immediately.
The PyQt5 UI enables Windows high-DPI scaling, uses a rounded Windows font stack for readability, and keeps the main content in a resizable scrollable window.

## Data Storage

The MVP stores local records in `data/daily_records.json`.

Current storage responsibilities:

- Create the JSON file automatically when it does not exist
- Back up invalid JSON files with an `.invalid-YYYYMMDD-HHMMSS.json` suffix
- Store app settings, break records, daily summaries, and per-day work minutes
- Validate basic data shapes before saving

## Timer State Machine

The core timer is UI-independent and lives in `app/core/timer.py`.

Supported states:

- `Idle`
- `Working`
- `Paused`
- `Reminder`
- `Breaking`
- `DayEnded`

Only `Working` counts toward total work time. `Paused`, `Reminder`, and `Breaking` do not count as work time. Completing a break returns a `CompletedBreak` object with start time, end time, duration seconds, and rounded-up duration minutes.

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
