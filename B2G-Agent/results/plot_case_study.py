"""Generate the three case-study figures and print the computational-cost table.

Run with Python >= 3.10, NumPy and matplotlib from any working directory:
    python B2G-Agent/results/plot_case_study.py
    python B2G-Agent/results/plot_case_study.py --results-dir PATH_TO_FINAL_COMPARISON

All three figures are saved in the figures directory, as vector PDFs and PNG previews.
The LaTeX table is printed to the terminal; no table file is created.
Running again regenerates only this script's three named PDF outputs.

UPDATE GUIDE
-----------
The script reads reported_metrics.csv and reported_provenance.json from DEFAULT_RESULTS_DIR.
There are no embedded experimental values or fallbacks to previous versions.
To use another finalized report, change DEFAULT_RESULTS_DIR or --results-dir.
Token means use the recorded attempts per method (200 tasks x 3 = 600); the
other two costs retain the reported mean seconds per execution.

DATA AND FIGURE CONTRACT
------------------------
The selected methods are Proposed, Baseline, Translator v2, Actor v2 and
Reviewer v4, each covering the same 200 tasks x 3 repeats. Exactly 18 metric
names contain 63 applicable values; blank non-target agent cells are not zeros.
Missing, unexpected or inconsistent input raises an error before PDF export.
No live experiment, network call, fitting, resampling or extrapolation occurs.
Reviewer metrics are the final feedback-impact indicators: appropriate first
handling / 600; reverse review reach / 300 source-executable runs; final success
over the same 300. They were selected after acquisition and describe workflow
effects, not isolated diagnostic accuracy; the third overlaps with overall TSR.

Evidence logic (quantitative grid): component quality -> overall outcomes ->
agent-specific performance against the corresponding ablation. These panels
describe observed differences; they do not assume Proposed is always best.
Values are aggregate means, with no error bars or significance claims because
replicate-level variation is unavailable in the aggregate input. The figures
and table omit footnotes at the author's request.

Notation follows the metric definitions/equations in Main.tex: Q^F, Q^A,
Q^V, Q^G; Q^qua and Q^tsr; P^tra_i, P^act_i and P^rew_i. Component ticks omit
the task index e; F/A/V use all 600 runs; G uses 300 source-executable runs. Clarification G is N/A.
Overall quality is averaged per run with three or four applicable components.
The result-file F_tra/F_act/F_rew keys map to the manuscript's P symbols.

Export contract: Python/matplotlib only; 183 mm canvas, tightly cropped PDFs;
editable embedded TrueType
text, white background, consistent method colors/hatches, zero-based bar axes.
Figure 2 has independent left [0,100] and right [0,1] y scales: bar heights across
the two metric groups do not imply equal units. Figure 3 is short and wide.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator, StrMethodFormatter
import numpy as np


# The selected report is explicit; never auto-select a recent or partial run.
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent

METHOD_SPECS = (
    ("proposed", "Proposed", "full framework", ("translator", "actor", "reviewer")),
    ("baseline", "Baseline", "single agent", ()),
    ("translator_v2", "Ablation-Translator", "v2", ("translator",)),
    ("actor_v2", "Ablation-Actor", "v2", ("actor",)),
    ("reviewer_v4", "Ablation-Reviewer", "v4", ("reviewer",)),
)
AGENT_KEYS = {"translator": "tra", "actor": "act", "reviewer": "rew"}
COST_KEYS = {
    "total_tokens": "total_token_consumption",
    "llm_inference_latency_s": "llm_inference_latency",
    "retrieval_time_s": "retrieval_time",
}

# Cosmetic settings; every method keeps its color and hatch in all figures.
COLORS = ("#4C78A8", "#A2A7AD", "#E3AF68", "#7FBAAC", "#B59AC8")
HATCHES = ("", "//", "..", "\\\\", "xx")
EDGE_COLOR = "#4A4A4A"
COMPONENTS = ("Q_F", "Q_A", "Q_V", "Q_G")
COMPONENT_LABELS = (r"$Q^F$", r"$Q^A$", r"$Q^V$", r"$Q^G$")
AGENT_PANELS = (
    ("translator", "Translator", "tra", 2),
    ("actor", "Actor", "act", 3),
    ("reviewer", "Reviewer", "rew", 4),
)
PDF_NAMES = (
    "Fig-Quality_components.pdf",
    "Fig-Quality_overall.pdf",
    "Fig-Agent_performance.pdf",
)


def run_count(method: dict) -> int:
    return method["tasks"] * method["repeats"]


def load_methods(results_dir: Path = DEFAULT_RESULTS_DIR) -> list[dict]:
    """Read the final matrix; preserve missing non-target metrics as absent."""
    results_dir = Path(results_dir)
    provenance = json.loads((results_dir / "reported_provenance.json").read_text(encoding="utf-8-sig"))
    method_ids = {spec[0] for spec in METHOD_SPECS}
    if set(provenance["methods"]) != method_ids:
        raise ValueError("Provenance must describe exactly the five selected methods.")
    tasks, repeats = provenance["tasks_per_method"], provenance["repeats_per_task"]
    if type(tasks) is not int or type(repeats) is not int or min(tasks, repeats) < 1:
        raise ValueError("Provenance must record positive integer task/repeat counts.")
    if provenance["expected_attempts_per_method"] != tasks * repeats:
        raise ValueError("Provenance attempts do not match tasks * repeats.")
    if provenance["reviewer_metric_protocol"] != "reviewer-feedback-impacts-full200-20261103":
        raise ValueError("This figure requires the selected Reviewer feedback-impact definition.")
    quality_keys = (*COMPONENTS, "Q_qua", "Q_tsr")
    agent_keys = {f"F_{symbol}_{i}" for symbol in AGENT_KEYS.values() for i in (1, 2, 3)}
    expected_rows = set(quality_keys) | agent_keys | set(COST_KEYS.values())
    with (results_dir / "reported_metrics.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if (len(reader.fieldnames or []) != 6
                or set(reader.fieldnames or []) != {"metric"} | method_ids):
            raise ValueError("Expected a metric column and five selected method columns.")
        rows = {}
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed metric row or missing CSV cell.")
            key = row.pop("metric")
            if key in rows:
                raise ValueError(f"Duplicate metric row: {key}")
            rows[key] = row
    if set(rows) != expected_rows:
        raise ValueError("The final matrix must contain exactly the selected 18 metric rows.")
    methods = []
    for source_id, name, version, agents in METHOD_SPECS:
        required_agents = {f"F_{AGENT_KEYS[agent]}_{i}" for agent in agents for i in (1, 2, 3)}
        required = set(quality_keys) | required_agents | set(COST_KEYS.values())
        values = {}
        for key, row in rows.items():
            cell = row[source_id].strip()
            if key in required:
                if not cell:
                    raise ValueError(f"Missing applicable metric: {source_id}/{key}")
                values[key] = float(cell)
            elif cell:
                raise ValueError(f"Unexpected non-target agent metric: {source_id}/{key}")
        methods.append({
            "source_id": source_id, "name": name, "version": version,
            "tasks": tasks, "repeats": repeats,
            "quality": {key: values[key] for key in quality_keys},
            "quality_cohorts": provenance["quality_cohorts"][source_id],
            "agents": {agent: tuple(values[f"F_{AGENT_KEYS[agent]}_{i}"] for i in (1, 2, 3))
                       for agent in agents},
            "cost": {key: values[source_key] for key, source_key in COST_KEYS.items()},
        })
    validate_data(methods)
    for source_id in ("proposed", "reviewer_v4"):
        reviewer = next(m for m in methods if m["source_id"] == source_id)["agents"]["reviewer"]
        for i, value in enumerate(reviewer, 1):
            key = f"F_rew_{i}"
            numerator = provenance["reviewer_numerators"][source_id][key]
            denominator = provenance["reviewer_denominators"][key]
            if not 0 <= numerator <= denominator or denominator <= 0:
                raise ValueError(f"Invalid Reviewer counts: {source_id}/{key}")
            if not math.isclose(value, numerator / denominator, rel_tol=0, abs_tol=1e-12):
                raise ValueError(f"Reviewer metric differs from its audited counts: {source_id}/{key}")
    return methods


def validate_data(methods: list[dict]) -> None:
    """Reject missing, out-of-range or internally inconsistent input data."""
    expected_agents = ({"translator", "actor", "reviewer"}, set(),
                       {"translator"}, {"actor"}, {"reviewer"})
    expected_names = ("Proposed", "Baseline", "Ablation-Translator",
                      "Ablation-Actor", "Ablation-Reviewer")
    if tuple(m["name"] for m in methods) != expected_names:
        raise ValueError("Keep the required five methods in their specified order.")
    for method, agents in zip(methods, expected_agents):
        name = method["name"]
        for field in ("tasks", "repeats"):
            if type(method[field]) is not int or method[field] < 1:
                raise ValueError(f"{name}: {field} must be a positive integer.")
        quality = method["quality"]
        if set(quality) != set(COMPONENTS) | {"Q_qua", "Q_tsr"}:
            raise ValueError(f"{name}: exactly six quality metrics are required.")
        for key, value in quality.items():
            upper = 100 if key == "Q_qua" else 1
            if not math.isfinite(value) or not 0 <= value <= upper:
                raise ValueError(f"{name}: {key} must be in [0,{upper}].")
        cohorts = method["quality_cohorts"]
        executable, clarification = cohorts["executable"], cohorts["clarification"]
        n = run_count(method)
        if executable["attempts"] + clarification["attempts"] != n or clarification["G"] is not None:
            raise ValueError(f"{name}: invalid applicable cohorts.")
        derived_quality = (executable["attempts"] * 25 * sum(executable[k] for k in ("F", "A", "V", "G"))
                           + clarification["attempts"] * (100 / 3) * sum(clarification[k] for k in ("F", "A", "V"))) / n
        if not math.isclose(quality["Q_qua"], derived_quality, abs_tol=1e-10):
            raise ValueError(f"{name}: Q_qua differs from applicable-component aggregation.")
        if not math.isclose(quality["Q_G"], executable["G"], abs_tol=1e-12):
            raise ValueError(f"{name}: G differs from its applicable cohort.")
        if not math.isclose(quality["Q_tsr"], (executable["success_count"] + clarification["success_count"]) / n, abs_tol=1e-12):
            raise ValueError(f"{name}: TSR differs from its counts.")
        if set(method["agents"]) != agents:
            raise ValueError(f"{name}: agent metrics must cover {sorted(agents)}.")
        for agent, values in method["agents"].items():
            if len(values) != 3 or any(not math.isfinite(v) or not 0 <= v <= 1
                                       for v in values):
                raise ValueError(f"{name}/{agent}: three ratios are required.")
        cost = method["cost"]
        if set(cost) != {"total_tokens", "llm_inference_latency_s", "retrieval_time_s"}:
            raise ValueError(f"{name}: exactly three computational metrics are required.")
        if any(not math.isfinite(v) or v < 0 for v in cost.values()):
            raise ValueError(f"{name}: costs must be finite and nonnegative.")
        if int(cost["total_tokens"]) != cost["total_tokens"]:
            raise ValueError(f"{name}: total_tokens must be a measured integer total.")


def configure_style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "mathtext.fontset": "dejavusans",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "legend.frameon": False,
        "axes.linewidth": 0.65,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "hatch.linewidth": 0.35,
        "pdf.fonttype": 42,
        "text.usetex": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    })


def method_handles(methods, indices=range(5)) -> list[Patch]:
    return [Patch(facecolor=COLORS[i], edgecolor=EDGE_COLOR, linewidth=0.45,
                  hatch=HATCHES[i], label=methods[i]["name"]) for i in indices]


def add_legend(fig, methods, indices=range(5), *, y=0.985) -> None:
    indices = tuple(indices)
    fig.legend(handles=method_handles(methods, indices), loc="upper center",
               bbox_to_anchor=(0.5, y), ncol=len(indices),
               handlelength=1.7, handleheight=0.9, columnspacing=1.25,
               handletextpad=0.45, borderaxespad=0)


def style_axis(ax) -> None:
    ax.grid(False, which="both", axis="both")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def figure_quality_components(methods):
    """Four metric groups, each with five bars in the required method order."""
    fig, ax = plt.subplots(figsize=(183 / 25.4, 87 / 25.4))
    fig.subplots_adjust(left=0.085, right=0.985, bottom=0.16, top=0.88)
    centers = np.arange(4)
    width = 0.145
    for i, method in enumerate(methods):
        values = [method["quality"][key] for key in COMPONENTS]
        bars = ax.bar(centers + (i - 2) * width, values, width=width * 0.94,
                      color=COLORS[i], edgecolor=EDGE_COLOR, linewidth=0.45,
                      hatch=HATCHES[i], zorder=3)
        ax.bar_label(bars, labels=[f"{value:.2f}" for value in values],
                     padding=3, fontsize=6.6)
    ax.set_xticks(centers, COMPONENT_LABELS, fontsize=11)
    ax.tick_params(axis="x", length=0, pad=7)
    ax.set_xlim(-0.58, 3.58)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_locator(MultipleLocator(0.2))
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:.1f}"))
    ax.set_ylabel("Mean component score")
    style_axis(ax)
    add_legend(fig, methods)
    return fig


def figure_quality_overall(methods):
    """One score group on the left axis; one TSR group on the right axis."""
    fig, left = plt.subplots(figsize=(183 / 25.4, 87 / 25.4))
    fig.subplots_adjust(left=0.085, right=0.90, bottom=0.16, top=0.84)
    right = left.twinx()
    right.patch.set_visible(False)
    width = 0.13
    offsets = (np.arange(5) - 2) * width
    for i, method in enumerate(methods):
        common = dict(width=width * 0.94, color=COLORS[i], edgecolor=EDGE_COLOR,
                      linewidth=0.45, hatch=HATCHES[i], zorder=3)
        for ax, position, key in ((left, offsets[i], "Q_qua"),
                                  (right, 1.25 + offsets[i], "Q_tsr")):
            value = method["quality"][key]
            bars = ax.bar(position, value, **common)
            ax.bar_label(bars, labels=[f"{value:.2f}"], padding=3, fontsize=7)
    left.set_xlim(-0.60, 1.85)
    left.set_ylim(0, 100)
    right.set_ylim(0, 1)
    left.yaxis.set_major_locator(MultipleLocator(20))
    right.yaxis.set_major_locator(MultipleLocator(0.2))
    right.yaxis.set_major_formatter(StrMethodFormatter("{x:.1f}"))
    left.set_xticks([0, 1.25], [r"$Q^{\mathrm{qua}}$", r"$Q^{\mathrm{tsr}}$"],
                   fontsize=11)
    left.tick_params(axis="x", length=0, pad=7)
    left.set_ylabel("Mean quality score")
    right.set_ylabel("Task success rate")
    style_axis(left)
    right.spines["top"].set_visible(False)
    right.spines["left"].set_visible(False)
    right.spines["right"].set_visible(True)
    right.grid(False)
    left.axvline(0.625, color="#BEC3C8", linewidth=0.7, linestyle=(0, (3, 3)))
    add_legend(fig, methods, y=0.94)
    return fig


def figure_agent_performance(methods):
    """Three side-by-side horizontal panels, two bars per metric."""
    fig, axes = plt.subplots(1, 3, figsize=(183 / 25.4, 65 / 25.4))
    fig.subplots_adjust(left=0.080, right=0.985, bottom=0.19, top=0.79, wspace=0.40)
    y = np.arange(3)
    height = 0.30
    for ax, panel in zip(axes, AGENT_PANELS):
        agent, title, symbol, ablation_index = panel
        for method_index, offset in ((0, -0.18), (ablation_index, 0.18)):
            values = methods[method_index]["agents"][agent]
            bars = ax.barh(y + offset, values, height=height,
                           color=COLORS[method_index], edgecolor=EDGE_COLOR,
                           linewidth=0.45, hatch=HATCHES[method_index], zorder=3)
            # A zero-width bar is intentional; its 0.00 label remains visible.
            for bar, value in zip(bars, values):
                ax.text(value + 0.025, bar.get_y() + bar.get_height() / 2,
                        f"{value:.2f}", ha="left", va="center", fontsize=6.1)
        ax.set_yticks(y, [rf"$P^{{\mathrm{{{symbol}}}}}_{{{i}}}$" for i in (1, 2, 3)],
                      fontsize=9)
        ax.tick_params(axis="y", length=0, pad=5)
        ax.set_ylim(2.6, -0.6)  # Metric 1 at the top; Proposed above its ablation.
        ax.set_xlim(0, 1.18)  # Leave space for labels while retaining a zero origin.
        ax.set_xticks([0, 0.5, 1], ["0", "0.5", "1.0"])
        ax.set_xlabel("Metric value", labelpad=3)
        ax.set_title(title, loc="left", pad=8, fontweight="bold")
        style_axis(ax)
    add_legend(fig, methods, (0, 2, 3, 4))
    return fig


def computational_table_latex(methods) -> str:
    """Print-ready LaTeX using the same data, without another output file."""
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Comparison of LLM Usage}",
        r"\label{tab:computational-cost}",
        r"\setlength{\tabcolsep}{4pt}",
        r"\resizebox{\columnwidth}{!}{%",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Method & \makecell{Tokens\\(per task)} & \makecell{LLM latency\\(s/task)} & \makecell{Retrieval\\(s/task)} \\",
        r"\midrule",
    ]
    for method in methods:
        cost = method["cost"]
        mean_tokens = cost["total_tokens"] / run_count(method)
        lines.append(
            f"{method['name']} & {mean_tokens:.2f} & "
            f"{cost['llm_inference_latency_s']:.2f} & "
            f"{cost['retrieval_time_s']:.2f} " + r"\\"
        )
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"}",
        r"\end{table}",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR,
                        help="Directory containing reported_metrics.csv and reported_provenance.json")
    args = parser.parse_args()
    methods = load_methods(args.results_dir)
    configure_style()
    output_dir = Path(__file__).resolve().parent / "figures"
    output_dir.mkdir(exist_ok=True)
    builders = (figure_quality_components, figure_quality_overall,
                figure_agent_performance)
    for builder, filename in zip(builders, PDF_NAMES):
        fig = builder(methods)
        fig.savefig(output_dir / filename, format="pdf", bbox_inches="tight",
                    pad_inches=0.03, metadata={
            "Title": filename.removesuffix(".pdf").replace("_", " "),
            "Subject": "Final selected five-method report; all methods evaluated over 600 runs",
            "Creator": "Python / matplotlib",
        })
        fig.savefig(output_dir / filename.replace(".pdf", ".png"), dpi=300, bbox_inches="tight", pad_inches=0.03)
        plt.close(fig)
        print(f"Saved: {filename}")
    print("\n" + computational_table_latex(methods))


if __name__ == "__main__":
    main()
