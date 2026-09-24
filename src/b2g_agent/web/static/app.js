const appState = {
  scenario: null,
  role: null,
  session: null,
  latestRun: null,
  finalPlan: null,
};

const roleLabels = {
  building_engineer: "Building Engineer",
  distribution_power_engineer: "Distribution Power Engineer",
};

const parameterLabels = {
  cooling_setpoint_c: ["Cooling setpoint", "°C"],
  building_count: ["Building program", "homes"],
  retrofit_level: ["Retrofit", ""],
  pv_kw_per_building: ["PV per building", "kW"],
  demand_response_pct: ["Demand response", "%"],
  target_bus: ["Connection", ""],
  transformer_capacity_kva: ["Transformer", "kVA"],
  line_capacity_kw: ["Line capacity", "kW"],
};

document.addEventListener("DOMContentLoaded", initialize);

async function initialize() {
  bindEvents();
  try {
    const [health, scenario] = await Promise.all([
      requestJSON("/api/health"),
      requestJSON("/api/scenario"),
    ]);
    appState.scenario = scenario;
    document.querySelector("#service-status").textContent = `${health.service} ${health.version} · local service online`;
    document.querySelector("#service-dot").classList.add("online");
    populateScenario(scenario);
  } catch (error) {
    showToast(`Could not connect to the local service: ${error.message}`, true);
    document.querySelector("#service-status").textContent = "Local service unavailable";
  }
}

function bindEvents() {
  document.querySelectorAll(".role-card").forEach((button) => {
    button.addEventListener("click", () => selectRole(button.dataset.role));
  });
  document.querySelector("#accept-brief").addEventListener("change", (event) => {
    document.querySelector("#enter-room").disabled = !event.target.checked;
  });
  document.querySelector("#enter-room").addEventListener("click", enterRoom);
  document.querySelectorAll("[data-back]").forEach((button) => {
    button.addEventListener("click", () => showStage(Number(button.dataset.back)));
  });
  document.querySelector("#composer").addEventListener("submit", sendMessage);
  document.querySelector("#message-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      document.querySelector("#composer").requestSubmit();
    }
  });
  document.querySelector("#rerun-button").addEventListener("click", runCurrentCase);
  document.querySelector("#review-button").addEventListener("click", finalizePlan);
  document.querySelector("#download-report").addEventListener("click", downloadReport);
}

function populateScenario(scenario) {
  document.querySelector("#scenario-summary").textContent = scenario.summary;
  document.querySelector("#simulation-note").textContent = scenario.simulation_note;
  replaceList("#constraint-list", scenario.hard_constraints);
}

function selectRole(role) {
  appState.role = role;
  const counterpart = role === "building_engineer" ? "distribution_power_engineer" : "building_engineer";
  const roleInfo = appState.scenario.user_roles.find((item) => item.id === role);
  const counterpartInfo = appState.scenario.user_roles.find((item) => item.id === counterpart);
  document.querySelector("#selected-role-badge").textContent = roleLabels[role];
  document.querySelector("#mission-title").textContent = roleLabels[role];
  document.querySelector("#mission-text").textContent = roleInfo.mission;
  document.querySelector("#counterpart-text").textContent = `${roleLabels[counterpart]} — ${counterpartInfo.mission}`;
  document.querySelector("#accept-brief").checked = false;
  document.querySelector("#enter-room").disabled = true;
  showStage(2);
}

async function enterRoom() {
  if (!appState.role) return;
  const button = document.querySelector("#enter-room");
  setBusy(button, true, "Opening room");
  try {
    appState.session = await requestJSON("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ role: appState.role }),
    });
    appState.latestRun = appState.session.runs.at(-1);
    renderWorkspace(appState.session);
    showStage(3);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false, "Enter co-design room →");
  }
}

function renderWorkspace(snapshot) {
  renderParticipants(snapshot);
  renderMessages(snapshot.messages, true);
  renderParameters(snapshot.parameters);
  renderRun(snapshot.runs.at(-1), snapshot.runs.length);
  renderLedger(snapshot.decision_ledger);
  document.querySelector("#backend-pill").textContent = humanizeBackend(snapshot.llm_backend);
}

function renderParticipants(snapshot) {
  const row = document.querySelector("#participant-row");
  row.replaceChildren();
  row.append(
    element("span", "participant-chip user", `You · ${roleLabels[snapshot.user_role]}`),
    element("span", "participant-chip mediator", "B2G-Agent · mediator"),
    element("span", "participant-chip", `AI · ${roleLabels[snapshot.counterpart_role]}`),
  );
}

function renderMessages(messages, replace = false) {
  const container = document.querySelector("#messages");
  if (replace) container.replaceChildren();
  messages.forEach((message) => {
    if (container.querySelector(`[data-message-id="${message.message_id}"]`)) return;
    const wrapper = element("article", `message ${message.speaker}`);
    wrapper.dataset.messageId = message.message_id;
    const initials = message.speaker === "mediator" ? "B2G" : message.speaker === "user" ? "YOU" : "AI";
    const speakerName = message.speaker === "mediator"
      ? "B2G-Agent · mediator"
      : message.speaker === "user"
        ? `You · ${roleLabels[appState.session.user_role]}`
        : `AI · ${roleLabels[appState.session.counterpart_role]}`;
    const avatar = element("div", "message-avatar", initials);
    const body = element("div", "message-body");
    body.append(element("div", "message-meta", speakerName), element("div", "message-bubble", message.text));
    wrapper.append(avatar, body);
    container.append(wrapper);
  });
  container.scrollTop = container.scrollHeight;
}

