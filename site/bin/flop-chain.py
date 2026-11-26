#!/usr/bin/env python3
"""flop-chain.py — our own FLOP chain interaction library + CLI.

Read-only for now: constants, storage, decoded events, domain helpers.
Deployed at /usr/local/lib/flop-ops/flop-chain.py with substrate-interface
in /usr/local/lib/flop-ops/pylib.

Usage:
  flop-chain.py pallets                       list runtime pallets
  flop-chain.py constants [Pallet]            constant values (all or one)
  flop-chain.py storage [Pallet]              storage items (all or one)
  flop-chain.py query Pallet Item [key]       single storage query
  flop-chain.py count Pallet Map [cap]        bounded map count
  flop-chain.py events <block|a-b>            decoded events for block(s)
  flop-chain.py us                            our miner's full record
  flop-chain.py network                       network totals snapshot
  flop-chain.py econ                          supply/emission/rewards/dilution
  flop-chain.py runtime [path]                download runtime WASM+hash
"""
import hashlib
import json
import os
import sys

PYLIB = "/usr/local/lib/flop-ops/pylib"
if PYLIB not in sys.path:
    sys.path.insert(0, PYLIB)

# Endpoint: testnet default (post-migration 2026-11-26); override per-network:
#   FLOP_RPC_URL=wss://rpc.devnet.flop.network flop-chain.py pallets
WS_RPC = os.environ.get("FLOP_RPC_URL", "wss://testnet.flop.network")
MINER_ADDR = "5DLMZtB5it7s6DZRmd98ABzfY8zPx9JBAAcvCtgXTL4ttSkC"
OUR_CHANNEL = ("0x8e70fec05a140e4bd225a4b8c84cc8e33bdadc2a13038bc6242e"
               "8c77a5feabba")
INTERESTING = {"ComputeChannel", "HwCalibration", "MinerStaking",
               "SyntheticTasks", "HasStation", "MinerSlashing",
               "AirdropVesting", "TokenClaim", "FlopPoui",
               "ModelRegistry", "ModelRegistrars", "FlopSubsidy",
               "WorkVesting", "MeteringVerifier", "Balances",
               "BlockRewards", "Treasury"}
TREASURY_POT = "5EYCAe5kjJEU9CJ4QMep83WeQNvGwkWpknkU7r3Q3w7n13iV"


def connect():
    from substrateinterface import SubstrateInterface
    si = SubstrateInterface(url=WS_RPC)
    si.init_runtime()
    return si


def q(si, mod, fn, params=None):
    try:
        r = si.query(mod, fn, params or [])
        return r.value if hasattr(r, "value") else r
    except Exception as e:
        return {"err": str(e)[:120]}


def cmd_pallets(si):
    return sorted(m["name"] for m in si.get_metadata_modules())


def cmd_constants(si, pallet=None):
    out = {}
    for c in si.get_metadata_constants():
        if pallet and c.get("module_name") != pallet:
            continue
        out.setdefault(c["module_name"], {})[c["constant_name"]] = \
            c["constant_value"]
    return out


def cmd_storage(si, pallet=None):
    out = {}
    for s in si.get_metadata_storage_functions():
        if s["storage_name"].startswith(":"):
            continue
        if pallet and s.get("module_name") != pallet:
            continue
        out.setdefault(s["module_name"], []).append(
            s["storage_name"] + " (" + str(s.get("type_class")) + ")")
    return out


def cmd_count(si, mod, fn, cap=120):
    n = len(list(si.query_map(mod, fn, [], max_results=int(cap))))
    return f"{n}+" if n >= int(cap) else n


def cmd_events(si, spec):
    if "-" in spec:
        a, b = spec.split("-", 1)
        blocks = range(int(a), int(b) + 1)
    else:
        blocks = [int(spec)]
    out = []
    for bn in blocks:
        h = si.get_block_hash(bn)
        for ev in si.get_events(h):
            try:
                v = ev.value
                out.append({
                    "block": bn,
                    "pallet": v.get("module_id") or v.get("module"),
                    "event": v.get("event_id") or v.get("event"),
                    "attrs": v.get("attributes"),
                })
            except Exception:
                out.append({"block": bn, "raw": str(ev)[:200]})
    return out


