# Committee Scrutiny — STAKING Objective
**2026-11-24 23:10 UTC** | Analyst: flop-expert

---

## Preflight: scope-gating

The staking objective has two monitored-asset touchpoints: (1) our miner's sponsored seat depends on staking mechanics, and (2) the exchange objective's float assumptions interact with lock-up products. Both are in-scope. Proceeding.

---

## Thesis map

The design claims three separable value propositions. I will score each independently before an umbrella verdict.

| Proposition | Claim | Chain state today |
|---|---|---|
| P1: Protocol staking — sponsor/delegate, earn yield share | Pallet exists, mechanics verified | **(obs)** `total_rewards=0.0`, reward buckets flat since ≥13:00, `period_miners=0`, `proofs_24h=0` |
| P2: Product staking — StakeBoard demo, engagement layer | Deployed, paying, battle-tested | fakeFLOP / fakeUSDC, 2 stakers, funded by operator |
| P3: Bonded privacy tiers — verify+punish, nobody else does it | Slashing mechanism = moat | `miners_slashed=0` network-wide, enforcement path **never fired** |

---

## What the docs get right

**Mechanics are real.** The `MinerStaking` pallet fields cited in DETAILED.md match devnet chain state **(obs 23:10)**: `TotalMiners=760`, `TotalStake≈73.7M`, `SponsorPositions` backing our seat at 34,999.99, `UnbondingRequests`/`MinerSlashing`/`BlacklistedHardwareIds` present in runtime. The pallet is not vaporware.

**Dependency acknowledgment is honest.** DESIGN.md explicitly names the sponsor-withdrawal risk and flags the mining/exchange interactions. The risks section in DETAILED.md is unusually candid for a goal document.

**The sandbox demo proves builder capability.** StakeBoard v2 deployed, time-weighted score, day-epoch accounting, `claim()` paying — these are real engineering artifacts even if the economics are synthetic.

---

## What is wrong or missing

### 1. The existence proof is not an economic conversion path *(standing blind spot)*

The docs conflate "the pallet exists and has these fields" with "we can earn yield from it." These are different claims. The chain today shows:
- `total_rewards` for our miner: **0.0** — not a rounding artifact, identical across every poll since at least 13:00
- Reward buckets (miner/validator/agent/staker): **flat** across every snapshot today **(obs)**
- `period_miners=0` at the last distribution block 4,492,800; next boundary ~4,579,200 (~02:48–02:55 UTC tomorrow) will pay **nothing** to an empty set
- `proofs_24h=0` — no proof-of-work has settled through the chain today

**The pallet exists; the yield does not yet flow.** The design presents the mechanics as the product, but the product requires a functioning reward pipeline that is currently producing zero output. This is not a protocol bug — it is a market-stage fact. But the docs do not name it.

### 2. The sponsored-stake blast radius is uncontained *(standing blind spot — privileged-key check)*

DETAILED.md names sponsor withdrawal as Risk 1 but does not complete the audit:
- Our miner's `self_stake=0.0` **(obs)**. The entire 34,999.99 is a single external sponsor's position
- **One key action** — the sponsor calling `withdraw_sponsor_position` — eliminates our seat with no warning and no on-chain recourse for us
- The docs ask "where does 35k self-bond come from?" but do not answer it, bound a timeline, or identify a mitigation path
- `sponsorship.settled=false`, `legs=[]` **(obs)** — the settlement path is open but not progressed

This is not a risk to manage in a future phase; it is a live structural dependency of the **mining** objective that the staking objective's "who funds our bond" question inherits. If the sponsor exits before we self-bond, both silos are simultaneously impaired.

### 3. Yield math is unverifiable at current chain state *(reward-bucket opacity — docs' own Risk 5)*

The docs acknowledge this but do not fully draw the implication. The empirical pattern **(obs, all polls today)**:
- Issuance delta tracks subsidy pots (labs+foundation), not 96×blocks
- Reward bucket values (miner 37,324,800 / validator 43,130,880 etc.) are **cumulative historical figures, not per-period flows**
- Distribution mechanics have not produced a non-zero `period_miners` count in any observed window

We cannot verify what fraction of a future distribution would reach a delegator or sponsor because: (a) we have never observed a live distribution with miners in the set, (b) the per-block emission accounting doesn't reconcile against issuance in any observed window. Presenting a yield-share product to external delegators before this is understood is a credibility risk.

### 4. The privacy-tier moat rests entirely on an unproven mechanism

P3 is the highest-value proposition in the docs and the most speculative:
- `miners_slashed=0`, `slashing_burned=0` **(obs)** — the slashing path has **never executed on devnet**
- The claim "attestation detects; slashing punishes" requires both halves to work in production under adversarial conditions
- TEE attestation integration is not mentioned in any chain pallet observed; it is an architectural assumption
- The "nobody sells verify+punish" competitive claim may be correct but cannot be validated from chain state; it requires an independent market survey the docs do not provide

The moat narrative asks external delegators to bond stake against a punishment mechanism that has never fired. That is not a dealbreaker for a roadmap item, but it **cannot be the primary sell in the near term**.

### 5. StakeBoard's "battle-tested" framing is overstated

- 2 stakers on a sandbox chain with synthetic assets is a proof-of-concept, not battle-testing
- The pool is funded by the operator (3M fakeUSDC liability acknowledged) — real yield requires real revenue
- v1 was abandoned; v2 is a solo rebuild
- "Demo mechanics already battle-tested → ship real version faster" is a reasonable dev argument but not a product-market validation

