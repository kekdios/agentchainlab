# COMMITTEE MEETING — Mining Objective Scrutiny
**Analyst: FLOP Expert | 2026-11-24 23:05 UTC**
**Probe basis: mining snapshot 23:05, KB enriched 22:01**

---

## Preflight: Document vs. Chain Conflicts

Before scoring, two factual corrections to the DETAILED.md that affect the thesis:

| DETAILED.md claim | Chain obs (23:05) | Impact |
|---|---|---|
| Cal expires "~2026-11-30 (~453k blocks)" | Cal block 4,565,895 → expires 5,017,158 = **451,263 blocks left** ≈ **5.22d → ~2026-11-30 03:30 UTC** at 1 blk/s. Direction correct; number slightly stale | Minor |
| Testnet "6 validators (fresh keys, not devnet identities)" | Not confirmed by chain probe; testnet econ zeros and account absent are confirmed. Validator count is trigger-sourced at best | Minor — overstates testnet visibility |
| "Sessions=0 all-time" | Technically: 1 refunded (0x6beb), 1 open/legacy (0x8e70). Zero *settled* sessions is correct | Presentational; not a thesis error |
| "period_miners currently 0 → no payout expected" | Confirmed (obs 23:05: period_miners=0) | Confirmed correct |

---

## Thesis Examination

### The core claim
> "Operate a calibrated GPU miner; first-mover advantage converts to paid sessions when testnet/mainnet opens."

This is a **staging bet**: pay now, extract later. The question is whether the conditions required for extraction are reachable from our current position.

---

## What Is Sound

**1. The supply-side role is real and necessary (obs-confirmed).**
The protocol is structurally complete on devnet: HTLC sessions (9,901 total, 9,791 active), metering proofs pathway, distribution epochs, calibration-gated work_vesting — these all exist as live pallets. Miners are not speculative; they are a required protocol primitive. ✓

**2. We are genuinely inside the door (obs-confirmed).**
Registered block 3,535,427, cal v4 cap 34,127, sponsored 34,999.99, image current 0.1.418, regready all-true, unfenced, strikes 0. This is not aspirational positioning — it is confirmed chain state. Among 760 registered miners with period_miners=0 network-wide, we are as ready as any. ✓

**3. Cost basis is accurate and bounded (obs-confirmed).**
~$4.40/day is consistent with gpu.ai ~$95/mo + droplet spend. No hidden cost discovered in probes. ✓

**4. Operational infrastructure is real and working (obs-confirmed).**
Containers Up 4 days, collect.sh running, Expert watching, Telegram notify live, GPU idle with weights resident (correct behavior at sessions=0). The "moat is the ops record" claim is at least partially earned. ✓

**5. Kill criteria exists.**
"No path to paid sessions by mainnet economics decision point" is an actual off-ramp. Many bootstrap-phase docs have no kill condition at all. ✓

---

## What Is Wrong or Missing

**W1. The reward mechanics described are observationally incomplete.**
DESIGN.md states: "Distribution epochs pay miners proportional to settled work." This is *partially* correct but misses a critical obs: `reward buckets have been flat since at least 2026-11-17`. Miner bucket 37,324,800 — identical across every probe today. The issuance delta tracks *subsidy pots*, not per-block emission (4,565,895 − 4,562,006 = 3,889 blocks × 96 = 373,344 — absent from issuance). The docs say one thing; the chain shows something different. The team has not explained this. The docs call it out as "unproven on us yet" — that's correct — but the doc *implies* the mechanism is understood. It isn't, and that gap is not flagged with sufficient weight.

**W2. The first-mover claim conflates devnet position with testnet position.**
Testnet: our account does not exist, `our_miner_registered=false`, econ zeros. Testnet spec 1014035 (one ahead of devnet 1014034) — the runtime has already diverged. The 760 devnet miners do *not* automatically carry to testnet. GOAL.md says "operators who are already calibrated...take the first seats" — this is an *assumption*, not a confirmed protocol property. There is zero obs evidence that devnet registration confers testnet priority. The docs present this as near-certainty; it should be Risk #0.

**W3. Calibration expiry is a hard gate, not a footnote.**
~5.2 days to expiry (obs: 451,263 blocks at 23:05). DETAILED.md lists it as Risk #2 in a list; it should be a **P0 operational item with a dated renewal plan**. If recalibration requires testnet registration (which requires account funding, which requires a faucet that doesn't exist on testnet), and if devnet recal is structurally different from testnet recal, the expiry compounds the testnet-access risk. The docs do not address the renewal *procedure* under current testnet conditions. Cal version 1 still open in the legacy channel suggests the protocol tracks calibration versions carefully — a lapse matters.

**W4. The economics break-even model is not a model.**
DETAILED.md says "variable = reward rate at session availability. Unknown until testnet economics activate." That is correct but incomplete. A proper stress-test would bound the problem: at 34,127 GFLOP/s cap, what session utilization rate is needed to cover $4.40/day at plausible FLOP token prices? The doc does not attempt this. Without even an order-of-magnitude estimate, the kill criteria ("no path to paid sessions") is unactionable — you can't evaluate the path without a rough model of what "economic" looks like.