def cmd_us(si):
    return {
        "miner": q(si, "MinerStaking", "Miners", [MINER_ADDR]),
        "ghost_stats": q(si, "SyntheticTasks", "MinerGhostStatsStore",
                         [MINER_ADDR]),
        "airdrop_grant": q(si, "AirdropVesting", "AirdropGrants",
                           [MINER_ADDR]),
        "channel": q(si, "ComputeChannel", "Channels", [OUR_CHANNEL]),
        "strikes": q(si, "MinerSlashing", "StrikeRecords", [MINER_ADDR]),
        "sponsor_positions": q(si, "MinerStaking",
                               "SponsorPositionsByMiner", [MINER_ADDR]),
        "calibration": q(si, "HwCalibration", "BenchmarkBurstCaps",
                         [MINER_ADDR]),
    }


def cmd_network(si):
    return {
        "settlement_paused": q(si, "HasStation", "SettlementPaused"),
        "subsidy_active": q(si, "FlopSubsidy", "SubsidyActive"),
        "subsidy_end_block": q(si, "FlopSubsidy", "SubsidyEndBlock"),
        "total_miner_paid": q(si, "ComputeChannel", "TotalMinerPaid"),
        "total_gn_credited": q(si, "ComputeChannel", "TotalGnCredited"),
        "total_burned": q(si, "ComputeChannel", "TotalBurned"),
        "total_refunded": q(si, "ComputeChannel", "TotalRefunded"),
        "miners_slashed": q(si, "MinerSlashing", "TotalMinersSlashed"),
        "proof_count": q(si, "FlopPoui", "ProofCount"),
        "poui_epoch": q(si, "FlopPoui", "CurrentEpoch"),
        "model_count": q(si, "ModelRegistry", "ModelCount"),
        "total_miners": q(si, "MinerStaking", "TotalMiners"),
        "total_stake": q(si, "MinerStaking", "TotalStake"),
        "grant_count": q(si, "AirdropVesting", "ActiveGrantCount"),
        "ghost_issued": q(si, "SyntheticTasks", "TotalIssued"),
        "ghost_completed": q(si, "SyntheticTasks", "TotalCompleted"),
        "ghost_incorrect": q(si, "SyntheticTasks", "TotalIncorrect"),
        "htlc_escrows": q(si, "HasStation", "EscrowCounter"),
        "forward_listings": cmd_count(si, "ComputeChannel",
                                      "ForwardListings"),
    }