### 6. Missing: unbonding queue parameters

DETAILED.md mentions `UnbondingRequests` exists but does not state the unbonding period in blocks or wall-clock time. For a yield product, illiquidity duration is a first-order pricing input. Stakers need to know this before committing capital.

---

## Single biggest weakness

**There is no demonstrated reward flow to any staker or sponsor on this network.** Every other risk — slashing untested, StakeBoard demo, sponsor-withdrawal exposure — is conditional on first solving the fundamental question: does backing a miner in this protocol's current state produce any yield at all? The answer from chain state today is: **not observably**. `total_rewards=0`, buckets flat, `period_miners=0`, `proofs_24h=0`. The design builds an elaborate product architecture on top of a yield pipe that has not been observed flowing. Until at least one distribution cycle completes with miners in the set and the per-staker/per-sponsor reward math reconciles against on-chain data, the economic core of this objective is unproven.

---

## What survives scrutiny

- The staking **infrastructure** (pallet, unbonding, slashing code) is real and present on-chain **(obs)**
- Our miner's sponsored seat is a live instantiation of the protocol mechanic
- StakeBoard demonstrates engineering capability for the product layer
- The privacy-tier thesis is directionally correct as a market positioning statement (though execution-dependent)
- The dependency acknowledgments in the docs are honest and structurally sound

---

## Verdict: **CONDITIONAL**

**Conditions required before the objective advances to execution:**

| # | Condition | Why blocking |
|---|---|---|
| C1 | Observe at least one distribution cycle with `period_miners > 0` and reconcile per-miner/per-sponsor reward math against chain state | Yield product has no verified economic core until this happens |
| C2 | Bound the sponsor-withdrawal exposure: either (a) identify the 35k FLOP self-bond source and timeline, or (b) obtain a binding on-chain commitment from the current sponsor | Single-key blast radius on our seat is uncontained |
| C3 | Verify unbonding queue duration in blocks before any external delegator pitch | Illiquidity is a first-order staking product parameter |
| C4 | Reframe the privacy-tier claim as a roadmap item contingent on slashing firing in production, not a current deliverable | Overstated claim damages credibility with sophisticated delegators |

**The thesis survives as a protocol-aligned objective with real infrastructure. It does not survive as a yield product until C1 is met, and it carries unacceptable sponsor-exit risk until C2 is resolved.**

---

## Knowledge base update flags

- `total_staked` (frontier/agents) moved: **255,314.22** (was 255,235.81, **+78.41**) **(obs 23:10)**
- `da_blobs` **38,401** (+66 vs 22:01)
- `active_agents` **19,200** (+2 vs 22:01)
- `total_agents` **23,910** (+7 vs 23,903)
- HTLC **9,901** (+1), active **9,791** (+1)
- Subsidy pots **36,529,528** each (+33,416 vs 22:01) — still equal, tracking
- Issuance **4,415,751,933.760991** (+66,832 vs 22:01); 4,189 blocks × 96 = 402,144 — not in issuance; pattern holds
- Cal block **4,566,191**; expires 5,017,158 − 4,566,191 = **450,967** blocks ≈ **5.22 d → ~2026-11-30 03:30 UTC**
- Next distribution: 4,579,200 − 4,566,195 = **13,005** blocks ≈ **3.6 h → ~02:46 UTC 2026-11-25**
- All other miner fields unchanged; event log still ends 15:22Z
2026-11-24 23:15 UTC committee: minimax-m3=agree; deepseek-chat=partly

--- committee ---
[minimax-m3] agree: Correct call. The duty officer correctly identifies that the pallet existing ≠ yield flowing (total_rewards=0, reward buckets flat, period_miners=0) and that the sponsored-stake single-key dependency is a live, unmitigated blast radius for both staking and mining. Verdict CONDITIONAL is right; the thesis is mechanically sound but economically pre-revenue and structurally exposed.
[deepseek-chat] partly: Right on mechanics & demo rigor, but underweights the economic dependency on sponsor and reward plumbing not yet functional.
2026-11-24 23:15 UTC lesson recorded: Conflated existence-of-mechanism with proof-of-revenue-flow.

--- synthesis ---
**STAKING — Final Verdict: CONDITIONAL**

Three propositions, one real flaw each. P1 (protocol yield): pallet verified, mechanics real, but `total_rewards=0.0`, reward buckets flat all day, `period_miners=0`, `proofs_24h=0` — the yield pipeline is not flowing; the docs present mechanics as product without naming that gap. P2 (StakeBoard demo): genuine engineering, honest sandbox labeling, 2 stakers, funded liability acknowledged — survives as a capability proof, not a business yet. P3 (bonded privacy moat): strategically differentiated thesis, but `miners_slashed=0` network-wide means the enforcement path has never fired; the moat is unproven code. **Single biggest weakness:** our miner's `self_stake=0.0` with 34,999.99 on a single external sponsor — one `withdraw_sponsor_position` call collapses both the staking and mining silos simultaneously, `sponsorship.settled=false` with no mitigation bound. **Conditions to pass:** (1) define a self-bond acquisition path and timeline before the sponsor question is live, (2) confirm reward flow is functioning before yield-share claims are made externally, (3) treat slashing as unproven until at least one network event fires.