async function sendMessage(event) {
  event.preventDefault();
  if (!appState.session) return;
  const input = document.querySelector("#message-input");
  const text = input.value.trim();
  if (!text) return;

  const optimistic = {
    message_id: `local-${Date.now()}`,
    speaker: "user",
    role: appState.role,
    text,
  };
  renderMessages([optimistic]);
  input.value = "";
  const sendButton = document.querySelector(".send-button");
  setBusy(sendButton, true, "Thinking");
  try {
    const turn = await requestJSON(`/api/sessions/${appState.session.session_id}/messages`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    document.querySelector(`[data-message-id="${optimistic.message_id}"]`)?.remove();
    renderMessages(turn.messages);
    appState.session.parameters = turn.parameters;
    appState.session.decision_ledger = turn.decision_ledger;
    appState.session.llm_backend = turn.llm_backend;
    if (turn.simulation_run) {
      appState.latestRun = turn.simulation_run;
      appState.session.runs.push(turn.simulation_run);
      renderRun(turn.simulation_run, appState.session.runs.length);
    }
    renderParameters(turn.parameters);
    renderLedger(turn.decision_ledger);
    document.querySelector("#backend-pill").textContent = humanizeBackend(turn.llm_backend);
  } catch (error) {
    document.querySelector(`[data-message-id="${optimistic.message_id}"]`)?.remove();
    input.value = text;
    showToast(error.message, true);
  } finally {
    setBusy(sendButton, false, "Send ↑");
    input.focus();
  }
}

async function runCurrentCase() {
  if (!appState.session) return;
  const button = document.querySelector("#rerun-button");
  setBusy(button, true, "Running");
  try {
    const run = await requestJSON(`/api/sessions/${appState.session.session_id}/simulate`, { method: "POST" });
    appState.latestRun = run;
    const snapshot = await requestJSON(`/api/sessions/${appState.session.session_id}`);
    appState.session = snapshot;
    renderRun(run, snapshot.runs.length);
    renderLedger(snapshot.decision_ledger);
    showToast(`Coupled run ${run.run_id} completed.`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false, "Run current case");
  }
}

function renderParameters(parameters) {
  const list = document.querySelector("#parameter-list");
  list.replaceChildren();
  Object.entries(parameters).forEach(([key, value]) => {
    const [label, unit] = parameterLabels[key] || [key, ""];
    const item = element("div");
    item.append(element("dt", "", label), element("dd", "", `${formatValue(value)} ${unit}`.trim()));
    list.append(item);
  });
}

function renderRun(run, runCount = 1) {
  if (!run) return;
  appState.latestRun = run;
  const metrics = run.metrics;
  document.querySelector("#metric-voltage").textContent = Number(metrics.minimum_voltage_pu).toFixed(3);
  document.querySelector("#metric-line").textContent = Number(metrics.maximum_line_loading_pct).toFixed(1);
  document.querySelector("#metric-transformer").textContent = Number(metrics.maximum_transformer_loading_pct).toFixed(1);
  document.querySelector("#metric-peak").textContent = Number(metrics.feeder_peak_kw).toFixed(0);
  document.querySelector("#run-count").textContent = `${runCount} ${runCount === 1 ? "run" : "runs"}`;
  const badge = document.querySelector("#feasibility-badge");
  badge.className = `feasibility-badge ${metrics.feasible ? "feasible" : "risk"}`;
  badge.textContent = metrics.feasible ? "Feasible" : "Needs revision";
  drawLoadChart(run.timeseries);
}

function drawLoadChart(points) {
  const canvas = document.querySelector("#load-chart");
  const bounds = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(300, bounds.width);
  const height = Math.max(120, bounds.height);
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, width, height);

  const pad = { left: 8, right: 8, top: 10, bottom: 16 };
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;
  const maxLoad = Math.max(...points.map((point) => point.feeder_kw)) * 1.08;

  ctx.strokeStyle = "#e4ebf2";
  ctx.lineWidth = 1;
  [0.25, 0.5, 0.75].forEach((fraction) => {
    const y = pad.top + chartHeight * fraction;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
  });

  const gradient = ctx.createLinearGradient(0, pad.top, 0, height - pad.bottom);
  gradient.addColorStop(0, "rgba(23, 105, 224, 0.28)");
  gradient.addColorStop(1, "rgba(23, 105, 224, 0.01)");
  const coordinates = points.map((point, index) => ({
    x: pad.left + (index / (points.length - 1)) * chartWidth,
    y: pad.top + chartHeight - (point.feeder_kw / maxLoad) * chartHeight,
  }));
  ctx.beginPath();
  coordinates.forEach((point, index) => index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y));
  ctx.lineTo(coordinates.at(-1).x, height - pad.bottom);
  ctx.lineTo(coordinates[0].x, height - pad.bottom);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.beginPath();
  coordinates.forEach((point, index) => index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y));
  ctx.strokeStyle = "#1769e0";
  ctx.lineWidth = 2.4;
  ctx.stroke();

  ctx.fillStyle = "#8b9aaa";
  ctx.font = "8px system-ui";
  ctx.fillText("00", pad.left, height - 3);
  ctx.fillText("12", pad.left + chartWidth / 2 - 4, height - 3);
  ctx.fillText("23", width - pad.right - 10, height - 3);
}

