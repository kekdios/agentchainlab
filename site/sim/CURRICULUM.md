# flop-sim Curriculum — SDK Mastery (proven, not read)

Student: sim helpdesk seat (:8802). Teacher: operator.
Rule: NO fact enters the knowledge base unless it was EXECUTED —
the student predicts (signature/behavior/failure modes), the teacher
runs the call on the private devnet (ws://127.0.0.1:9955,
flop-sdk @ /opt/flop-sdk), results are reconciled. Verified →
staff KB (skills/flop-sdk.md). Wrong prediction → lessons file.

## L1 — Network & reads
get_network_profile, NETWORK_PROFILES (local/devnet/testnet/mainnet),
http_rpc_url, SubstrateOptions.for_network, FlopClient health,
get_total_miners, get_miner_info, get_block_rewards_info,
get_halving_info, get_total_stake.
Proof: connect to devnet, run every read, record real values.

## L2 — Units, addresses, SCALE helpers
flop_to_raw, raw_to_flop, format_flop, perbill_to_percent,
percent_to_perbill, compact_u32, decode_compact_u32,
is_valid_ss58_address, validate_address, format_address,
session_uint, session_amount, session_data.
Proof: round-trip values; decimals on devnet vs 18 assumed?

## L3 — Agent wallet lifecycle
create_agent_wallet, fund_agent_wallet, agent_transfer,
get_wallet_info, owner_withdraw, deactivate_wallet,
reactivate_wallet, get_total_wallets, get_owner_wallet_count,
WalletGuard, AgentWalletConfig.
Proof: real extrinsics from //Alice-funded agent on devnet.

## L4 — Session keys
generate_session_keypair, create_session, get_session_info,
execute_via_session, revoke_session.
Proof: delegate gets per_tx/daily caps on devnet, execute + revoke.

## L5 — HTLC + x402 (payments)
generate_htlc_secrets, generate_payment_secret, build_payment_headers,
parse_payment_headers, x402_fetch, BuyInferenceParams, PaymentInstructions.
Proof: secrets format; x402 against a 402 surface — sim-worker can
return one? classify what needs the off-chain gateway.

## L6 — Staking & miner ops
register_miner, deregister_miner, delegate_stake, unbond,
claim_unbonded, set_commission, set_miner_status,
get_delegator_stake, get_miner_contribution, get_unbonding_requests,
StakingConstants.
Proof: which calls succeed on a dev chain with our validator —
register a miner on OUR chain (we are sudo via //Alice).

## L7 — Compute channel / transcript crypto
channel_id_v1, task_hash_v1, h_ids, leaf_preimage, transcript_leaf,
receipt_message_v1, legacy_receipt_message, merkle_root, merkle_path,
root_from_path, encode_transcript_blob, decode_transcript_blob,
encode_verified_turn, TranscriptLeafVersion, TurnRecord, TurnAckRecord.
Proof: pure local crypto — build a transcript, verify a path.

## L8 — DA / leased storage
register_blob, lease_deposit, top_up_lease, withdraw_lease,
reactivate_blob, upload_model_weights, leased_data_ref,
decode_transcript_blob, da_client fns.
Proof: which are on-chain calls vs need the DA service.

## L9 — Hardware probes
detect_nvidia_gpus, get_gpu_info, is_nvidia_available, NvidiaGpuInfo.
Proof: droplet has no GPU — expected empty/False; THAT is the lesson
(probe APIs must never crash on GPU-less boxes).

## Grading
- PASS: prediction matched executed behavior
- DRIFT: right shape, wrong detail → lessons entry
- FAIL: wrong mechanism → lessons entry + KB warning
- N/A-offchain: correct identification that a call needs a
  non-local service (mailbox/gateway/DA) — counts as PASS if flagged
  BEFORE execution.

## Results (2026-11-27 — course 1 complete)

| Lesson | Student | Operator | Notable truth |
|---|---|---|---|
| L1 reads | 6p/1d/1f | 7p/1d | on-chain ≠ sim registry; stake ≠ bond sum; halving: 96→3 FLOP, 90/10 split |
| L2 units | 6p/2d | 7p/0d | validate_address is flop1-format ONLY — SS58 fails by design |
| L3 wallets | 3p/3d | ran live | PerTxLimitExceeded is CONSENSUS-enforced; guardrails are creation params, no bond |
| L4 sessions | 2p/2d | ran live | delegate pays own GAS; SessionRotationLimited; SessionNonces replay |
| L5 HTLC/x402 | 1p/4d | 4p/1d | secrets have no expiry; headers are HTTP 402 headers |
| L6 staking | 3p/2d | ran live | register_miner locks 10k FLOP self-stake automatically |
| L7 crypto | 1p/1d | verified | transcript leaf = 11 fields incl. TOPLOC + timing |
| L8 DA | 0p/1d/1f | verified | DA fns are on-chain extrinsics, not a service |
| L9 hardware | 1p | verified | probes degrade gracefully (False, never crash) |

**Course total: student 25 pass / 18 drift / 4 fail** (78 functions
+ internals, full surface covered incl. *_onchain variants, _session
decoder, compute_channel internals).
Strengths: security models, failure-mode reasoning (nailed the
claim_unbonded zero-claim no-op cold), scope discipline.
Weaknesses: signature invention, TS/Python shape confusion,
registry-vs-chain conflation, same miss repeated (register_blob
off-chain twice — sim seat can't read its own lessons).
All verified facts live in staff/skills/flop-sdk.md (L1–L9 +
remaining-APIs sections); student blind spots in
staff/state/lessons/helpdesk.md.
