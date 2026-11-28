#!/usr/bin/env python3
"""wire-flow.py — the waterfall driver. One shot per cron tick:

1. Settle any locked wire older than SETTLE_AFTER_S (the "flight landed")
2. Submit one new wire (payee round-robins the sandbox crew)

Deterministic treasury ops — the desk holds preimages; this script is
the scheduler. No brains anywhere. Cron every 10m.
Env: WIRE_API (default http://127.0.0.1:8803), WIRE_FLOW_STATE.
"""

import json
import os
import time
import urllib.request
from pathlib import Path

API = os.environ.get("WIRE_API", "http://127.0.0.1:8803")
STATE = Path(os.environ.get("WIRE_FLOW_STATE",
                            "/var/lib/flop-ops/wire-flow.json"))
SETTLE_AFTER_S = int(os.environ.get("WIRE_SETTLE_AFTER", "120"))
AMOUNT = float(os.environ.get("WIRE_AMOUNT", "1"))
DEADLINE = int(os.environ.get("WIRE_DEADLINE_BLOCKS", "200"))

# sandbox crew — dev keypairs, rotating destinations
PAYEES = [
    "5FLSigC9HGRKVhB9FiEo4Y3koPsNmBmLJbpXg2mp1hXcS59Y",  # //Charlie
    "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",  # //Dave
    "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy",  # //Eve
    "5HGjWAeFDfFCWPsjFQdVV2Msvz2XtMktvgocEZcCj68kUMaw",  # //Ferdie
]


def call(method, path, body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def main():
    now = time.time()
    st = json.loads(STATE.read_text()) if STATE.exists() else {"i": 0}
    jobs = call("GET", "/jobs")

    # land the wires that have been "in flight" long enough
    for jid, j in jobs.items():
        if j.get("status") == "locked" and now - j.get("ts", 0) \
                >= SETTLE_AFTER_S:
            r = call("POST", "/jobs/%s/settle" % jid)
            print("settled", jid[:18], "->", r.get("status"))

    # launch the next wire
    payee = PAYEES[st["i"] % len(PAYEES)]
    r = call("POST", "/jobs", {
        "payee": payee, "amount": AMOUNT,
        "deadline_blocks": DEADLINE,
        "counterparty": "tb1qauto%06d" % st["i"], "chain": "btc"})
    print("wired %.2f -> %s (%s)" % (AMOUNT, payee[:14],
                                     str(r.get("escrow_id"))[:18]))
    st["i"] += 1
    STATE.write_text(json.dumps(st))


if __name__ == "__main__":
    main()
