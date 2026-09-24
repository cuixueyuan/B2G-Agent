# Harborview Residential Renewal

## Purpose

Harborview is a deliberately constrained vertical scenario for validating the complete B2G-Agent interaction loop before connecting large external simulation stacks. It is designed to produce meaningful building-grid trade-offs within seconds and to make every equation and decision variable inspectable.

## Scenario

A representative coastal community plans to add or renovate 80 residential buildings on a radial distribution feeder. The human participates as either a Building Engineer or Distribution Power Engineer. The counterpart is an AI NPC with scenario-defined objectives, while B2G-Agent mediates and records the process.

### Building objectives

- preserve a defensible cooling setpoint and occupant comfort;
- choose no, standard, or deep retrofit scope;
- evaluate rooftop PV and peak-period demand flexibility;
- avoid unnecessary building-side capital cost.

### Grid objectives

- maintain minimum voltage at or above 0.95 p.u.;
- keep line and transformer loading at or below 100%;
- prefer targeted upgrades and adequate operating margin;
- serve the agreed building program reliably.

## Decision Space

| Parameter | Range | Domain significance |
|---|---:|---|
| Cooling setpoint | 20–28 °C | Comfort and cooling demand |
| Building count | 10–300 | Development scale |
| Retrofit level | none / standard / deep | Envelope and HVAC demand multiplier |
| PV per building | 0–15 kW | Daytime net-load reduction |
| Demand response | 0–35% | Peak-period load reduction |
| Connection bus | bus 3–8 | Electrical distance from the source |
| Transformer capacity | 250–1500 kVA | Substation thermal headroom |
| Line capacity | 200–1500 kW | Feeder thermal headroom proxy |

## Deterministic Backend

The backend produces one 24-hour profile. Residential demand combines transparent morning, evening, appliance, envelope, and cooling shapes. Cooling demand responds to setpoint and retrofit level. PV follows a daytime production curve, while demand response reduces the 15:00–20:00 gross load with a small rebound.

The community net load is added to an existing feeder profile. Voltage drop varies by connection-bus distance. Line loading and transformer apparent-power loading are computed from the resulting feeder demand.

This formulation is intended for workflow testing and reproducible demonstrations. It is not calibrated to a particular city, building stock, weather file, feeder, or utility planning standard.

## Expected Negotiation

The baseline is intentionally near or beyond thermal limits. A participant can respond through several strategies:

- reduce demand through standard/deep retrofit;
- add demand response;
- adjust building program or comfort assumptions;
- select a closer connection point;
- increase transformer or feeder capacity;
- combine moderate building and grid interventions.

This creates a real negotiation rather than a one-click optimum. B2G-Agent selects the best available feasible run for final review using building satisfaction, grid reliability, and indicative cost; the human still decides whether to approve it.

## Promotion To Real Simulators

The vertical scenario should be promoted one capability at a time:

1. replace the load equations with EnergyPlus archetype runs;
2. validate thermostat and schedule edits through EnergyPlus-MCP;
3. standardize EnergyPlus output into the shared load contract;
4. replace radial equations with a PowerMCP/OpenDSS feeder model;
5. compare deterministic and real-simulator metrics for regression;
6. enable the real backend only after tolerance and provenance tests pass.