**W5. The legacy open channel 0x8e70 risk is listed but not dispositioned.**
Risk #6 is "unresolved session residue from cal v1." This channel has been open since block 3,699,036 — over 866,000 blocks ago at cal v1 cap 1. `evidenceStatus=NONE`, `timeoutPath=open_until_timeout`. The docs note it; they do not say what happens when it times out, whether it generates a strike, whether it blocks future session opens, or whether operator action is required. It is listed as though it is merely cosmetic. It may not be.

**W6. Sponsored stake dependency is under-analyzed.**
Risk #4 names it. But the deeper question is: who controls the sponsor, what are the withdrawal conditions, and is there a protocol mechanism that forces self-bond at testnet transition? If the sponsor withdraws before mainnet, we need 35k FLOP self-stake to remain active. Where does that come from? The staking objective is listed as a separate silo — but it is actually a *dependency* of the mining objective, not a parallel track. The design siloes them when they should be coupled.

---

## Single Biggest Weakness

**The first-mover thesis rests on an unverified protocol property: that devnet registration, calibration, and operational history confer priority or guaranteed access on testnet/mainnet.**

Every other weakness is recoverable. If recalibration is routine, W3 is a cron job. If the break-even model is unfavorable, the kill criteria triggers. If the legacy channel expires cleanly, W5 dissolves. But if testnet seat allocation is by lottery, by invite list controlled by @flop_labs, by a fresh stake race, or by any mechanism that does not reward prior devnet participation — the entire "why us, why now" argument collapses. We would have paid ~$4.40/day for positioning that the protocol does not recognize.

This is not a reason to stop. It *is* a reason to treat testnet access as a **live open question requiring direct confirmation**, not a background assumption.

---

## Verdict

**CONDITIONAL**

**Conditions to survive full scrutiny:**

1. **[Cal — 5-day deadline]** Document the devnet recalibration procedure now. Confirm whether testnet recal requires a funded account. Execute before block 5,017,158. Failure = miner loses its primary protocol gate.

2. **[Testnet access — open question]** Obtain from @flop_labs or on-chain evidence whether devnet registration history confers any testnet priority. If the answer is "no special priority" or "lottery," revise the first-mover framing and re-evaluate whether continued devnet spend is justified solely as protocol-learning R&D.

3. **[Economics model — 30-day item]** Build a minimum break-even table: FLOP/session-GN × price scenarios × our cap utilization rate → daily revenue. This is needed before the mainnet economics decision point has any meaning.

4. **[0x8e70 disposition]** Determine from protocol docs or direct test: does the legacy cal-v1 open channel generate a strike on timeout? Is operator action available? Flag the outcome.

5. **[Staking coupling]** Acknowledge in the MINING design that it has a hard dependency on sponsored or self-staked 35k FLOP. The two objectives are not parallel silos on this point.

The devnet miner is **healthy and should stay**. The objective **survives as a monitored R&D position**, not yet as a validated business. The committee should not approve a second GPU or expanded spend until Condition 2 is answered.
2026-11-24 23:10 UTC committee: minimax-m3=agree; deepseek-chat=partly

--- committee ---
[minimax-m3] agree: Correctly identifies the load-bearing gap: devnet registration does not automatically port to testnet, and the 760-miner count is meaningless for the actual decision point. The reward-bucket flatness observation is the right next thing to interrogate — but the analyst should also flag that $4.4/day is bleeding on a non-portable position; the staging thesis needs an explicit testnet-seat conversion path or the burn rate is pure R&D, not positioning.
[deepseek-chat] partly: They correctly identify gaps in reward mechanics and testnet position, but underestimate the risk of sponsor stake withdrawal and single point of failure.
2026-11-24 23:10 UTC lesson recorded: Treated chain-state completeness as thesis validation rather than separating *existence proof* from 

--- synthesis ---
**VERDICT: CONDITIONAL**

Thesis is structurally sound — supply-side role is real, our devnet position is confirmed chain-state, cost basis is accurate, kill criteria exists. Three load-bearing weaknesses survive review: **(1)** devnet registration does not port to testnet (obs-confirmed: account absent, spec diverged to 1014035, econ zeros) — the first-mover claim is an unverified assumption, not a protocol property; **(2)** reward mechanics are empirically opaque — miner bucket flat since 2026-11-17, issuance tracks subsidy pots not per-block emission, the settlement-to-epoch path is undocumented in live chain behavior; **(3)** sponsored stake (~35k, not ours) can be withdrawn unilaterally, and a single-GPU single-host topology means one failure at the testnet seat window is unrecoverable. Deepseek is correct that the doc underweights risks (1) and (3); minimax is correct that $4.40/day is burning on a non-portable position — this is pure R&D spend until a testnet-seat conversion path is confirmed, not "positioning." **Conditions to survive:** (a) identify the testnet onboarding gate and confirm whether devnet identity confers any priority; (b) explain the flat reward buckets before treating reward mechanics as understood; (c) document the sponsored-stake withdrawal risk and minimum self-bond required to hold the seat independently.
