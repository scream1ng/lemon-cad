---
name: costing
description: Estimate sheet-metal fabrication cost from uploaded PDF drawings, drawing images or CAD, with per-component raw material, laser cutting, bending, setup hours, pieces per hour, welding, finishing and assembly totals. Use when a user drops a drawing for costing, requests a manufacturing estimate, or wants process and material cost breakdowns.
---

# Costing

Return an immediately useful internal budget estimate in chat. Do not require STEP or a questionnaire before starting from a readable drawing. AUD excluding GST by default. Label provisional assumptions prominently; never describe a budget estimate as a supplier quotation.

Each rule lives in one reference file:

| File | Owns |
|---|---|
| `references/estimating.md` | Input precedence, drawing reading, BOM and hardware ownership, batch quantity, yield, cycle times, scenarios, revisions |
| `references/material-pricing.md` | Material price decision order, IXL baseline, proxies, scaling, units/GST, age |
| `references/rates.json` | Saved resource rates, default resources, fallback throughputs, margin, e-coat reference |
| `references/calculator-contract.md` | Calculator input schema and output fields |
| `references/report-format.md` | Chat report layout, margin/selling presentation, inspection/packing absorption |

## Commands

The first argument may pick a mode; the rest (quantity, MOQ, file) applies as usual. Keep the same inputs and calculator results across modes in a conversation; switching mode only changes presentation unless inputs change.

| Command | Output |
|---|---|
| `/costing summary …` | Summary only, per `report-format.md` "Summary mode": roll-up table, batch line, unpriced items. |
| `/costing breakdown …` (default when no mode is given) | Full authoritative report per `report-format.md`: roll-up, one table per Part and Assembly, notes. |
| `/costing nest …` | Laser nest page: run `scripts/nest.py … --html <part>-nest.html --title "<part> Nest" --sheet-price <$/sheet>` (shop 1200 × 2400 usable sheet per `estimating.md`, even when priced on IXL 1220 × 2440), then deliver the one page to match the host. Claude Code on the user's machine: write it beside the input STEP and open it (`open -a "Google Chrome" PAGE.html` on macOS). Cowork / claude.ai chat: write it to the session's output folder so it is attached, and also show the exact generated HTML inline when the host offers a raw-HTML view (do not claim it rendered without seeing it). Do not publish it as an artifact unless asked. Give the file path or attachment and per-sheet counts, utilisation and $/part in chat. The page is self-contained (no CDN); each blank is drawn once and placed by reference, so keep it under 250,000 bytes (the script reports the size). Needs STEP outlines (see `estimating.md`). |

## Workflow

1. Read all five reference files and `references/ixl-material-baseline.json`.
2. Read the drawing (text and every sheet visually) and reconcile the BOM, per `estimating.md`. For a STEP-only input, run `scripts/step_geometry.py` first.
3. State the batch quantity (default 100, provisional) and build a route per component, then assembly operations once.
4. Price material per `material-pricing.md`; estimate yield per `estimating.md` (true-shape `scripts/nest.py` when STEP outlines exist, else dimensioned flat envelopes).
5. Write schema-2 input and run `python3 scripts/calculate.py INPUT.json`. It must succeed before reporting; review its totals. Run low/base/high and batch-size scenarios where `estimating.md` requires them.
6. Report in chat exactly per `report-format.md`: cost roll-up first, then one table per Part and Assembly.
7. For revisions, run `python3 scripts/compare.py PREVIOUS_RESULT.json CURRENT_RESULT.json` and explain every changed cost.
8. End with the few inputs most likely to change the result (usually batch size, factory rates, nest yield or coating quote). Deliver the estimate before asking optional questions. Create spreadsheets/documents only when requested.

A worked example is in `examples/bracket/`.
