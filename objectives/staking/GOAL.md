# Objective: STAKING (sandbox) — StakeBoard lock-up test process

## Executive summary

**What this is:** a ~90-day live test of our exchange processes using
play tokens. StakeBoard v2 (`0x816dD5aD…8Ca5e`, chain 424242) lets
anyone lock **fakeFLOP** until **2027-02-21**, accrue a time-weighted
score (tokens × seconds), and `claim()` **fakeUSDC** yield — ~100%/day,
global pool cap 100k/day, funded with 3M fakeUSDC we minted.

**Why it exists as a business objective:** it is NOT a staking
business — it is the public proving ground for the exchange's hard
problems in miniature:
- **Lock → track → claim → settle** is the same shape as an HTLC swap
  (funds committed, conditions checked, payout on proof)
- **On-chain accounting under adversarial play** — volunteers probe
  the claim math, cooldowns, caps, and epoch boundaries for free
- **A retention game** that keeps testers on the venue between swaps:
  faucet → stake → scoreboard → claim — the engagement loop runs on
  the same users the exchange needs
- **Honest-label credibility** — "no airdrop, testing only" copy;
  real-yield claims never made

**Scope boundary (explicit):** FLOP-protocol staking (MinerStaking,
sponsor/delegator yield share) is NOT this objective — it is a
dependency of MINING and was analyzed separately as a bonus exercise.

**Success metric:** ≥X external stakers survive the full 90-day
window with zero contract exploits, claim-math bugs, or drain events.
Kill criteria: contract bug found in the wild (the test fails) or
nobody plays (no signal generated).
