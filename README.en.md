# Healthy Work App

[繁體中文](README.md)

Healthy Work App is a small Windows desktop app for healthier work habits. It helps you run focused work countdowns, receive break reminders, record breaks and water intake, and review a simple end-of-day health report.

The app is built with Python, PyQt5, local JSON storage, and optional Lottie animations through PyQtWebEngine. It does not require a cloud account and does not use an AI API.

## Features

- Work countdown timer with configurable break reminder interval.
- Pause, restart countdown, early break, snooze reminder, and end-day actions.
- Active break reminder dialog when the countdown reaches zero.
- Break timer with completed break records.
- A single break record counts for at most 60 minutes to avoid polluted statistics if you forget to return to work.
- Water intake and optional note entry after a break.
- Today dashboard for work time, break time, break count, water total, current break, and last break.
- End-of-day report with health score and rule-based suggestions.
- Local work session records for detecting long continuous work sessions.
- State-based cat animations, using Lottie JSON first and GIF fallback when needed.
- Local JSON storage with basic validation and invalid-file backup.

## Download And Use

For normal users, the recommended distribution format is a Windows portable ZIP release.

1. Open this repository's **Releases** page.
2. Download the latest Windows `.zip` file from the release assets.
3. Extract the full ZIP folder before running the app.
4. Double-click the `.exe` file inside the extracted folder.
5. Keep the extracted folder contents together. The executable depends on bundled runtime and animation resources.

The ZIP version is portable and does not need installation. To remove it, close the app and delete the extracted folder.

Windows may show a SmartScreen warning for unsigned builds. That warning can appear even when the app is not malicious; it means the executable has not been code-signed by a trusted publisher.

## Run From Source

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.main
```

If your global Python environment already has the dependencies installed, this also works:

```powershell
python -m app.main
```

## Health Scoring

The health score uses rule-based local logic.

- Formal health scores are shown only when there is enough work data.
- If no work has been recorded, the report shows `今天尚未工作`.
- If recorded work is under 30 minutes, the report shows `資料較少，暫不評分`.
- At 30 minutes or more, the report shows the normal `X / 100` score.
- Water targets scale with recorded work time instead of using one fixed daily threshold.
- The basic water target is `1500 ml / 16 waking hours`, about 94 ml per work hour.
- The ideal water target is `2000 ml / 16 waking hours`, 125 ml per work hour.
- There is no daily cap; long workdays scale proportionally.
- The rest rhythm goal is to avoid any continuous work session longer than 60 minutes.
- Total break time is a secondary target based on at least 5 minutes of break time per recorded work hour.
- If a single break exceeds 60 minutes, the app warns that the break record will be counted as 60 minutes; today's statistics and reports use the capped duration.
- Older saved summaries may still contain a numeric score, but reports apply the current display rule first to avoid misleading scores.

## Animation Assets

The main timer card uses different animations for each state:

- Idle: `paws animation`
- Working: `rolling cat animation`
- Paused: `Loading Cat`
- Reminder: `Le Petit Chat _Cat_ Noir`
- Breaking: `Cat playing animation`
- Day ended: `Cat is sleeping and rolling`

The app tries to play Lottie JSON files from `gif/json` first. If PyQtWebEngine, the local `lottie.min.js` player, or a JSON animation is unavailable, it falls back to GIF files from `gif`.

Source, creator, and license information for animation assets and the bundled Lottie player are recorded in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Data Storage

When running from source, records are stored in:

```text
data/daily_records.json
```

When running from the Windows portable build, records are stored next to the executable:

```text
HealthyWork/data/daily_records.json
```

Stored data includes:

- App settings.
- Break records.
- Work session records.
- Daily summaries.
- Per-day work minutes.

This file contains user activity data and should not be committed to GitHub. The repository keeps `data/.gitkeep` only so the data folder exists.

## Packaging Notes

For the first public build, use a Windows portable ZIP created from a PyInstaller `onedir` build. Avoid `onefile` until resource loading and data persistence are fully verified.

The packaged app must include:

- The executable.
- PyQt5 and PyQtWebEngine runtime files.
- The full `gif/` folder.
- `gif/json/lottie.min.js`.
- All Lottie JSON files.
- All GIF fallback files.

Before publishing a release, verify:

- The app opens by double-clicking the executable.
- Lottie animation plays when PyQtWebEngine is available.
- GIF fallback works if Lottie cannot load.
- Work countdown, pause, reminder, snooze, break, and end-day flows work.
- Break records and water records persist after closing and reopening the app.
- End-of-day report opens and displays friendly missing-data text instead of `N/A`.

GitHub should store source code in the repository and packaged ZIP files in **GitHub Releases**. Do not commit generated `.exe`, `.zip`, local user records, virtual environments, or Python cache files.

## Development

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Current test coverage includes timer state transitions, storage behavior, statistics, scoring rules, reminder flow, animation fallback behavior, and main UI persistence flows.

## Project Structure

```text
app/
  main.py
  ui/
    animation.py
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
gif/
  json/
tests/
README.md
README.en.md
requirements.txt
```

## Platform Notes

The current project is developed and packaged on Windows. Source execution on macOS or Linux may be possible if PyQt5 and PyQtWebEngine are installed correctly, but packaged builds for those platforms have not been verified yet. For public distribution, prepare and test one build per operating system.
