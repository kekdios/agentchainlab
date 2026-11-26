# MINING — general design

## Value chain

```
GPU inference work  ->  PoUI metering (verified)  ->  settled sessions
      ^                                                 |
      |                                                 v
   our miner serving models                     FLOP rewards per epoch
```

The chain verifies work happened correctly (calibration sets a
hardware cap; metering settles per-session). A miner's income = its
share of settled obligations, gated by calibration validity and
stake standing.

## Components

1. **Compute host** — gpu.ai A4000 16GB, containerized worker serving
   the calibration-tier model (Qwen2.5-0.5B today; larger models as
   the network demands them).
2. **Chain identity** — miner keypair (sr25519 AccountId), sponsored
   stake ~35k FLOP, session/enclave keys, calibration records.
3. **Settlement layer** — compute channels + sessions: customer locks
   budget, miner serves, obligation settles per metering proofs.
4. **Ops layer** — collect.sh probes → status.json; flop-expert
   (committee) watches miner_health and pages on degradation.

## Revenue mechanics (as understood, 2026-11)

- Calibration establishes `cap` (verified GFLOP/s). Work can't exceed cap.
- Distribution epochs pay miners proportional to settled work.
- Earn-to-unlock vesting (`work_vesting`) gates reward withdrawal
  behind continued contribution — rewards vest, not dump.
- Sponsored stake lets the network back proven machines; strikes and
  blacklisting are the punishment path.

## Posture

Bootstrap investment phase: we pay ~$4.4/day to hold a calibrated,
monitored seat until paid sessions open. The asset being built is
not the GPU — it is the operational record and readiness.
