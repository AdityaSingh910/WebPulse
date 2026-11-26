# WebPulse: installation guide (Windows 10 / 11)

This guide installs WebPulse on another Windows laptop. On 26 Nov 2026 it was tested end to end: a brand-new
virtual environment was created, only `requirements.txt` was installed into it (**91 s**, wheels only, no compiler
needed), and the full end-to-end suite then passed on it (**126/126**). No Docker, WSL or paid service is needed.

## 1. What you need

| Item | Version used | How to get it |
|---|---|---|
| Windows | 10 or 11 (tested on 11) | |
| Python | **3.12** (3.12.4 tested) | python.org installer; tick "Add python.exe to PATH" |
| Microsoft Edge | any current version | preinstalled on Windows; used headless for JavaScript pages |
| PowerShell | 7 (`pwsh`), as tested. Windows PowerShell 5.1 ran `run.ps1`'s safety checks correctly; a full start was only tested on 7 | Microsoft Store "PowerShell" |
| Disk | ~600 MB for the environment, a few MB for data | |
| Internet | only to install packages and to monitor real sites | |

## 2. Get the project

Copy the project folder (or `git clone` your repository) to, for example, `C:\WebPulse`. Keep the folder structure
as it is: `run.ps1` must stay next to `changedetection.py`.

## 3. Create the environment and install

```powershell
cd C:\WebPulse
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# optional, only to run the unit tests:
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`run.ps1` and the test scripts look for Python in this order, so no paths need editing:
1. `<project>\.venv\Scripts\python.exe`;
2. `%USERPROFILE%\venvs\cdio-simplified\Scripts\python.exe` (the original development location);
3. a `-Python C:\path\to\python.exe` argument.

No Playwright browser download is needed: WebPulse drives the Edge that is already installed.

## 4. Start WebPulse

```powershell
.\run.ps1
```

If Windows refuses to run scripts, run this once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or start
it with `powershell -ExecutionPolicy Bypass -File .\run.ps1`.

`run.ps1` starts three things and prints where they are:

| Service | Address | Purpose |
|---|---|---|
| WebPulse | http://127.0.0.1:5000 | open this in your browser |
| Headless Edge | 127.0.0.1:9222 | reads pages that need JavaScript |
| Demo site | 127.0.0.1:8199 | the Controlled demo |

* **Where the data lives:** `%USERPROFILE%\cdio-data\webpulse-demo`. Change it with `-Datastore D:\data\webpulse`.
* **Other options:** `-Port 5001`, `-Workers 5`, `-NoBrowser`, `-NoDemoSite`.
* **Security:** everything listens on 127.0.0.1 only, and SSRF protection is always on.

**Safety checks.** Before starting anything, `run.ps1` refuses, with a red message, when:
* the port is busy ("WebPulse is already running there", or the program and PID that use it);
* another WebPulse already uses the **same data folder** (two copies would both run the scheduler and could
  corrupt the data);
* the demo-site port is used by another program;
* Python or Edge cannot be found.

**Stopping.** Press **Ctrl+C** in the window. WebPulse saves and exits, and `run.ps1` then stops the demo site and
the headless Edge it started, including Edge's child processes.

## 5. Optional: demonstration data

Run these with WebPulse **stopped**. `setup_presentation.py` copies the data folder to `<folder>-backup-<date-time>`
first. The other two only add watches, but make your own copy of the folder if it already holds data you care about.

```powershell
.\.venv\Scripts\python.exe demo\seed_demo.py         %USERPROFILE%\cdio-data\webpulse-demo   # sandbox sites, Hacker News, python.org
.\.venv\Scripts\python.exe demo\add_demo_site.py     %USERPROFILE%\cdio-data\webpulse-demo   # the [Demo] watches + demo proxy
.\.venv\Scripts\python.exe demo\setup_presentation.py %USERPROFILE%\cdio-data\webpulse-demo  # real Indian shops and job boards
```

`demo\persistence_check.py snapshot|compare` fingerprints every watch before and after a restart, if you want to
prove persistence by hand.

## 6. Running without a visible terminal (optional)

The normal workflow is the visible window ("WebPulse backend - keep open"), which shows the live log. To run in
the background instead:

```powershell
# start hidden, with the log kept in a file
Start-Process pwsh -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command',
  "Set-Location C:\WebPulse; .\run.ps1 *>&1 | Out-File -Encoding utf8 $env:TEMP\webpulse-run.log"

# follow the log
Get-Content $env:TEMP\webpulse-run.log -Wait -Tail 20

# stop it (WebPulse, demo site and the helper Edge)
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'changedetection\.py|fixture_server\.py|cdio-edge-profile' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

Stopping it this way is a hard stop. It is safe for the saved data, because every write is atomic (temp file + rename,
verified in Phase 15), but checks still waiting in the queue are dropped. Checking continues while the browser tab is
closed: the scheduler runs inside the WebPulse process, not in the page.

**Starting at log-in (optional):** create a Task Scheduler task "At log on" whose action is
`pwsh.exe -WindowStyle Hidden -File C:\WebPulse\run.ps1`.

## 7. Check the installation

```powershell
.\e2e\run_e2e.ps1 -Browser -UI    # throw-away instances on other ports; about 4 minutes; expect "total": "126/126"
.\e2e\run_unit.ps1                # needs requirements-dev.txt; expect "NEW failures: 0"
```

The unit run reports 8 Windows-only failures, listed and explained in `e2e/known_windows_unit_failures.txt`:
* 4 symlink tests need administrator rights or Developer Mode;
* 1 test assumes Linux;
* 2 upstream tests are outdated;
* 1 test needs `fork()`.

## 8. Troubleshooting

| Message / symptom | What to do |
|---|---|
| "port 5000 is busy - WebPulse is already running there" | Open http://127.0.0.1:5000; it is already running. Or start a second copy with `-Port 5001 -Datastore <other folder>` |
| "another WebPulse ... is already using the data folder" | Stop the other copy first; never run two on one data folder |
| "Python virtual environment not found" | Do step 3, or pass `-Python` |
| JavaScript pages show "Loading..." | Edge did not start: look for the yellow warning in the window; start without `-NoBrowser` |
| A watch shows "Fetch blocked: ... private/reserved address" | Expected: WebPulse never reads local or private network addresses (SSRF protection) |
| Checks stopped overnight | The laptop slept. WebPulse catches up within a second of waking. Keep it plugged in and set sleep to "Never" for demonstrations |

## 9. Uninstall

Stop WebPulse, then delete the project folder (including `.venv`) and `%USERPROFILE%\cdio-data\webpulse-demo`. Nothing
is installed system-wide.