function renderLedger(items) {
  const list = document.querySelector("#decision-ledger");
  replaceListElement(list, items.length ? items.slice(-6) : ["No negotiated decisions yet."]);
}

async function finalizePlan() {
  if (!appState.session) return;
  const button = document.querySelector("#review-button");
  setBusy(button, true, "Preparing review");
  try {
    const plan = await requestJSON(`/api/sessions/${appState.session.session_id}/finalize`, { method: "POST" });
    appState.finalPlan = plan;
    renderFinalPlan(plan);
    showStage(4);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false, "Review plan →");
  }
}

function renderFinalPlan(plan) {
  const run = plan.selected_run;
  const metrics = run.metrics;
  const status = document.querySelector("#review-status");
  status.textContent = plan.status === "ready" ? "Ready for professional review" : "Revision required";
  status.className = `review-status ${plan.status === "ready" ? "" : "risk"}`;
  document.querySelector("#final-summary").textContent = plan.summary;
  document.querySelector("#building-score").textContent = `${metrics.building_satisfaction_score.toFixed(1)}/100`;
  document.querySelector("#grid-score").textContent = `${metrics.grid_reliability_score.toFixed(1)}/100`;
  document.querySelector("#capital-cost").textContent = `$${metrics.estimated_capital_cost_kusd.toFixed(0)}k`;
  const scoreBars = document.querySelectorAll(".score-row i");
  scoreBars[0].style.setProperty("--score-width", `${metrics.building_satisfaction_score}%`);
  scoreBars[1].style.setProperty("--score-width", `${metrics.grid_reliability_score}%`);
  replaceList("#accepted-decisions", plan.accepted_decisions);
  replaceList("#unresolved-items", plan.unresolved_items.length ? plan.unresolved_items : ["No unresolved hard constraints in the selected candidate."]);
  document.querySelector("#report-markdown").textContent = plan.report_markdown;
  renderFinalConstraints(metrics);
}

function renderFinalConstraints(metrics) {
  const container = document.querySelector("#final-constraints");
  container.replaceChildren();
  const constraints = [
    ["Minimum voltage ≥ 0.95 p.u.", metrics.minimum_voltage_pu.toFixed(3), metrics.minimum_voltage_pu >= 0.95],
    ["Maximum line loading ≤ 100%", `${metrics.maximum_line_loading_pct.toFixed(1)}%`, metrics.maximum_line_loading_pct <= 100],
    ["Maximum transformer loading ≤ 100%", `${metrics.maximum_transformer_loading_pct.toFixed(1)}%`, metrics.maximum_transformer_loading_pct <= 100],
  ];
  constraints.forEach(([label, value, pass]) => {
    const row = element("div", "constraint-row");
    row.append(element("span", "", label), element("strong", "", value), element("b", pass ? "" : "fail", pass ? "Pass" : "Fail"));
    container.append(row);
  });
}

function downloadReport() {
  if (!appState.finalPlan) return;
  const blob = new Blob([appState.finalPlan.report_markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `b2g-agent-${appState.session.session_id}-final-plan.md`;
  link.click();
  URL.revokeObjectURL(url);
}

function showStage(number) {
  document.querySelectorAll(".stage").forEach((stage) => stage.classList.remove("active"));
  document.querySelector(`#stage-${number}`).classList.add("active");
  document.querySelectorAll(".progress-step").forEach((step) => {
    const value = Number(step.dataset.step);
    step.classList.toggle("active", value === number);
    step.classList.toggle("complete", value < number);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function requestJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch (_) {
    // A non-JSON provider or proxy error is handled below.
  }
  if (!response.ok) {
    throw new Error(payload?.detail || `Request failed with status ${response.status}`);
  }
  return payload;
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  button.textContent = label;
  button.classList.toggle("loading", busy);
}

function replaceList(selector, items) {
  replaceListElement(document.querySelector(selector), items);
}

function replaceListElement(list, items) {
  list.replaceChildren();
  items.forEach((item) => list.append(element("li", "", item)));
}

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== "") node.textContent = text;
  return node;
}

function formatValue(value) {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(1);
  return String(value).replaceAll("_", " ");
}

function humanizeBackend(value) {
  if (!value) return "Mediator ready";
  if (value.startsWith("openai:")) return `LLM mediator · ${value.split(":")[1]}`;
  return "Offline fallback mediator";
}

let toastTimer;
function showToast(message, error = false) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.className = `toast show ${error ? "error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.className = "toast"; }, 4200);
}
