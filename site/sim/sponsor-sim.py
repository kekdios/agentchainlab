#!/usr/bin/env python3
"""sponsor-sim — the sandbox franchise office ("McDonald's University").

We hold the FFLOP treasury on chain 424242, so WE are the sponsor:
enroll a sim miner, bond the stake from our treasury, fire a ghost
calibration burst at it, grade the verify rate, issue a cap — the same
lifecycle the real faucet+issuer runs on testnet.

Usage:
  sponsor-sim.py enroll <name> [--jobs 8] [--cap 195]
  sponsor-sim.py burst <name> [--jobs 8]
  sponsor-sim.py list

Env: /etc/flop-ops-sim.env (SIM_WORKER, EVM_RPC, EVM_KEY, FFLOP, MODEL).
Registry: /var/lib/flop-ops/sim-registry.json
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, "/usr/local/lib/flop-ops/pylib")  # eth_keys/rlp

ENV = os.environ.get("FLOP_OPS_ENV", "/etc/flop-ops-sim.env")
REGISTRY = "/var/lib/flop-ops/sim-registry.json"
PASS_RATE = 0.89          # same bar as the real ghost burst
BOND = 35_000             # mirrors the real 35k sponsor bond


def env():
    out = {}
    try:
        for ln in open(ENV):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                out[k] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def registry():
    try:
        return json.load(open(REGISTRY))
    except Exception:
        return {"miners": {}}


def save_reg(r):
    os.makedirs(os.path.dirname(REGISTRY), exist_ok=True)
    json.dump(r, open(REGISTRY, "w"), indent=1)


def rpc(url, method, params):
    r = urllib.request.urlopen(urllib.request.Request(
        url, data=json.dumps(
            {"jsonrpc": "2.0", "method": method,
             "params": params, "id": 1}).encode(),
        headers={"Content-Type": "application/json"}), timeout=15)
    return json.loads(r.read()).get("result")


def bond_fflop(e, to_addr, amount):
    """Transfer `amount` FFLOP (18 dec) from the treasury/deployer key.
    Uses eth_keys for signing — same primitives exchange/coord.py
    uses, zero extra deps."""
    from eth_keys import keys as _k
    from eth_utils import keccak as _k3
    import rlp as _rlp
    key = e["EVM_KEY"]
    key = key[2:] if key.startswith("0x") else key
    pk = _k.PrivateKey(bytes.fromhex(key))
    me = pk.public_key.to_checksum_address()
    url = e.get("EVM_RPC", "http://127.0.0.1:8545")
    token = e["FFLOP"]
    chain = int(e.get("EVM_CHAIN", "424242"))
    sel = _k3(b"transfer(address,uint256)")[:4]
    data = sel + bytes.fromhex(to_addr[2:].lower().rjust(64, "0")) \
        + int(amount).to_bytes(32, "big")
    nonce = int(rpc(url, "eth_getTransactionCount",
                    [me, "pending"]), 16)
    gas_price = int(rpc(url, "eth_gasPrice", []), 16)
    tx = [nonce, gas_price, 300000,
          bytes.fromhex(token[2:]), 0, data, chain, 0, 0]
    sighash = _k3(_rlp.encode(tx))
    sig = pk.sign_msg_hash(sighash)
    signed = tx[:6] + [sig.v + chain * 2 + 35, sig.r, sig.s]
    return rpc(url, "eth_sendRawTransaction",
               ["0x" + _rlp.encode(signed).hex()])


def job(e, prompt, idx):
    req = urllib.request.Request(
        e.get("SIM_WORKER", "http://127.0.0.1:8801") + "/job",
        data=json.dumps({"id": "ghost-%d" % idx,
                         "prompt": prompt}).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


PROMPTS = [
    "State the model identifier you serve.",
    "Reply with exactly: CALIBRATION OK",
    "Summarize proof-of-inference in one sentence.",
    "What is 17 * 23? Reply with the number only.",
    "Give one sentence on why verification matters.",
    "Return the word READY.",
    "Name your backend engine.",
    "Reply: ACK",
]


def burst(e, name, jobs):
    r = registry()
    m = r.get("miners", {}).get(name)
    if not m:
        sys.exit("no such sim miner: %s (enroll first)" % name)
    results = []
    for i in range(jobs):
        t0 = time.time()
        try:
            d = job(e, PROMPTS[i % len(PROMPTS)], i)
            ok = bool(d.get("proof", {}).get("verified"))
            results.append((ok, time.time() - t0))
        except Exception as ex:
            results.append((False, time.time() - t0))
            print("  job %d err: %s" % (i, str(ex)[:80]))
        time.sleep(0.2)
    verified = sum(1 for ok, _ in results if ok)
    rate = verified / max(1, jobs)
    passed = rate >= PASS_RATE
    lat = sorted(x[1] for x in results)
    cap = int(200 - min(180, 1000 * lat[len(lat) // 2])) \
        if passed else 0
    m["calibration"] = {
        "state": "active" if passed else "failed",
        "verified_jobs": verified, "total_jobs": jobs,
        "rate": round(rate, 3), "cap_gflops": cap,
        "at": int(time.time())}
    r["miners"][name] = m
    save_reg(r)
    print("%s: %d/%d verified (%.0f%%) -> %s cap=%d" %
          (name, verified, jobs, rate * 100,
           "ACTIVE" if passed else "FAILED", cap))


def enroll(e, name, jobs):
    r = registry()
    if name in r.get("miners", {}):
        sys.exit("already enrolled: %s" % name)
    from eth_keys import keys as _k
    pk = _k.PrivateKey(os.urandom(32))
    addr = pk.public_key.to_checksum_address()
    m = {"addr": addr, "name": name, "enrolled": int(time.time()),
         "bond": BOND, "sponsor": "treasury", "calibration": None}
    try:
        txh = bond_fflop(e, addr, BOND * 10 ** 18)
        m["bond_tx"] = txh
        print("bond tx: %s" % txh)
    except Exception as ex:
        m["bond_tx"] = None
        print("bond failed (%s) — enrolling unbonded" % str(ex)[:120])
    r.setdefault("miners", {})[name] = m
    save_reg(r)
    print("enrolled %s at %s" % (name, addr))
    burst(e, name, jobs)


def main():
    e = env()
    args = sys.argv[1:]
    if not args or args[0] not in ("enroll", "burst", "list"):
        sys.exit(__doc__)
    cmd, rest = args[0], args[1:]
    if cmd == "list":
        r = registry()
        for n, m in r.get("miners", {}).items():
            c = m.get("calibration") or {}
            print("%-16s %s bond=%s cal=%s cap=%s" %
                  (n, m["addr"][:12] + "…", m.get("bond"),
                   (c or {}).get("state", "—"), (c or {}).get(
                       "cap_gflops", "—")))
        return
    if not rest:
        sys.exit("usage: sponsor-sim.py %s <name> [--jobs N]" % cmd)
    name = rest[0]
    jobs = 8
    if "--jobs" in rest:
        jobs = int(rest[rest.index("--jobs") + 1])
    (enroll if cmd == "enroll" else burst)(e, name, jobs)


if __name__ == "__main__":
    main()
