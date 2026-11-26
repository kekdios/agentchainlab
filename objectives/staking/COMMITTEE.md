# COMMITTEE MEETING — StakeBoard Sandbox Scrutiny
**2026-11-24 23:47 UTC | Analyst: flop-expert**

---

## 0. Scope confirmation

The objective under review is **StakeBoard v2 as a live test of exchange processes** using play tokens on chain 424242. FLOP-protocol staking (MinerStaking, sponsor/delegator) is **out of scope** for this verdict. I will not blur that boundary.

---

## 1. The core thesis

> "Lock → track → claim → settle is the same shape as an HTLC swap."

**Structural mapping (assessed):**

| StakeBoard stage | Exchange analogue claimed | Mapping quality |
|---|---|---|
| approve + lock | HTLC deposit leg | **Weak** — HTLC has a *counterparty* and a *hash preimage* condition; lock() has neither. Unilateral lock ≠ bilateral commitment. |
| score = amount × time | Time-weighted accounting / escrow duration | **Moderate** — the math shape is correct (integral of balance over time); HTLC deadlines are discrete timeouts, not continuous accumulators. Similar failure modes (overflow, boundary), different semantics. |
| claim() → ERC-20 transfer | Settlement payout path | **Strong** — this is a genuine, exercised transfer path under real block clocks. |
| day-epoch pool cap | Budget/faucet cap accounting | **Strong** — identical accounting shape; epoch resets, cap exhaustion, race conditions all transfer directly. |
| lock-until timestamp | HTLC refund window | **Weak-to-moderate** — the failure shape (what happens at expiry) is relevant, but the sandbox has *no* refund path, so the refund leg of the HTLC shape is entirely untested. |

**Verdict on the mapping:** 2 of 5 analogues are strong, 2 are weak, 1 is moderate. The thesis holds for **settlement mechanics and cap accounting**. It does not hold for **counterparty coordination, hash-condition verification, or the refund/timeout leg** — which are arguably the hardest parts of HTLC exchange operations.

---

## 2. What is genuinely well-designed

**(a) Iteration loop worked.** v1 → v2 (no-yield → paying) in response to "make it pay" feedback is real product iteration. The feedback loop the docs claim is functioning.

**(b) Agent self-test is a meaningful signal.** An autonomous agent completing faucet→approve→stake→claim with no human intervention is a legitimate legibility proof. If an agent can't complete the flow, the flow is broken for the class of users the exchange targets. This is the strongest single signal in the dataset.

**(c) "No airdrop — testing only" honest labeling.** Prevents the credibility trap of implied real yield. Correctly scoped.

**(d) Cap + epoch accounting is directly reusable.** The day-epoch pool cap code, once audited in the sandbox, can be ported or referenced for faucet budget logic. Genuine transfer of learning.

**(e) Failure is defined.** Kill criteria are stated: contract bug in the wild, or zero engagement. Having explicit kill criteria is better than most sandbox designs.

---

## 3. What is wrong or missing

### 3a. The refund leg is absent — a critical gap

The HTLC's most operationally dangerous moment is the **timeout/refund path**: funds committed, counterparty non-responsive, refund window expires, funds returned (or not). StakeBoard has **no unlock before 2027-02-21**. The lock is absolute. This means the sandbox **cannot generate signal** about the failure mode that causes the most real-money loss in exchange operations. The analogy breaks exactly where it matters most.

### 3b. No counterparty — the bilateral coordination problem is untested

HTLC swaps require two parties to coordinate. StakeBoard is unilateral. The coordination failure modes — counterparty goes dark, preimage withheld, timing attacks between lock and reveal — are structurally absent. The sandbox tests *one leg* of a two-legged process.

### 3c. Anvil chain fragility is an existential risk to the dataset

A chain reset destroys all locks, scores, and claim history. There is **no migration path, no snapshot commitment, no external anchoring** described. The 90-day test requires 90 days of chain uptime on a single VM's state file. One operator error, cloud provider incident, or botched update ends the experiment and invalidates the dataset. The docs acknowledge this but offer no mitigation.

### 3d. Success metric is incomplete

"≥X external stakers survive the full 90-day window with zero contract exploits" — **X is undefined**. Without a floor, any N ≥ 1 technically satisfies the criterion. Two stakers (one of which is our own agent) are currently active. If that count stays at 2 through day 90, does the test pass? The metric as written cannot generate a falsifiable verdict.

### 3e. Scoreboard gaming corrupts the signal

"Bot stakers inflate the scoreboard; keep metrics interpreted honestly" is acknowledged but not mitigated. If the exchange-process signal comes from observed behavior under adversarial play, and the adversarial players are bots inflating scores rather than humans probing claim-math edge cases, the signal quality degrades. The docs have no bot-filtering methodology.

### 3f. The agent-legibility proof is a one-time snapshot

One agent completing the flow once proves the flow was legible at that moment. It does not prove the flow remains legible after UI changes, contract upgrades, or faucet parameter shifts. No re-run cadence is specified.

### 3g. Blast-radius audit is absent