def cmd_econ(si):
    """Token economics: supply, emission, reward pools, dilution, ours.
    All values raw (1e18 = 1 FLOP); callers convert for display."""
    miner = q(si, "MinerStaking", "Miners", [MINER_ADDR]) or {}
    acct = (q(si, "System", "Account", [MINER_ADDR]) or {}).get("data", {})
    return {
        "total_issuance": q(si, "Balances", "TotalIssuance"),
        "rewards": {
            "miner": q(si, "BlockRewards", "TotalMinerRewards"),
            "validator": q(si, "BlockRewards", "TotalValidatorRewards"),
            "agent": q(si, "BlockRewards", "TotalAgentRewards"),
            "staker": q(si, "BlockRewards", "TotalStakerRewards"),
            "last_distribution_block":
                q(si, "BlockRewards", "LastDistributionBlock"),
            "period_miners": q(si, "BlockRewards", "PeriodMiners"),
        },
        "emission": {c["constant_name"]: c["constant_value"]
                     for c in si.get_metadata_constants()
                     if c.get("module_name") == "BlockRewards"},
        "subsidy": {
            "active": q(si, "FlopSubsidy", "SubsidyActive"),
            "end_block": q(si, "FlopSubsidy", "SubsidyEndBlock"),
            "labs_total": q(si, "FlopSubsidy", "TotalLabsSubsidy"),
            "foundation_total":
                q(si, "FlopSubsidy", "TotalFoundationSubsidy"),
        },
        "airdrop": {
            "grant_count": q(si, "AirdropVesting", "ActiveGrantCount"),
            "grants_created": q(si, "AirdropVesting", "TotalGrantsCreated"),
            "claim_active": q(si, "TokenClaim", "ClaimActive"),
            "total_claimable": q(si, "TokenClaim", "TotalClaimable"),
        },
        "total_miners": q(si, "MinerStaking", "TotalMiners"),
        "total_stake": q(si, "MinerStaking", "TotalStake"),
        "treasury_pot": (q(si, "System", "Account", [TREASURY_POT]) or {})
                        .get("data"),
        "our": {
            "rewards_earned": miner.get("total_rewards_earned"),
            "self_stake": miner.get("self_stake"),
            "delegated_stake": miner.get("delegated_stake"),
            "is_active": miner.get("is_active"),
            "balance_free": acct.get("free"),
            "balance_reserved": acct.get("reserved"),
        },
        # Frontier lanes — the wider pallet surface discovered 2026-11-20.
        # Mostly empty today; each is a tripwire for when the protocol
        # switches a lane on (vesting, ZK settlement, assets, governance,
        # paid storage, bootstrap lock).
        "frontier": {
            "work_vesting": {
                "total_escrowed": q(si, "WorkVesting", "TotalEscrowed"),
                "epoch_gn_entries": cmd_count(si, "WorkVesting",
                                              "CurrentEpochGn", 50),
                "epoch_start_block":
                    q(si, "WorkVesting", "EpochStartBlock"),
                "active_miners":
                    len(q(si, "WorkVesting", "ActiveMiners") or []),
                "our_escrow":
                    q(si, "WorkVesting", "Escrows", [MINER_ADDR]),
            },
            "da_blobs": q(si, "DaRegistry", "TotalBlobs"),
            "agents": q(si, "AgentIdentity", "GlobalStats"),
            "next_asset_id": q(si, "Assets", "NextAssetId"),
            "referendum_count": q(si, "Referenda", "ReferendumCount"),
            "bounty_count": q(si, "Bounties", "BountyCount"),
            "miners_slashed": q(si, "MinerSlashing", "TotalMinersSlashed"),
            "slashing_burned": q(si, "MinerSlashing", "TotalBurned"),
            "guest_image_pinned":
                q(si, "MeteringVerifier", "GuestImageId") is not None,
            "emergency_paused": q(si, "EmergencyPause", "PausedCount"),
            "emergency_overrides":
                q(si, "EmergencyOverride", "TotalOverrides"),
            "bootstrapped_at": q(si, "RetainedBootstrap", "BootstrappedAt"),
            "paid_storage_reservations":
                q(si, "PaidStorage", "NextReservationId"),
            "campaign": q(si, "Campaign", "Campaign") is not None,
        },
    }


def cmd_runtime(si, path="/var/lib/flop-ops/expert/runtime.wasm"):
    try:
        code = si.rpc_request("state_getRuntimeCode", [])
    except Exception as e:
        return {"error": f"state_getRuntimeCode unavailable: {e}"}
    blob = bytes.fromhex((code.get("result") or "").removeprefix("0x"))
    h = hashlib.sha256(blob).hexdigest()
    if path:
        with open(path, "wb") as f:
            f.write(blob)
    return {"bytes": len(blob), "sha256": h, "path": path}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    si = connect()
    if cmd == "pallets":
        out = cmd_pallets(si)
    elif cmd == "constants":
        out = cmd_constants(si, args[0] if args else None)
    elif cmd == "storage":
        out = cmd_storage(si, args[0] if args else None)
    elif cmd == "query":
        out = q(si, args[0], args[1], args[2:] or None)
    elif cmd == "count":
        out = cmd_count(si, args[0], args[1],
                        args[2] if len(args) > 2 else 120)
    elif cmd == "events":
        out = cmd_events(si, args[0])
    elif cmd == "us":
        out = cmd_us(si)
    elif cmd == "network":
        out = cmd_network(si)
    elif cmd == "econ":
        out = cmd_econ(si)
    elif cmd == "runtime":
        out = cmd_runtime(si, args[0] if args else
                          "/var/lib/flop-ops/expert/runtime.wasm")
    else:
        sys.exit(f"unknown command {cmd!r} — see --help")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
