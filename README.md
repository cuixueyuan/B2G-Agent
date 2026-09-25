# B2G-Agent

**An LLM-mediated research environment for building-grid co-design.**

B2G-Agent helps Building Engineers and Distribution Power Engineers collaborate without requiring either person to master the other discipline's terminology or simulation workflow. A human selects one role, an LLM plays the other role as an AI counterpart, and B2G-Agent interprets free-form input, translates professional implications, runs a transparent scenario model, and records the path to a joint plan.

![B2G-Agent concept: an AI mediator connecting building and power engineers](docs/assets/b2g-agent-concept.png)

## Research Scenarios

The local application now provides two selectable scenarios:

### 1. Harborview Residential Renewal

The two engineers coordinate an 80-home expansion and retrofit program. They negotiate comfort, retrofit level, rooftop PV, peak flexibility, connection location, transformer capacity, and feeder capacity while checking voltage and thermal limits.

### 2. Harborview Demand Response Service

The two engineers prepare a civic building for a utility demand-response service. They must agree on:

- a defensible counterfactual baseline method;
- any justified baseline adjustment;
- the event start time and duration;
- a realistic kW reduction commitment per building;
- comfort and controllable-load implications;
- post-event rebound limits;
- measurable delivery and feeder benefit.

The deterministic research backend reports baseline peak, baseline confidence, delivered reduction, delivery percentage, rebound, voltage, and equipment loading. It is not a settlement-grade baseline or calibrated building-controls model.

## Four-Stage Interface

1. Choose to participate as the Building Engineer or Distribution Power Engineer.
2. Choose one of the two research scenarios and review its responsibilities and evidence boundary.
3. Negotiate with the AI counterpart in the mediated co-design room.
4. Review the selected candidate, constraint checks, unresolved items, and reproducible Markdown report.

| 1. Choose an engineering role | 2. Choose and review a scenario |
|---|---|
| ![Choose between Building Engineer and Distribution Power Engineer](docs/assets/screenshots/01-role-selection.png) | ![Choose between the residential-renewal and demand-response scenarios](docs/assets/screenshots/02-project-brief.png) |

| 3. Enter the co-design room | 4. Review the joint plan |
|---|---|
| ![Three-way co-design room with shared demand-response evidence](docs/assets/screenshots/03-codesign-room.png) | ![Final decision package and demand-response acceptance checks](docs/assets/screenshots/04-final-review.png) |

## Local Installation With Your Own API Key

Python 3.11 or newer and Git are required. Every interactive session requires the tester's own OpenAI API key; B2G-Agent will refuse to create a session when the key is missing or still contains the example placeholder.

### Windows PowerShell

```powershell
git clone https://github.com/cuixueyuan/B2G-Agent.git
Set-Location B2G-Agent
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
notepad .env
```

### macOS or Linux

```bash
git clone https://github.com/cuixueyuan/B2G-Agent.git
cd B2G-Agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` and replace the placeholder with your own key:

```dotenv
OPENAI_API_KEY=replace_with_your_actual_api_key
B2G_MODEL=gpt-4.1-mini
B2G_LLM_ENABLED=true
B2G_REQUIRE_LLM=true
```

Start the local application:

```text
b2g-web
```

Open <http://127.0.0.1:8000>. The co-design room should display `LLM mediator · gpt-4.1-mini`. If session creation reports that an API key is required, stop the process with `Ctrl+C`, correct `.env`, and restart it.

The real `.env` is ignored by Git. Never paste the key into browser JavaScript, source files, screenshots, issues, or commits. See the [complete local deployment guide](docs/local-deployment.md) for verification and troubleshooting.

## Interaction Model

```text
Free-form engineer message
        ↓
Role- and scenario-aware LLM interpretation
        ↓
Validated parameter/action schema ──→ clarification or confirmation
        ↓
Scenario-specific evidence execution
        ↓
Audience-specific translation + AI counterpart response
        ↓
Decision ledger → candidate comparison → final human review
```

The LLM interprets intent and writes explanations; deterministic code validates parameter names and ranges, executes the scenario equations, and calculates engineering metrics. The LLM is not allowed to invent simulation results.

## Tool And Attribution Status

This table distinguishes software that the current release actually executes from tools that are cited as future integration targets.

