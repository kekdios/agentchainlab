#!/usr/bin/env python3
"""Collect FLOP testnet mining status → /var/www/agentchainlab/mining.json

Pulls session/info (auth'd), worker log events, sponsor log, container +
GPU state from the gpu.ai miner box, parses it into the JSON that
/mining.html polls. Runs on cron (*/5). Never writes secrets to output.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ENV_FILE = os.environ.get("FLOP_OPS_ENV", "/etc/flop-ops.env")
OUT = Path("/var/www/agentchainlab/mining.json")
MINER_DIR = "/opt/flop-miner-testnet"
WORKER_CONTAINER = "flop-miner-01-worker-1"
DRIFT_FILE = Path(os.environ.get("DRIFT_FILE", "/var/lib/flop-ops/last-drift"))
WORKSIG_FILE = Path(os.environ.get("WORKSIG_FILE", "/var/lib/flop-ops/last-worksig"))
NOTIFY = "/usr/local/lib/flop-ops/notify.py"
FLOP_CHAIN = "/usr/local/lib/flop-ops/flop-chain.py"

REMOTE_CMD = r"""
tok=$(grep -m1 '^SESSION_AUTH_TOKEN=' {MINER_DIR}/miner.env 2>/dev/null | cut -d= -f2)
echo "==INFO=="
info=""; for i in 1 2 3; do
  info=$(curl -sf --max-time 8 ${tok:+-H "Authorization: Bearer $tok"} http://127.0.0.1:8645/session/info 2>/dev/null) && break
  info=""; sleep 2
done
echo "$info"
echo
echo "==FENCE=="
fence=$(curl -sf --max-time 6 ${tok:+-H "Authorization: Bearer $tok"} http://127.0.0.1:8645/internal/signer-fence 2>/dev/null)
echo "$fence"
echo
echo "==LOG=="
docker logs -t {WORKER_CONTAINER} --tail 400 2>&1 | tail -250
echo "==SPONSOR=="
tail -40 /var/log/flop-sponsor.log 2>/dev/null
echo "==DOCKER=="
docker ps --format '{{.Names}}|{{.Status}}'
echo "==GPU=="
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null
echo "==ENV=="
grep -E '^(WORKER_NAME|MODEL_NAME|FLOP_WORKER_IMAGE)=' {MINER_DIR}/miner.env
"""

# Log lines worth surfacing in the activity feed.
KEEP_RE = re.compile(
    r"calibration|capacity rate|session host|chain settle|session[- ]"
    r"serv|endpoint ad|inventory|fenc|enrol|registered|bond|slash|settle|"
    r"verified job|job[s]?\b|error|fail|disconnect|refus", re.I)
DROP_RE = re.compile(
    r"ghost-task/|every 2000|polling https|miner-worker\.mjs|node:internal|"
    r"RPC-CORE|Failed WS Request|^\s+at |subscrib|known hosts|^\s*$",
    re.I)


def load_env():
    d = {}
    try:
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                d[k] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return d


def sections(raw):
    out, cur = {}, None
    for line in raw.splitlines():
        m = re.match(r"^==(\w+)==$", line.strip())
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def fetch(env):
    key = env.get("VM_SSH_KEY", "/root/.ssh/flop_vast")
    host = env.get("VM_SSH_HOST", "127.0.0.1")
    port = env.get("VM_SSH_PORT", "22")
    cmd = [
        "ssh", "-i", key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=12",
        "-o", "StrictHostKeyChecking=accept-new", "-p", port,
        f"root@{host}", "bash", "-s",
    ]
    remote = REMOTE_CMD.replace("{MINER_DIR}", MINER_DIR).replace(
        "{WORKER_CONTAINER}", WORKER_CONTAINER)
    p = subprocess.run(cmd, input=remote, capture_output=True,
                       text=True, timeout=90)
    if p.returncode != 0:
        raise RuntimeError(f"ssh rc={p.returncode}: {p.stderr[:200]}")
    return sections(p.stdout)


def parse_sponsor(txt):
    # Settled sponsorship legs from /var/log/flop-sponsor.log
    legs = re.findall(
        r'"kind":\s*"(\w+)"[^}]*?"amountRaw":\s*"(\d+)"[^}]*?'
        r'"txHash":\s*"(0x[0-9a-f]+)"[^}]*?"state":\s*"(\w+)"', txt, re.S)
    out = {"settled": False, "legs": []}
    seen = set()
    for kind, raw, tx, state in legs:
        if tx in seen:                # sponsor log repeats the same tx set
            continue
        seen.add(tx)
        out["legs"].append({
            "kind": kind,
            "flop": round(int(raw) / 1e18, 4),
            "tx": tx, "state": state,
        })
        if state == "settled":
            out["settled"] = True
    return out


def f18(x):
    try:
        return int(x) / 1e18
    except (TypeError, ValueError):
        return None


def fetch_econ(env=None):
    """On-chain token economics via flop-chain.py (one WS connect).
    FLOP-unit floats for balances, raw ints for counters/blocks."""
    env_ = dict(os.environ)
    if env and env.get("MINER_ADDR"):
        env_["MINER_ADDR"] = env["MINER_ADDR"]
    for _ in range(2):
        try:
            p = subprocess.run([FLOP_CHAIN, "econ"], capture_output=True,
                               text=True, timeout=120, env=env_)
            r = json.loads(p.stdout)
            if isinstance(r, dict) and "total_issuance" in r:
                break
            r = None
        except Exception:
            r = None
    if r is None:
        return {}
    rw = r.get("rewards") or {}
    em = r.get("emission") or {}
    sub = r.get("subsidy") or {}
    air = r.get("airdrop") or {}
    our = r.get("our") or {}
    pot = r.get("treasury_pot") or {}
    pm = rw.get("period_miners")
    return {
        "total_issuance": f18(r.get("total_issuance")),
        "rewards": {k: f18(rw.get(k))
                    for k in ("miner", "validator", "agent", "staker")},
        "last_distribution_block": rw.get("last_distribution_block"),
        "period_miners": len(pm) if isinstance(pm, list) else pm,
        "emission_per_block": f18(em.get("InitialRewardPerBlock")),
        "halving_interval_blocks": em.get("HalvingIntervalBlocks"),
        "max_halvings": em.get("MaxHalvings"),
        "distribution_period_blocks": em.get("DistributionPeriodBlocks"),
        "max_miners_per_period": em.get("MaxMinersPerPeriod"),
        "subsidy": {"active": sub.get("active"),
                    "end_block": sub.get("end_block"),
                    "labs_total": f18(sub.get("labs_total")),
                    "foundation_total": f18(sub.get("foundation_total"))},
        "airdrop": {"grant_count": air.get("grant_count"),
                    "grants_created": air.get("grants_created"),
                    "claim_active": air.get("claim_active"),
                    "total_claimable": f18(air.get("total_claimable"))},
        "total_miners": r.get("total_miners"),
        "total_stake": f18(r.get("total_stake")),
        "treasury_pot_free": f18(pot.get("free")),
        "our": {"rewards_earned": f18(our.get("rewards_earned")),
                "self_stake": f18(our.get("self_stake")),
                "delegated_stake": f18(our.get("delegated_stake")),
                "is_active": our.get("is_active"),
                "balance_free": f18(our.get("balance_free")),
                "balance_reserved": f18(our.get("balance_reserved"))},
        "frontier": norm_frontier(r.get("frontier") or {}),
    }


def norm_frontier(fr):
    """Frontier-lane tripwires. FLOP-unit floats where raw 1e18."""
    wv = fr.get("work_vesting") or {}
    ag = fr.get("agents") or {}
    return {
        "work_vesting": {
            "total_escrowed": f18(wv.get("total_escrowed")),
            "epoch_gn_entries": wv.get("epoch_gn_entries"),
            "epoch_start_block": wv.get("epoch_start_block"),
            "active_miners": wv.get("active_miners"),
            "our_escrow": wv.get("our_escrow"),
        },
        "da_blobs": fr.get("da_blobs"),
        "agents": {"total_agents": ag.get("total_agents"),
                   "total_tasks": ag.get("total_tasks"),
                   "total_volume": f18(ag.get("total_volume")),
                   "total_staked": f18(ag.get("total_staked"))},
        "next_asset_id": fr.get("next_asset_id"),
        "referendum_count": fr.get("referendum_count"),
        "bounty_count": fr.get("bounty_count"),
        "miners_slashed": fr.get("miners_slashed"),
        "slashing_burned": f18(fr.get("slashing_burned")),
        "guest_image_pinned": fr.get("guest_image_pinned"),
        "emergency_paused": fr.get("emergency_paused"),
        "emergency_overrides": fr.get("emergency_overrides"),
        "bootstrapped_at": fr.get("bootstrapped_at"),
        "paid_storage_reservations": fr.get("paid_storage_reservations"),
        "campaign": fr.get("campaign"),
    }


def parse_events(log):
    evs, prev = [], ""
    for line in log.splitlines():
        m = re.match(r"^(\S+)\s+(.*)$", line)
        if not m:
            continue
        ts, body = m.groups()
        body = body.strip()
        if not KEEP_RE.search(body) or DROP_RE.search(body):
            continue
        body = re.sub(r"\s+", " ", body)[:300]
        if body == prev:          # collapse consecutive dupes
            continue
        prev = body
        evs.append({"ts": ts.split(".")[0] + "Z" if "T" in ts else ts,
                    "line": body})
    return evs[-40:]


def main():
    global OUT, MINER_DIR, WORKER_CONTAINER
    env = load_env()
    # Per-miner overrides may come from either the process env or the env
    # file (FLOP_OPS_ENV selects the file on multi-miner crons).
    for k in ("MINING_OUT", "MINER_DIR", "WORKER_CONTAINER", "DRIFT_FILE",
              "WORKSIG_FILE"):
        v = os.environ.get(k) or env.get(k)
        if v:
            if k == "MINING_OUT":
                OUT = Path(v)
            elif k == "DRIFT_FILE":
                globals()["DRIFT_FILE"] = Path(v)
            elif k == "WORKSIG_FILE":
                globals()["WORKSIG_FILE"] = Path(v)
            else:
                globals()[k] = v
    try:
        s = fetch(env)
    except Exception as e:
        print(f"flop-mining: fetch failed: {e}", file=sys.stderr)
        # Keep last JSON alive but mark stale fetch.
        data = {"updated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                "error": str(e)}
        if OUT.exists():
            try:
                data = json.loads(OUT.read_text())
                data["updated"] = time.strftime("%Y-%m-%d %H:%M UTC",
                                                time.gmtime())
                data["error"] = str(e)
            except Exception:
                pass
        OUT.write_text(json.dumps(data) + "\n")
        return

    info, env_kv = {}, {}
    try:
        info = json.loads(s.get("INFO", ""))
    except Exception:
        pass
    fresh = bool(info)
    prev = {}
    if OUT.exists():
        # Endpoint fetch failed — keep last-good calibration/serving/identity.
        # prev is loaded either way: econ also falls back to it on RPC failure.
        try:
            prev = json.loads(OUT.read_text())
            if not info:
                info = prev.get("_info", {})
        except Exception:
            pass
    for line in s.get("ENV", "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env_kv[k.strip()] = v.strip()

    chain = {}
    if info.get("minerAddress"):
        try:
            chain = json.loads(urllib.request.urlopen(urllib.request.Request(
                "https://testnet.flopscan.io/api/miners/"
                + info["minerAddress"],
                headers={"User-Agent": "flop-ops/1.0"}), timeout=10).read())
        except Exception:
            pass
    net = {}
    try:
        net = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://testnet.flopscan.io/api/stats",
            headers={"User-Agent": "flop-ops/1.0"}), timeout=10).read())
    except Exception:
        pass

    econ = fetch_econ(env) or prev.get("econ") or {}

    try:
        fence = json.loads(s.get("FENCE", ""))
    except Exception:
        fence = {}
    if not fence:
        fence = prev.get("_fence", {})
    signer_fence = {
        "fenced": fence.get("fenced"),
        "sha256": fence.get("fenceSha256"),
        "recoverable_in_process": fence.get("recoverableInProcess"),
    } if fence else prev.get("signer_fence") or {}

    log = s.get("LOG", "")
    cal_log = re.search(
        r"\[calibration\] initial cap accepted: ([\d.]+) GFLOP/s from "
        r"(\d+) verified jobs \(window from #(\d+)\)", log)
    cap_log = re.search(
        r"capacity rate:\s*(?:set\s*)?([\d.]+) G_n/s for (\d+) sessions",
        log)
    cal = info.get("calibration") or {}
    img = env_kv.get("FLOP_WORKER_IMAGE", "")
    drift = DRIFT_FILE.read_text().strip() if DRIFT_FILE.exists() else "?"
    try:
        # Prefer a live check: running build vs releases.json latest. The
        # env's :stable tag can't string-match the digest-pinned release
        # (that produced a permanent false STALE on miner-01, 2026-11-27).
        relv = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://flop.network/releases.json",
            headers={"User-Agent": "flop-ops/1.0"}), timeout=10).read())
        latest = (relv.get("miner-worker") or {}).get("latest")
        wver = (info.get("image") or {}).get("version")
        if latest and wver:
            drift = "current" if wver == latest else "STALE"
    except Exception:
        pass
    docker = {}
    for line in s.get("DOCKER", "").splitlines():
        if "|" in line:
            n, st = line.split("|", 1)
            docker[n.strip()] = st.strip()
    sponsor = parse_sponsor(s.get("SPONSOR", ""))
    if not sponsor["legs"]:
        # Faucet-lane sponsorship leaves no local legs — read the on-chain
        # position so the tile shows the real posted bond.
        reg_tx = next((a.get("transactionHash")
                       for a in chain.get("stakingActivity") or []
                       if a.get("call") == "sponsorRegisterMiner"), None)
        for pos in chain.get("sponsorPositions") or []:
            st = pos.get("status") or "active"
            sponsor["legs"].append({
                "kind": "auto-" + (pos.get("role") or "sponsor"),
                "flop": round(int(pos.get("amount", "0") or 0) / 1e18, 4),
                "tx": reg_tx, "state": st,
            })
            if st == "active":
                sponsor["settled"] = True

    data = {
        "updated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "identity": {
            "miner": info.get("minerAddress", "?"),
            "worker": env_kv.get("WORKER_NAME", "testnet-miner-01"),
            "model": info.get("model", env_kv.get("MODEL_NAME", "?")),
            "model_hash": (info.get("modelIdentity") or {}).get(
                "modelHash", info.get("modelHash", "?")),
            "image": info.get("image", {}).get("version",
                                               img.split(":")[-1].split("@")[0]),
            "drift": drift,
        },
        "calibration": {
            "ready": cal.get("ready"),
            "state": cal.get("state"),
            "cap_gflops": cal.get("capGflopsPerSec",
                                  cal_log.group(1) if cal_log else None),
            "verified_jobs": int(cal_log.group(2)) if cal_log else None,
            "window_start": int(cal_log.group(3)) if cal_log else None,
            "accepted_at": cal.get("acceptedAt"),
            "expires_at": cal.get("expiresAt"),
            "current_block": cal.get("currentBlock"),
            "version": cal.get("calibrationVersion"),
        },
        "serving": {
            "is_ready": info.get("is_ready"),
            "sessions": info.get("sessions", 0),
            "capacity_gn": int(cap_log.group(1)) if cap_log else None,
            "capacity_sessions": int(cap_log.group(2)) if cap_log else None,
            "max_unacked_gn": info.get("maxUnackedGn"),
            "audit_handoff": info.get("audit_handoff_enabled"),
        },
        "chain": {
            "self_stake": int(chain.get("selfStake", "0") or 0) / 1e18,
            "sponsored_stake": int(chain.get("sponsoredStake", "0") or 0)
                / 1e18,
            "delegated_stake": int(chain.get("delegatedStake", "0") or 0)
                / 1e18,
            "is_active": chain.get("isActive"),
            "blacklisted": chain.get("blacklisted"),
            "strikes": chain.get("strikes"),
            "registered_block": chain.get("registeredBlock"),
            "commission": chain.get("commission"),
            "total_rewards": int(chain.get("totalRewards", "0") or 0) / 1e18,
            "total_slashed": int(chain.get("totalSlashed", "0") or 0) / 1e18,
            "gpu_inventory_declared":
                chain.get("declaredGpuInventory") is not None,
            "poui_rank": chain.get("pouiRank"),
            "work": chain.get("work") or {},
        },
        "network": {
            "sessions_htlc": net.get("totalHTLCs"),
            "sessions_active": net.get("activeHTLCs"),
            "proofs_24h": net.get("proofs24h"),
            "latest_block": net.get("latestBlockNumber"),
            "best_block": (net.get("finality") or {}).get("bestBlock"),
            "index_lag": ((net.get("finality") or {}).get("bestBlock") or 0)
                - (net.get("latestBlockNumber") or 0) or None,
            "registered_miners": net.get("registeredMiners"),
            "active_agents": net.get("activeAgents"),
        },
        "econ": econ,
        "signer_fence": signer_fence,
        "sponsorship": sponsor,
        "hardware": {"gpu": s.get("GPU", "")},
        "containers": docker,
        "events": parse_events(log),
        "info_stale": not fresh,
        "_info": info or prev.get("_info", {}),
        "_fence": fence,
    }
    OUT.write_text(json.dumps(data, indent=1) + "\n")

    # Email on on-chain work-counter transitions (first run seeds silently).
    w = data["chain"]["work"]
    sig = "work " + "|".join(
        str(w.get(k, 0)) for k in ("settled", "committed", "inFlight"))
    try:
        prev = WORKSIG_FILE.read_text().strip() \
            if WORKSIG_FILE.exists() else None
        WORKSIG_FILE.write_text(sig + "\n")
        if prev is not None and prev != sig:
            subprocess.run([NOTIFY, prev, sig,
                            "settled,committed,inFlight"], check=False)
    except Exception:
        pass


if __name__ == "__main__":
    main()
