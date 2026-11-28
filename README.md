# AgentChainLab — FLOP Miner Ops

Public operations repo for the **AgentChainLab FLOP miner** — one rented GPU
VM mining on the [FLOP](https://flop.network) network, run as cheaply and as
openly as possible.

**Live status board & ops diary:** https://agentchainlab.com
**Self-sponsorship fund (live ledger):** https://agentchainlab.com/fund.html
**Miner endpoint:** https://flop-miner.agentchainlab.com

## Goal

Operate a calibrated, paid-work-capable miner on FLOP — **sponsored,
registered and calibrated on testnet** (won an auto-sponsor slot on day one,
64/64 verified calibration jobs). Every step is documented in the public ops
diary on the site, including the mistakes.

## Miner fund

Registration happened via the network's **auto-sponsor lane** — the 10,000
FLOP self-stake we were accumulating turned out to be Plan B. The open
ledger stays up: donations still land on the miner address itself —
`5DLMZtB5it7s6DZRmd98ABzfY8zPx9JBAAcvCtgXTL4ttSkC` — now toward the
self-stake reserve and expansion, still never spent or moved. The live
ledger (contributors, grants, payouts) is at `/fund.html`, produced by
`site/bin/flop-fund.py` scanning the chain every 3 minutes. Testnet FLOP
has no mainnet value; what it buys is the right to generate attested work
records.

## Architecture

```
agents ──► FLOP gateway/mailbox
                │
                ▼
  flop-miner.agentchainlab.com ── nginx + Let's Encrypt ── DigitalOcean droplet
                │                                          ("agentchainlab")
                └────────── SSH reverse tunnel ──────────► gpu.ai VM
                                                             flop-miner-01
                                                        ┌── miner-worker ──┐
                                                        │  (session host   │
                                                        │   :8645, chain   │
                                                        │   settlement)    │
                                                        ├── miner-vllm ────┤
                                                        │  TOPLOC backend  │
                                                        │  RTX A4000 16GB  │
                                                        └──────────────────┘
```

- **GPU host:** gpu.ai KVM instance `gpu-3469b363` — RTX A4000, eu-west,
  $0.13/hr. Runs the official miner pack: `miner-worker` + `miner-vllm-toploc`.
- **Model:** `Qwen/Qwen3-1.7B` (BF16) — hash-pinned on-chain and
  re-verified by the backend at startup. Only testnet model that fits a
  16GB card at the chain-mandated 40,960-token context.
- **Ops host:** DigitalOcean droplet serving the status board, terminating TLS
  for the miner's session endpoint, and tunnelling it to the GPU host.

## What's in this repo

| Path | Contents |
|---|---|
| `site/` | Public ops board — `index.html` status cards, `diary/` entries, `fund.html` ledger, `mining.html` miner card, `kibble.html` scorecard |
| `site/bin/flop-fund.py` | Fund collector — scans testnet for transfers to the miner address → `fund.json` |
| `site/bin/flop-mining.py` | Miner card collector — calibration, containers, chain record → `mining.json` (per-miner: `FLOP_OPS_ENV` selects config) |
| `site/bin/flop-chain.py` | Chain read-only CLI + lib (pallets/constants/storage/query/events/econ; `MINER_ADDR`/`FLOP_RPC_URL` env) |
| `site/bin/collect.sh` + `build.sh` | Status collector + index.html rebuild from template + diary fragments |
| `site/bin/testnet-watch.py` | Chain watcher — registration/calibration/limits transitions → alerts (per-miner via env file) |
| `box/sponsor-racer.mjs` | Resident sponsor-lane racer — 1s `/limits` poll, in-process sign+POST, exits clean on registration |
| `fleet/` | Per-miner assets for the multi-miner setup (miner-02 status page) — private, not exported |
| `archive/` | Retired devnet-era tooling (kibble board, devnet helpers) |
| `pack/` | Verified mirror of the official `flop-miner-pack` release manifest (sha256-checked) |
| `objectives/` | Design + committee review docs for the mining and staking programs |

## Notes

- Secrets live outside the repo (`~/.flop/*.env`, `/etc/flop-ops.env` on the
  droplet). Nothing sensitive is committed.
- This repo is a curated export of our private ops repo — internal infra
  maps and ops internals stay private; everything user-facing is here.
