# B2G-Agent

**An LLM-mediated research environment for building-grid co-design.**

B2G-Agent helps Building Engineers and Distribution Power Engineers collaborate without requiring either person to master the other discipline's terminology or simulation workflow. A human selects one role, an LLM plays the other role as an AI counterpart, and B2G-Agent interprets free-form input, translates professional implications, runs a transparent scenario model, and records the path to a joint plan.

![B2G-Agent concept: an AI mediator connecting building and power engineers](docs/assets/b2g-agent-concept.png)

## Core Functions

B2G-Agent is designed as the third participant in a Building Engineer–Power Engineer dialogue: translator, software operator, conversation governor, and technical secretary. Its main functions are:

### 1. Cross-Domain Professional Translation

- **Language translation:** explain building terminology in the power engineer's decision context, and power-system terminology in the building engineer's decision context.
- **Model translation:** convert free-form professional opinions into a typed, validated shared case instead of requiring either engineer to edit simulation inputs manually.
- **Impact translation:** turn model evidence into consequences the other engineer can act on—for example, translating a comfort or controls proposal into load, voltage, capacity, delivery, or rebound implications.

### 2. Natural-Language Software Delegation

The engineers express goals, constraints, preferences, and proposed changes in ordinary professional language. The LLM interprets the message, decides whether clarification, confirmation, or new evidence is needed, and creates a structured action plan. Deterministic code validates every allowed parameter before any scenario calculation is executed; the LLM is not allowed to invent engineering metrics.

### 3. Evidence And Tool Orchestration

B2G-Agent determines whether a turn requires building-side analysis, grid-side analysis, or a coupled run, then returns the evidence in language appropriate to both roles. **The current v0.3 research release executes B2G-Agent's built-in deterministic residential-renewal and demand-response models.** Its intended validated software layer is EnergyPlus through EnergyPlus-MCP and OpenDSS/power-system analysis through PowerMCP; those external adapters are clearly marked as planned and are not yet called by this release.

### 4. AI Counterpart And Conversation Governance

When only one human is available, the LLM plays the other engineering role as a scenario-constrained NPC. The mediator preserves each discipline's priorities, asks focused questions, requires confirmation for material changes, tracks unresolved constraints, and guides the discussion toward a jointly acceptable plan rather than producing an isolated answer.

### 5. Traceability And Human Approval

Each session maintains shared parameters, messages, simulation runs, a decision ledger, constraint checks, and a reproducible Markdown report. Human engineers retain responsibility for final approval; the prototype does not present its built-in equations as a calibrated EnergyPlus/OpenDSS engineering study or a settlement-grade demand-response baseline.

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

Pages 3 and 4 provide a clear return path to page 1, so a tester can start a fresh session with a different role or scenario. Completed session artifacts remain saved locally.

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