*(Applying the blind-spot rule.)* A single admin key can: fund or drain the pool, and — per "Admin: pool funding, no user-fund withdrawal path" — the user-fund protection depends entirely on what that admin key *cannot* do. The docs assert "non-custodial within demo scope" but do not specify whether the admin can call a privileged drain function, upgrade the contract, or pause claims. If the admin key is compromised or misbehaves, the stated trust property (users' locked fakeFLOP is safe) may not hold. For play tokens this is low-stakes, but the design habit of leaving admin blast-radius unaudited is exactly what gets carried forward to real-money contracts.

---

## 4. The single biggest weakness

**The refund/timeout leg is completely absent.**

This is not a minor gap. The docs' central claim is that StakeBoard tests "the same shape as an HTLC swap." But HTLC operations fail — and fail expensively — at the timeout/refund boundary. That boundary does not exist in this sandbox. The 90-day absolute lock means testers cannot probe what happens when a commitment expires on a non-cooperative counterparty. The exchange team will complete 90 days of sandbox operation and will have learned nothing about the failure mode that most commonly causes real-money loss in HTLC-based exchanges.

A secondary consequence: the absolute lock will cause tester attrition. Users who lock tokens and cannot see, probe, or practice the unlock path will disengage. The retention game the docs describe depends on users feeling in control of their position. An inescapable 90-day lock is structurally hostile to the engagement loop.

---

## 5. Scope-gating check

*(Applying the blind-spot rule.)* Does this analysis affect a **monitored asset or require operator action**?

- StakeBoard is an **operator-built** sandbox on chain 424242. It is within our operational perimeter.
- The contract holds **3M fakeUSDC** minted by us — our liability, our reputation if the pool drains badly.
- The agent self-test at `0x3C44…93BC` is **our agent** — its behavior reflects on our exchange credibility.
- The devnet miner (**healthy, not affected**) has no dependency on this silo.

Verdict: this is in-scope. Operator action is not immediately required (no exploit observed, two stakers active, pool not drained). But the design gaps identified above should be addressed before the sandbox is used as evidence of exchange-process readiness.

---

## 6. Verdict

### CONDITIONAL

**The thesis partially survives.** The sandbox genuinely exercises ERC-20 transfer correctness, epoch/cap accounting, and agent-legibility — three real exchange-process signals. The iteration loop (v1→v2) works. The honest labeling is correct.

**Conditions required to upgrade to SURVIVES:**

1. **Define X** in the success metric before day 30. If 2 stakers is the floor, say so explicitly and explain why 2 generates sufficient signal. Otherwise the metric is unfalsifiable.

2. **Add a simulated refund path** — even a privileged admin-callable `earlyUnlock(addr)` gated behind a time condition — so the timeout/expiry failure shape can be observed. It does not need to be user-callable; it needs to generate observable behavior at a known boundary.

3. **Chain persistence commitment** — specify the backup cadence, snapshot anchoring, or migration plan for the Anvil state. A 90-day test on an unmitigated single-VM state file is a data-loss risk, not an acceptable ops posture.

4. **Admin blast-radius documentation** — enumerate what the admin key can and cannot do to user-locked funds. If the admin cannot drain user funds, prove it in the ABI or via a timelock. "Non-custodial within demo scope" is an assertion, not a proof.

**What would trigger REJECTED:** an exploit observed in the wild before condition 2 is addressed (the test fails on its own kill criterion), or the staker count stays ≤2 at day 30 with no growth trajectory (no signal generated, test is inconclusive noise).

---

*Miner status (obs 23:45): healthy, not serving, `is_active=true`, cal active v4, `info_stale=false`. No miner action required. Devnet chain seat unchanged. Testnet rollover not ready.*
2026-11-24 23:47 UTC committee: minimax-m3=agree; deepseek-chat=partly

--- committee ---
[minimax-m3] agree: Right on substance. The HTLC analogy is weakest where it matters most — no counterparty, no preimage condition, and no refund leg until 2027-02-21 — so the sandbox can't generate signal on the failure modes that cause real-money loss in exchange ops. The unilateral lock-to-self fundamentally isn't a bilateral commitment test. CONDITIONAL at best, and only because the settlement/cap-accounting half of the thesis is genuine.
[deepseek-chat] partly: Missed critical gap: StakeBoard lacks refund leg testing, which is a key HTLC failure mode. Otherwise correct on mapping strengths/weaknesses.
2026-11-24 23:47 UTC lesson recorded: Mapped analogues by structural shape but skipped the asymmetry test: "does the analogue fail in the 

--- synthesis ---
**CONDITIONAL — StakeBoard sandbox scrutiny, final verdict**
*2026-11-24 | reconciled from full analysis + consultant review*

**What survives:** Settlement payout path and day-epoch cap accounting are genuine exchange-process analogues — both strong, both directly reusable. Agent self-test (faucet→approve→stake→claim, no human) is the single most credible signal in the dataset. Iteration loop (v1→v2) and honest labeling are well-executed.

**Single biggest weakness (all reviewers converge):** The refund/timeout leg — HTLC's most dangerous failure mode — is structurally absent. No unlock before 2027-02-21, no counterparty, no preimage condition. The sandbox tests *one unilateral leg* of a bilateral commitment process and cannot generate signal on the coordination and timeout failures that cause real-money loss in live exchange ops.

**Correction to prior analysis:** Anvil chain fragility and pool-drain risk are real but secondary; the structural incompleteness of the HTLC analogy is the primary defect, not an implementation detail.

**Verdict: CONDITIONAL.** Approve for the exchange processes it *does* test (ERC-20 transfer correctness, epoch cap accounting, agent legibility). Do not use results to validate HTLC refund/timeout logic — that gap must be closed separately before exchange launch.
