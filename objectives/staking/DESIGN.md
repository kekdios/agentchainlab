# STAKING (sandbox) — general design

## What the process tests

```
faucet ──► approve+lock ──► score accrual ──► claim() ──► pool payout
fakeFLOP   venue verifies    on-chain          day-epoch    fakeUSDC
                │              math            accounting    ERC-20
                └── exchange-process analogues ────────────────┘
```

Every stage maps to an exchange mechanic we need to trust:

| StakeBoard stage | Exchange-process analogue |
|---|---|
| approve + lock tokens | user deposits into HTLC leg |
| score = amount × time | time-weighted accounting (same math as swap deadlines/escrow duration) |
| claim() → mint/transfer yield | settlement payout path — ERC-20 transfer correctness under load |
| day-epoch pool cap | budget/cap accounting like faucet epoch budgets |
| lock-until timestamp | timelock semantics — the same failure shape as HTLC refund windows |

## Contract mechanics (live, verified paying)

- Lock fakeFLOP → `scoreOf(addr) = locked × (now − lockStart)`
- `claimable(addr) = score / 86400` fakeUSDC (~100%/day equivalent)
- Global pool cap 100,000 fakeUSDC/day, day-epoch accounting on-chain
- Pool funded: 3,000,000 fakeUSDC minted to contract
- v1 `0x58c4…98A0C` abandoned (no yield) → v2 `0x816d…8Ca5e` shipped
  after the "make it pay" feedback — the iteration loop works.

## The funnel it feeds

anon 10 / sig-verified 250 / miner 1000 fakeFLOP+fakeUSDC from
/api/faucet → stake → scoreboard row → claim → sandbox swaps.
Two confirmed stakers: 0x7099…79C8 (5 fakeFLOP) and our agent
self-test 0x3C44…93BC (10 fakeFLOP, faucet→approve→stake→claim
verified end-to-end by an autonomous agent — the exact flow an
external agent must execute).

## Why fake yield still teaches

The tokens are worthless but the failure modes are real: claim-math
overflows, epoch-boundary races, pool-cap exhaustion, approval
frontruns, lock-timing edge cases. A volunteer who drains the demo
pool finds a bug that would have cost real money on a real yield
contract.
