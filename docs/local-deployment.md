# Local Deployment Guide

This guide runs the complete four-stage B2G-Agent interface on one computer. The default offline mode requires no API key and does not require EnergyPlus or OpenDSS.

## 1. Prerequisites

- Git.
- Python 3.11 or newer.
- A modern browser such as Edge, Chrome, Firefox, or Safari.
- Optional: an OpenAI API key for free-form LLM mediation.

Verify the required commands:

```text
git --version
python --version
```

On Windows, `py -3.11 --version` can be used when `python` is not yet on `PATH`.

## 2. Clone And Create An Environment

### Windows PowerShell

```powershell
git clone https://github.com/cuixueyuan/B2G-Agent.git
Set-Location B2G-Agent
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

If PowerShell blocks activation, allow scripts only for the current terminal and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### macOS Or Linux

```bash
git clone https://github.com/cuixueyuan/B2G-Agent.git
cd B2G-Agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

## 3. Choose A Runtime Mode

### Mode A: Offline Demo

The example environment is already configured for this mode:

```dotenv
OPENAI_API_KEY=
B2G_MODEL=gpt-4.1-mini
B2G_LLM_ENABLED=false
```

Offline mode provides:

- both engineer-role choices;
- the complete four-stage interface;
- the AI counterpart and mediator using deterministic fallback responses;
- the Harborview scenario backend, metrics, constraint checks, and charts;
- decision-ledger and final Markdown report generation.

It does not send data to an LLM provider.

### Mode B: LLM Mediation

Edit `.env` and provide your own key:

```dotenv
OPENAI_API_KEY=your_own_api_key_here
B2G_MODEL=gpt-4.1-mini
B2G_LLM_ENABLED=true
```

Do not put the key in source code, browser JavaScript, screenshots, issues, or commits. The application reads it only from the local Python process. Restart the service whenever `.env` changes.

## 4. Start The Application

With the virtual environment active:

```text
b2g-web
```

Equivalent explicit launch command:

```text
python -m b2g_agent.web.cli --host 127.0.0.1 --port 8000
```

Open these local URLs:

- Interface: <http://127.0.0.1:8000>
- Health check: <http://127.0.0.1:8000/api/health>
- Interactive API documentation: <http://127.0.0.1:8000/docs>

The terminal must remain open while using the interface. Press `Ctrl+C` to stop the service.

## 5. Complete The Four Stages

1. Choose Building Engineer or Distribution Power Engineer.
2. Review the Harborview brief, counterpart role, constraints, and evidence boundary; then acknowledge the brief.
3. Enter professional judgments or proposed changes in natural language, inspect the shared case and simulation evidence, and rerun the current case when needed.
4. Select **Review plan** to inspect constraints and download the reproducible Markdown report.

Runtime session artifacts are written under `outputs/web_sessions/`. That directory is ignored by Git.

## 6. Verify The Installation

Run the automated test suite:

```text
python -m pytest -q
```

Expected result for the current release:

```text
27 passed
```

The count may increase as new tests are added; any failures should be investigated before using the research prototype.

## 7. Troubleshooting

### `b2g-web` Is Not Recognized

Confirm the virtual environment is active, then reinstall the editable package:

```text
python -m pip install -e ".[dev]"
python -m b2g_agent.web.cli
```

### Port 8000 Is Already In Use

Choose another local port:

```text
b2g-web --port 8765
```

Then open <http://127.0.0.1:8765>.

### The Status Says `Offline fallback mediator`

This is expected when `B2G_LLM_ENABLED=false` or `OPENAI_API_KEY` is empty. For LLM mediation, populate both settings and restart the service.

### The Interface Loads But Cannot Create A Session

- Check the terminal for an exception.
- Confirm that the repository directory is writable.
- Confirm that `/api/health` returns a JSON response.
- Delete no source files; runtime artifacts belong only under the ignored `outputs/` directory.

### EnergyPlus Or OpenDSS Is Missing

Neither program is required for the Harborview vertical demo. They are needed only for the legacy real-simulator workflow. See the sample documentation under `samples/single-building-to-grid/` before configuring those paths.

## 8. Update An Existing Clone

From a clean local checkout:

```text
git pull --ff-only
python -m pip install -e ".[dev]"
python -m pytest -q
```

Preserve your local `.env`; it is intentionally not tracked by Git.
