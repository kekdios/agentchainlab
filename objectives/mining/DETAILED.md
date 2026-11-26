# MINING — detailed design

## Current position (verified 2026-11-24)

| Field | Value |
|---|---|
| Devnet miners | 760 total; ours active, sponsored 34,999.99 |
| Calibration | v4 active, cap 34,127 GFLOP/s, expires ~2026-11-30 (~453k blocks) |
| Sessions | 0 all-time; rewards $0 this epoch |
| Worker image | 0.1.418 current; CLI 0.1.455 |
| Testnet | TotalMiners=0, 6 validators (fresh keys, not devnet identities), our account does not exist |
| Cost | ~$4.37/day (gpu.ai ~$95 + droplets ~$38 per month) |

## Infrastructure

- **gpu.ai VM**: A4000, worker containers (up 4d, GPU idle w/ weights
  resident — normal when sessions=0).
- **Ops droplet** (agentchainlab): collect.sh every 5min, flop-expert
  pulse+cron, notify.py → Telegram, tg-replyd ask channel.
- **flop-chain.py**: our own read layer — `us`, `econ`, `network`,
  `query Pallet Item` for ad-hoc state.

## Economics to validate

- Reward path: sessions open → settled obligations → epoch
  distribution → vesting unlock. Every link is unproven on us yet —
  sessions=0 means zero empirical yield data.
- Next distribution boundary (devnet): block ~4,579,200; period_miners
  currently 0 → no payout expected, but the boundary tests tracking.
- Break-even model: cost $4.4/day fixed; variable = reward rate at
  session availability. Unknown until testnet economics activate.

## Risks

1. **Testnet access** — invite-only today; account unfunded. If seats
   are allocated by lottery or reputation criteria we can't see,
   positioning may not convert. (Expert watches genesis checklist.)
2. **Calibration expiry ~Nov 30** — renewal required; miss = cap drops,
   testnet-readiness gate fails.
3. **Economics unknown** — rewards could underprice GPU cost for
   small single-GPU operators; earn-to-unlock adds liquidity lag.
4. **Sponsored stake is not ours** — can be withdrawn; losing it
   means needing self-bond to stay active.
5. **Single GPU / single host** — no failover; downtime at the wrong
   moment (genesis seat window) is the real risk, not average uptime.
6. **Legacy channel 0x8e70 still in-flight** — unresolved session
   residue from cal v1.

## KPIs the Expert tracks

miner state, GPU util/temp, calibration status + blocks-left,
image drift vs releases.json pin, sessions count, spend/day,
rewards accrued, strikes/blacklisted/fenced flags, testnet
regready + our account existence.