| Tool or project | Current status in B2G-Agent | Purpose |
|---|---|---|
| [OpenAI Python SDK](https://github.com/openai/openai-python) | **Used** | Calls the tester-selected OpenAI model from the local Python server. |
| [FastAPI](https://github.com/fastapi/fastapi) | **Used** | Provides the local HTTP API and serves the browser interface. |
| [Uvicorn](https://github.com/encode/uvicorn) | **Used** | Runs the local ASGI service started by `b2g-web`. |
| [Pydantic](https://github.com/pydantic/pydantic) | **Used** | Validates LLM plans, scenario parameters, sessions, and reports. |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | **Used** | Loads the tester's local `.env` without exposing it to the browser. |
| [EnergyPlus-MCP](https://github.com/LBNL-ETA/EnergyPlus-MCP) | **Cited; not integrated** | Planned EnergyPlus model inspection, modification, execution, and result extraction. It is not installed, imported, or called by this release. |
| [PowerMCP](https://github.com/Power-Agent/PowerMCP) from the Power-Agent project | **Cited; not integrated** | Planned OpenDSS and power-system tool orchestration. It is not installed, imported, or called by this release. |
| EnergyPlus and OpenDSS | **Not executed** | Future validated physics backends. Current metrics come from B2G-Agent's transparent deterministic research equations. |

External projects retain their own licenses and attribution. No EnergyPlus-MCP or PowerMCP source code is vendored into this repository.

## Architecture

```text
Browser interface
  └─ Local FastAPI service
      ├─ Role + research-scenario selection
      ├─ OpenAI-based mediator and AI counterpart
      ├─ Typed shared case state
      ├─ Residential-renewal research model
      ├─ Demand-response baseline and event model
      ├─ Decision ledger and candidate selection
      └─ Reproducible Markdown report

Planned adapters, not active in this release
  ├─ EnergyPlus-MCP
  └─ PowerMCP / OpenDSS
```

See [architecture.md](docs/architecture.md), [research-scenarios.md](docs/vertical-scenario.md), [capability-matrix.md](docs/capability-matrix.md), and [security.md](docs/security.md).

## API Endpoints

- `GET /api/health` — local service status.
- `GET /api/scenarios` — role information and two-scenario catalog.
- `GET /api/scenarios/{scenario_id}` — selected scenario brief and decision space.
- `POST /api/sessions` — create a role- and scenario-aware session.
- `POST /api/sessions/{id}/messages` — mediate one free-form turn.
- `POST /api/sessions/{id}/simulate` — rerun the current shared case.
- `POST /api/sessions/{id}/finalize` — select and report the best available candidate.

Interactive API documentation is available at `/docs` while the local service is running.

## Testing

Tests use fake mediator objects and never require a real API key:

```text
python -m pytest -q
```

The suite covers both scenario models, parameter validation, mediated sessions, final reports, API routes, and secret-safe configuration.

## Repository Layout

```text
src/b2g_agent/
  collaboration/       # roles, scenarios, LLM mediator, simulation, and sessions
  web/                 # FastAPI service and four-stage browser interface
docs/                  # architecture, capabilities, security, screenshots, and setup
tests/                 # deterministic unit and API tests
```

The earlier `single-building-to-grid` and `building-cluster-to-grid` samples and their dedicated workflow code were removed in v0.3.0 because they were not part of the current mediated collaboration product.

## Research Boundary And Roadmap

The included equations are auditable workflow surrogates, not professional planning, settlement, or operational models. Human engineers retain approval responsibility.

Next validation stages:

- connect thermostat, schedules, loads, and event controls through EnergyPlus-MCP;
- connect feeder compilation, equipment changes, QSTS, and convergence checks through PowerMCP/OpenDSS;
- compare simulated baselines with interval-meter methods and program settlement rules;
- add a real two-human collaboration mode;
- evaluate translation accuracy, tool selection, agreement quality, reproducibility, and professional trust.

## Citation

```bibtex
@software{b2g_agent,
  title  = {B2G-Agent: An LLM-Mediated Research Environment for Building--Grid Co-Design},
  author = {Xueyuan Cui},
  year   = {2026},
  url    = {https://github.com/cuixueyuan/B2G-Agent}
}
```

## License

Released under the MIT License. External projects are governed by their respective licenses.
