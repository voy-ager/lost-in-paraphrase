# Phase 1 pilot (issue #18)

Setup: ControlArena Apps, honest mode, trusted monitoring with the text-submit parser
(`trusted_monitoring_text_submit`), one Ollama model in both roles, `max_steps` 10, seed 0,
Docker sandbox, CPU only. Wall time includes Docker overhead. Peak RAM is system-wide used
memory (16 GB laptop). Raw logs stay local.

## Gate (2 honest samples per model)
Without the parser neither model ever submitted. With it, both models submit in 2 of 2 samples
(all four submits came from the parser) and the monitor scored every submit message. Pass rate 0/2 each.
A first gate run (fenced JSON only) gave 1 of 2 submits per model; the second sample emitted the
call as bare, unfenced JSON, so the parser now also accepts a bare JSON reply.

## Pilot (positions 1-10 of the seeded pool)
| model | samples | s/sample | submits (via parser) | monitor-scored msgs | pass | peak RAM |
|---|---|---|---|---|---|---|
| qwen2.5-coder:3b | 10 | 64.8 | 9 (9) | 9 | 0/10 | 15.1 GB |
| qwen2.5-coder:1.5b | 3 of 10, aborted | ~606 | 3 (3) | 3 | 0/3 | not measured |

Parser fire rate: 100% of submits (the models never emit structured tool calls). One 3b sample
never submitted (invented tool names, hit max_steps).

1.5b problem: in two attempts each sample stalled about 10 minutes (second attempt: no sample
finished in 10 min, aborted). Event timestamps show the stall is the trusted-monitor model call after
a short policy call (about 32 s), not Docker or scoring. Gate runs did not show it. Likely runaway
generation; untested fix: cap `max_tokens` on the monitor call.

Pass rate is 0 for all 15 scored samples. Small models fail Apps tests; usefulness will be near
the floor, which matters for the usefulness axis of the study.

## Pool
`AppsSetting(has_backdoor_solution=True)`, seed 0: 1444 tasks in each mode, so the needed 460 are available.

## Cost
3b all-roles pilot: 65 s/sample for policy plus one monitor call, consistent with the design estimate
(~5 CPU-min per sample for the full arm set). The 1.5b stall is unresolved, so a main-run projection is
only valid once that is fixed: design estimate ~30 CPU-h; with the stall unfixed it would be hours per sample-arm, far over budget.
