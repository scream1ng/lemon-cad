# LemonCAD credit pricing — proposal, 25 September 2026

## Recommendation

Prepaid credits, shared across all three engineering services. Keep anonymous viewing,
measurements, image/PDF exports and the agreed free-account drawing tier free.

- 1 credit = US$0.10. Initial packs: 100 credits / US$10; 250 / US$25;
  1,000 / US$100. No subscription or volume discount at launch.
- Costing: from 20 credits (US$2); planning range 20–60.
- Checking fixture concept: from 200 credits (US$20); planning range 200–600.
- Weld fixture concept: from 300 credits (US$30); planning range 300–1,000.
- These are proposed product prices, not measured job costs or guaranteed quotations.
  Do not charge for the existing non-AI calculator as if Claude already ran.
- Prices cover automated work only. Human engineering review, certification,
  manufacturing and physical verification are separate, not included services.

## Verified provider rates

Anthropic currently lists Sonnet 5 at US$2 input / US$10 output per million tokens,
Opus 5.5 at US$4 / US$20, and Haiku 4.5 at US$1 / US$5. Cache and server-tool usage
have their own rates; bill actual returned usage rather than estimating solely from
prompt length. [Official Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing).

Railway lists CPU at US$20/vCPU-month and memory at US$10/GB-month, with storage,
egress and the plan commitment additional. [Official Railway plans](https://docs.railway.com/pricing/plans).

## Illustrative economics — assumptions, not benchmarks

| Workload assumption | In / out tokens, summed across all turns | Token-only cost | Proposed floor |
|---|---:|---:|---:|
| Costing, Sonnet 5 | 30k / 8k | US$0.14 | US$2 |
| Checking concept, Opus 5.5 | 200k / 40k | US$1.60 | US$20 |
| Iterative weld concept, Opus 5.5 | 600k / 120k | US$4.80 | US$30 |
| Heavy iteration, Opus 5.5 | 1m / 250k | US$9.00 | Quote against cap |

Example incremental CAD compute: 10 minutes consuming 2 vCPU + 2 GB RAM is about
US$0.014, excluding idle capacity and other charges. In practice retries, support,
free-tier subsidies and workload uncertainty matter more than that small example.
Do not confuse incremental cost with the monthly bill.

A starting settlement policy to evaluate:

`credits = max(service_floor, ceil(3 * direct_provider_cost_USD / 0.10))`

Direct cost includes actual model input/output/cache charges, paid tools and attributable
CAD compute. The 3× multiplier is a proposed business rule, not a provider tariff. It
provides a 67% contribution margin on variable cost above the floor, before payment
fees, idle capacity, support, tax and refunds. Benchmark 30–50 representative jobs per
service before fixing the public tariff. Reprice or split jobs exceeding the quoted cap.

## UX and metering contract for the future API connection

1. Survey CAD geometry locally in the worker. Send compact, source-bound geometry facts
   and selected images to Claude; don't dump entire STEP files into a prompt.
2. Estimate credits, disclose included outputs and show a hard cap before the run.
3. Reserve that cap atomically. Bind it to user, job, source revision and tariff version.
4. Persist usage per API request, including cache categories, model ID, tool charges and
   retries. Never bill twice when a worker retries a completed request.
5. Stop before exceeding the cap; require an explicit additional budget for continuation.
6. Settle once against the immutable ledger and release unused reservation. Platform
   failures should not consume customer credits; cancellation policy needs clear terms.
7. Keep an audit trail and a receipt. Use integer credit units or a finer internal unit,
   not floating-point wallet balances. Revisions are separately quoted, not silently run.

Sonnet is a cost baseline for estimate explanations; fixture planning may need Opus.
Model choice must be evaluated on actual engineering correctness. Claude does planning
and tool orchestration; OCP remains the source of geometry and dimensional truth.
Do not run model-generated shell commands with unrestricted host/network access.

## Implementation status

This change updates the public feature cards and indicative pricing only. There is no
Claude API call, wallet debit, checkout or billing migration in this build. The fixture
service still captures briefs pending an engineered datum/spec workflow. Automatic
geometry generation and verified delivery must not be presented as available outputs.
Adding a credit ledger is a future schema change requiring the user's approval.
Prices are shown in USD to avoid an unverified AUD exchange-rate assumption; taxes are
not determined here and must be resolved before checkout launches.
