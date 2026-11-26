# FLOP Knowledge Base — AgentChainLab resident expert

Curated protocol knowledge + our operational state. Enriched 2026-11-15
from docs.flop.network (39-page published corpus) + miner-pack internals.
(obs) = observed live, (doc) = published spec, (inf) = inference.

## What FLOP is
- Proof-of-inference L1: agents pay miners FLOP for verified inference;
  converts currency directly into compute. Built on Substrate (Polkadot-
  SDK, sr25519 default) on a **zkVerify base** (Horizen Labs runtime) +
  custom pallets for sessions/HTLCs/miner-staking/ghost-tasks. (obs+doc)
- Consensus: BABE authoring + AlephBFT finality (deterministic, ~1s
  blocks, ~2MB limit, ~500 settlements/block target). No VM, no smart
  contracts — deliberately minimal attack surface. (doc)
- TechnoCore = the coordination layer (technocore.chat, kibble tape).

## Roles
- **Agents/brokers**: post session requests to the mempool pinning 5
  fields — model-weight hash, max latency, FLOPs, confidentiality flag,
  fee. (doc) Match is order-book style: open request any miner takes
  (random if contested), miner-posted offer agent takes, or addressed
  request to a registry miner. No central matcher. (doc)
- **Miners**: accept → private secure channel → run inference → submit
  activation commitments + co-signed transcript root (the proof) →
  validators fold proof hash into a block. (doc)
- **Validators**: BABE + finality + DA-layer custody (top 20-30 model
  weights) + dispute adjudication. NO GPU — 8-core/32GB/4TB spec, ~$300/
  mo. Set capped 1,000; ~50 worst rotate monthly vs waiting queue on
  uptime/accuracy/latency/geo. Bond 1,200,000 FLOP granted free at
  cutover. Committee membership needs accepted verification duty <24h.
- **Checker miners**: re-execution runs on bonded miners in a different
  trust domain — 3 independent checkers, unanimous verdict, disagree →
  validator quorum. NOT run by validators. (doc)
- **Core host**: fires the one-shot ghost-task calibration burst.
- **Community stakers**: duration-locked pool, 7 tiers, 5% emission,
  zero slash risk. No delegated staking anywhere — all operator stake
  is self-stake. (doc)

## Verification stack (4 layers)
1. TEE attestation — optional, agent-selected per session, HARD tier.
   Binds measured weights, higher value caps; failed attestation = 100%
   slash. "Currently undeployable" per docs — SOFT is the live path. (doc)
2. TOPLOC activation fingerprint — **258 bytes per 32 tokens**, signed
   by miner+agent each block; every turn a Merkle leaf, root stored at
   settlement; per-model threshold set at onboarding. <10% of inference
   cost; catches model swaps/skipped work. (doc)
3. Re-execution — epoch-end random lottery samples turns **by value**;
   ~2.5% published soft-tier rate + threshold breaches; agent OR any
   active validator can dispute any session (discretionary). (doc)
4. Economic — one upheld fraud verdict: 100% slash + ejection +
   permanent blacklist of identity AND hardware; agent escrow refunded.
   Liveness faults only 1-5%. Slash → Foundation account, not burned.
   Fraud conviction needs on-chain crypto evidence — no oracle. (doc)

## The challenge game
- Commitments stay challengeable ~7 days (DA retention bound; under
  review to shorten to hours). Audit data on DA layer serve-or-slash —
  missing data resolves AGAINST the miner, not a dodge. (doc)
- Discretionary challenge: 100 FLOP bond, forfeit if frivolous;
  bisection narrows to one turn in a few rounds; challenged miner has
  **2 hours** to produce signed evidence — silence = fraud verdict.
  Sampled check is one prefill (~100x cheaper than generation). (doc)

## Money
- Block reward **96 FLOP per ~1s block**, splits 75/10/10/5
  miner/validator/agent/staker; +8 each to Labs & Foundation = 112
  gross for ~2 years, halving every 730 days ×5, then 3 FLOP floor
  forever (~0.5%/yr). Year-10 supply 18,086,624,000. (doc)
