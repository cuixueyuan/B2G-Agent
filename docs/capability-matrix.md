# Simulator Capability Matrix

An MCP server's existence does not guarantee that every B2G-Agent decision can be executed safely. This matrix separates implemented behavior, existing legacy paths, and integration work that still requires verification.

| User-level action | Structured object | Current vertical backend | Legacy direct path | Target MCP path | Status / verification |
|---|---|---|---|---|---|
| Change cooling setpoint | `cooling_setpoint_c` | Deterministic load response | Not implemented | EnergyPlus-MCP schedule/setpoint extension | **Gap:** add IDF diff and output regression tests |
| Change building count | `building_count` | Implemented | Load scaling | B2G coupling layer | Implemented for the vertical scenario |
| Select retrofit level | `retrofit_level` | Deterministic multiplier | Not implemented | EnergyPlus-MCP envelope/HVAC tools | Partial; map to explicit measures |
| Add rooftop PV | `pv_kw_per_building` | Implemented | Not implemented | EnergyPlus + OpenDSS/PVSystem workflow | Requires consistent behind-the-meter treatment |
| Add demand response | `demand_response_pct` | Implemented | Not implemented | EnergyPlus schedules or post-processed load contract | Requires schedule and rebound policy |
| Change connection bus | `target_bus` | Implemented | OpenDSS load edit | PowerMCP/OpenDSS | Verify target existence and phase compatibility |
| Change transformer capacity | `transformer_capacity_kva` | Implemented | Not implemented | PowerMCP/OpenDSS transformer edit | Audit tool support and rating semantics |
| Change line capacity | `line_capacity_kw` | Implemented proxy | Reads `NormAmps` | PowerMCP/OpenDSS line edit | Replace kW proxy with conductor/ampacity model |
| Run 24-hour building model | Scenario run | Implemented surrogate | Real EnergyPlus single-building path | EnergyPlus-MCP | Validate weather, timestep, meter, and run status |
| Run grid snapshots | Scenario run | Implemented surrogate | OpenDSSDirect snapshots | PowerMCP/OpenDSS | Extend to QSTS and preserve convergence diagnostics |
| Produce final joint report | `FinalPlan` | Implemented | Markdown report | B2G orchestration layer | Implemented; add real-backend provenance |

## Acceptance Rule For A New Capability

A capability is not marked production-ready until it has:

1. a typed input schema and units;
2. a supported MCP tool or deterministic adapter;
3. a pre-execution validation check;
4. an input/model diff;
5. simulator success and convergence checks;
6. result extraction with units and provenance;
7. a regression test against a known case;
8. a user-facing explanation of limitations.
