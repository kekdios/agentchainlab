# STAKING (sandbox) — detailed design

## Contract surface (StakeBoard v2, chain 424242)

- `lock(amount)` — transfers fakeFLOP in, sets lockStart, adds to
  stakerCount; no unlock until 2027-02-21 (unix 1803168000)
- `scoreOf(addr)` — locked × elapsed seconds (view; anvil quirk:
  returns 0 until next mined block since chain mines on-demand)
- `claimable(addr)` — score/86400 fakeUSDC
- `claim()` — pays accrued fakeUSDC, resets score base; day-epoch
  accounting caps global payouts at 100k/day
- Admin: pool funding, no user-fund withdrawal path (non-custodial
  within demo scope)

## What the test actually exercises

1. **ERC-20 approve→transferFrom→claim cycle** — same signature flow
   as exchange EVM-leg fills.
2. **Time-weight math under real clocks** — block.timestamp-based
   score accrual; anvil mines only on txs so scoring visibility lags
   (a REAL testnet gotcha external testers will hit on real chains).
3. **Cap + budget accounting** — day-epoch pool cap is the same
   accounting shape as faucet epoch budgets and future fee accounting.
4. **Agent-legibility** — our own agent ran faucet→approve→stake
   with no human help; if an agent can complete it, the flow is
   documented well enough (SKILL.md proof).
5. **Scoreboard as telemetry** — stakerCount, lock distribution,
   claim cadence = a public engagement dashboard for the venue.

## What it does NOT test

- Real yield sustainability (pool is our minted liability)
- FLOP-chain staking mechanics (MinerStaking/sponsor/delegator —
  separate analysis, out of this silo's scope)
- Slashing/punishment paths (nothing slashes on the sandbox)
- Adversarial economic attacks on a token with real value

## Risks

1. **Pool drain is bounded but real** — 3M fakeUSDC liability; a
   claim-math bug drains it (that's the test working, but it kills
   the board's credibility for that epoch).
2. **Lock is absolute** — 90 days, no exit; testers who didn't read
   will feel burned. The "no airdrop — testing only" copy must stay
   loud.
3. **Anvil chain fragility** — a chain reset nukes all locks/scores;
   the demo's whole history is one VM's state file.
4. **Confusion with real staking** — naming overlap with FLOP
   MinerStaking; site copy must never imply real yield.
5. **Gaming is the point but also the noise** — bot stakers inflate
   the scoreboard; keep metrics interpreted honestly.

## Instrumentation

StakeBoard rows surfaced on /sandbox.html scoreboard; expert watches
contract balance + stakerCount via digest; any claim-path anomaly =
brief-worthy.