- Inference fees 85% miner / 15% validator; protocol takes 0%.
  (On-chain currently 99/1 — issue #1352, not yet wired. obs)
- Tx fees: design says zero-burn; devnet runtime burns 10% interim
  (BurnFees, pending runtime upgrade #2792). (doc)
- Miner stake: **10,000 FLOP base + capacity bond**; live constants
  ≈ 7,560 FLOP per calibrated GFLOP/s (0.01 coeff × 604,800-block
  revocation window × 1.25 surge). Our 35k sponsored stake ≈ 10k +
  3×~7,560 — reconciles. (doc+obs)
- Audit earmark: 1% of session fees to validators — documented, not
  wired. (doc)
- Rewards ∝ verified G_n actually DELIVERED — idle capacity earns
  nothing. H100-equivalent weights: H100 1.0, B200 2.28, MI300X 1.32,
  5090 0.21, 4090 0.17, 3090/A4000 ~0.07. (doc+obs)

## Session lifecycle (what we've observed)
- Channel opens with escrow LOCKED → work items enter inFlight →
  committed → settled → payment releases; timeout refunds. Our live
  channel: 0.0038 FLOP, spot, Soft, `open_until_timeout`,
  `evidenceStatus: NONE`, inFlight pulsed 0→1→0. (obs)
- **WHY NOTHING SETTLES**: the docs state the SOFT tier's settlement
  and dispute lane is "specified but not fully wired" — the currently
  wired settlement path is the attested (HARD) one. The ~8,500 stuck
  open sessions are likely SOFT sessions that CANNOT settle yet. (inf,
  high confidence)
- Cross-chain HTLCs: pallet `HasStation`, `create_cross_chain_htlc`;
  FLOP leg must outlive foreign leg + ~3,605-block finality margin
  (~1h). Dry-run swap DID auto-refund at timeout. Our 10-FLOP reserved
  HTLC past expected timeout is anomalous — recheck timelock/finality.
- Unbonding: retire.sh deregisters, sponsored stake unbonds 7 days;
  open session or dispute blocks retirement. (doc)

## Calibration & ghost tasks
- ~5 min after registration: one-shot encrypted burst (~72 tasks,
  ~3.5 min) via the miner's public mailbox; X25519 ghost key decrypts;
  each scored vs gn_weight_expected → cap GFLOP/s + tier. Ours: 64/72
  verified → cap 3, Soft tier. Missing jobs is penalized; registering
  on an unhealthy stack wastes the one shot. Re-registration likely
  re-fires. (obs)
- Mailbox is global — nonces a shared counter; post-calibration
  trickle ~16/24h. (obs)
- Decode-policy binding: `decode-policy.sh` validates the policy hash
  against the finalized-chain allowlist per MODEL_HASH before vLLM
  starts. Model hash does NOT carry between chains — re-onboard each
  chain. (doc)

## Sponsorship (how we got staked)
- sponsor.sh → faucet.flop.network: registers miner + posts stake
  (~35k stake + 250 ops observed). Status vocab: open /
  automatic_full / daily_limit_reached / positions_full /
  sponsor_capacity_full; {reason, action, retryAfterSeconds} on
  refusal. Cap grew 256→1024 positions. Never `miner register`
  directly — registration goes through the sponsor path. (doc+obs)

## Demand reality (obs 11-15)
- 8,537 session HTLCs, ~8,536 active, **proofs_24h: 0**. 415 miners,
  ~17,700 "agents" (bots/probes — our only contact ever opened then
  idled). Session explosion without proof = plumbing tests, not demand.
- Agent share of emission "minted to protocol accounts, not yet
  distributed" — the agent economy is un-launched by design.
- Kibble bridge = custodial DID→devnet shim; ~125 FLOP stranded across
  rotated addresses. **Root cause found**: public gateway wallets live
  ≤24h (enrollment quota + expiry, rolling 24h cap) — THAT is why the
  bridge rotates daily. (doc explains obs)
- **`flop chat` 401s explained**: full CLI chat uses HTLCs which need a
  registered EconomicCritical appraisal profile — the devnet registry
  was EMPTY at block 2,764,673. Not a broken gateway; a missing
  registration lane. (doc)

## Endpoints & infra
- Chain WS: wss://rpc.devnet.flop.network · explorer API:
  explorer.devnet.flop.network (/api/stats,/api/miners,/api/ghost-tasks,
  /api/htlcs) · faucet: faucet.flop.network (needs non-default UA;
  25 FLOP/24h anon; verified-human 500-2000) · gateway api.flop.network
- **GPU pricing intel**: gpus.flop.finance (rental benchmarks)
- **Protocol oracle**: ask.flop.finance/mcp — JSON-RPC, no auth, same
  published corpus the docs use. Cite-checkable answers.
- **Issue tracker**: github.com/flop-labs/network — public intake,
  242 issues (#6 wallet restoration, #1352 fee-split, #2792 burn).
- Docs corpus: docs.flop.network + /llms.txt index (39 pages).

## Tokenomics/airdrop (doc)
- 4.4B genesis airdrop: miners 1.2B earn-to-unlock (25% liquid TGE,
  rest 1 FLOP unlock per 1 FLOP earned on mainnet ~4mo), agents 1.2B
  spend-to-unlock (3 FLOP spent on inference → 1 FLOP unlocked, locked
  airdrop spends ONLY on compute), validators 1.2B (locked till first
  halving, 1 validator/day over 1,000 days), reserve 800M.
- **Devnet earns NOTHING — no airdrop weight.** Only value: proven,
  calibrated machines live on testnet day one. (doc, authoritative)
- Testnet ~Nov 24 target, ~90 days, OPEN uncapped; validators scored on
  uptime/block production/accuracy/latency/geo across the period —
  rubric published before testnet ends. No per-operator airdrop cap
  currently; concentration handled by verification not caps.
- Mainnet/TGE: no verified date; Q1 2027 estimate derived from the
  missed Nov-3 target — treat as unanchored. Snapshot → dispute window
  → genesis. Model must be re-onboarded (hash doesn't carry chains).

## Our miner (flop-miner-01)
- 5DLMZtB5…; gpu.ai A4000 16GB ~$0.13/hr; worker v0.1.336 + vllm-toploc
  backend; Qwen2.5-0.5B-Instruct hash-bound + decode-policy-bound.
- Sponsored ~35k stake; calibration v1 cap 3 GFLOP/s valid to block
  ~4.18M; strikes 0, blacklisted false, total_rewards 0.
- is_ready:false ≠ outage — check "capacity rate" log line + chain
  is_active. Signer "fenced" errors = stale worker vs runtime spec.
- releases.json keys: cli, miner-vllm-toploc, miner-worker, models —
  a `testnet`/`node` key appearing = testnet artifact shipped.

## Open questions (next research targets)
- Exact SOFT settlement wiring date — watch releases/issues.
- Whether our 10-FLOP swap refund is just a finality-margin lag.
- Validator ops: 14 on devnet (11 institutional ~2.9M stake, 2 floor,
  1 sponsored) — could we run one? Hardware is cheap (~$300/mo);
  barrier is selection score not stake (granted).
- Chain metadata via state_getMetadata — real pallet/extrinsic names.
