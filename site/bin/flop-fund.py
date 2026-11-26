#!/usr/bin/env python3
"""Self-sponsorship fund tracker — scans testnet for transfers into
MINER_ADDR, writes /var/www/agentchainlab/fund.json for fund.html.
Cron every 3 min."""
import json, os, sys, time, urllib.request

sys.path.insert(0, "/usr/local/lib/flop-ops/pylib")

RPC = "wss://testnet.flop.network"
MINER = "5DLMZtB5it7s6DZRmd98ABzfY8zPx9JBAAcvCtgXTL4ttSkC"
GOAL = 10000
STATE = "/var/lib/flop-ops/fund-state.json"
OUT = "/var/www/agentchainlab/fund.json"
ENV = "/etc/flop-ops.env"

def env():
    out = {}
    for ln in open(ENV):
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1); out[k] = v
    return out

def tg(e, text):
    tok, chat = e.get("TELEGRAM_BOT_TOKEN"), e.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        urllib.request.urlopen(urllib.request.Request(
            "https://api.telegram.org/bot%s/sendMessage" % tok,
            data=json.dumps({"chat_id": chat, "text": text}).encode(),
            headers={"Content-Type": "application/json"}, method="POST"), timeout=15)
    except Exception:
        pass

def main():
    from substrateinterface import SubstrateInterface
    # WSS gateway 429s under load — retry with jitter, skip cycle on failure
    si = None
    import random
    for _ in range(4):
        try:
            si = SubstrateInterface(url=RPC)
            si.init_runtime()
            break
        except Exception:
            time.sleep(5 + random.random() * 15)
            si = None
    if si is None:
        print("rpc connect failed; skipping cycle")
        return
    head = si.get_block_number(None)
    try:
        st = json.load(open(STATE))
    except Exception:
        # no history scan needed: we've never spent, so inbound transfers
        # provably cannot predate this run — but a pre-existing balance
        # (e.g. a faucet drip) is recorded as a labelled seed entry
        st = {"last_block": head, "contributions": []}
    seen = {c["block"] for c in st["contributions"] if c["block"] is not None}
    acct = si.query("System", "Account", [MINER]).value or {}
    bal = (acct.get("data", {}) or {}).get("free", 0) / 1e18
    if not st["contributions"] and bal > 0:
        st["contributions"].append({
            "block": None, "from": "pre-existing balance",
            "amount": bal,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "paid": False,
            "note": "balance present at fund launch (faucet grant)"})

    e = env()
    last = st["last_block"]
    new = []
    # scan blocks since last run for Transfers to MINER
    for n in range(last + 1, head + 1):
        try:
            h = si.get_block_hash(n)
            evs = si.get_events(h)
        except Exception:
            continue
        for ev in evs:
            try:
                v = ev.value
                if (v.get("module_id") == "Balances"
                        and v.get("event_id") == "Transfer"):
                    a = v.get("attributes") or {}
                    if a.get("to") == MINER and n not in seen:
                        rec = {"block": n, "from": a.get("from"),
                               "amount": a.get("amount", 0) / 1e18,
                               "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                   time.gmtime()),
                               "paid": False}
                        new.append(rec); seen.add(n)
            except Exception:
                continue
    if new:
        st["contributions"].extend(new)
        tot = sum(c["amount"] for c in new)
        tg(e, "[fund] +%.1f FLOP from %d transfer(s) — balance %.1f/%d"
              % (tot, len(new), bal, GOAL))
    st["last_block"] = head
    json.dump(st, open(STATE, "w"), indent=1)
    out = {"address": MINER, "goal_flop": GOAL, "balance_flop": round(bal, 2),
           "scanned_to": head,
           "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "contributions": st["contributions"]}
    json.dump(out, open(OUT, "w"), indent=1)
    print(time.strftime("%H:%M:%S"), "head", head, "bal", bal,
          "new", len(new))

if __name__ == "__main__":
    main()
