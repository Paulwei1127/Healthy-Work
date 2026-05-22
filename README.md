# Healthy Work App

Windows desktop MVP for healthier work habits.

This repository has the project skeleton, data layer, pure statistics/scoring logic, pure timer state machine, the PyQt5 main window, break-record persistence, and the end-of-day report dialog.

## Planned MVP

- Rest reminder interval setting
- Countdown timer with pause and restart
- Early break from the working or paused state
- Active break reminder dialog when time is up
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
- PyQtWebEngine for optional Lottie animation playback
- JSON file storage

## Run The Current UI

From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m app.main
```

The current UI is connected to `WorkTimer`, can save completed break records to `data/daily_records.json`, and can generate/save an end-of-day `DailySummary`.
On startup, the UI loads today's saved break records and work minutes once, initializes the timer as `Idle`, and displays today's totals immediately.
The PyQt5 UI enables Windows high-DPI scaling, uses a rounded Windows font stack for readability, and keeps the main content in a resizable scrollable window.
Work minutes are saved periodically, and the app checks for date rollover while running.
Rest interval settings are editable outside the active `Working` countdown and are saved when the input edit is finished. Invalid interval input is rejected and restored to the last valid value.
The main timer card and the break reminder dialog prefer Lottie JSON animations from `gif/json` through PyQtWebEngine and the bundled offline `gif/json/lottie.min.js` player. If PyQtWebEngine, the local Lottie player, or a JSON animation is unavailable, the UI falls back to the existing GIF animations in `gif` without blocking the timer or reminder flow.

When packaging with PyInstaller, include the full `gif/` folder, including `gif/json/lottie.min.js`, all Lottie JSON files, and all GIF fallback files.

## Health Scoring

The health score uses rule-based local logic, without an AI API.

- Water targets scale with recorded work time instead of using one fixed daily threshold. The basic target is `1500 ml / 16 waking hours` (about 94 ml per work hour), and the ideal target is `2000 ml / 16 waking hours` (125 ml per work hour). There is no daily cap; long workdays scale proportionally.
- Formal health scores are shown only when there is enough work data. If no work has been recorded, the report shows `今天尚未工作`; if recorded work is under 30 minutes, it shows `資料較少，暫不評分`; at 30 minutes or more, it shows the normal `X / 100` score.
- Older saved summaries may still contain a numeric health score, but reports still apply the current display rule first: under 30 recorded work minutes shows `今天尚未工作` or `資料較少，暫不評分` instead of a misleading score.
- Very short work sessions under 30 minutes do not receive a heavy water penalty.
- The rest rhythm goal is to avoid any continuous work session longer than 60 minutes. The app records precise `WorkSessionRecord` entries when work starts and truly ends through pause, break, restart, end day, date rollover, or app close. Health scoring uses the longest recorded work session first.
- Reminder is only a prompt, not a break. Staying on the reminder screen does not split a work session, and snooze also does not split it. Reminder wait time is not counted as work seconds, but the open session is kept until you actually pause, rest, restart, end the day, cross dates, or close the app.
- `average_work_session_minutes` remains for old data compatibility and auxiliary display. It is used only as an explicit estimate when no precise work session records are available.
- Reports use friendly missing-data text such as `今天尚未工作` or `尚無工作區段紀錄` instead of engineering placeholders like `N/A`.
- Total break time is a secondary target based on work duration: at least 5 minutes of break time per recorded work hour.
- Suggestions include the recorded work duration, basic and ideal water targets, actual water intake, estimated work rhythm, and proportional break-time target.

## Test

```powershell
python -m pytest
```

The tests cover timer elapsed ticks, storage settings/work minutes, statistics date filtering, reminder prompt deduplication, and basic UI persistence flows.

## Future Enhancements

- Quick water-only record button
- System tray minimize behavior
- Optional startup-on-login setting
- Optional richer sound or Windows notification integration

## Data Storage

The MVP stores local records in `data/daily_records.json`.

Current storage responsibilities:

- Create the JSON file automatically when it does not exist
- Back up invalid JSON files with an `.invalid-YYYYMMDD-HHMMSS.json` suffix
- Store app settings, break records, work session records, daily summaries, and per-day work minutes
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
