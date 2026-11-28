#!/usr/bin/env python3
"""wire-api.py — the desk. Job-submit facade over the FLOP escrow rail.

A wire = open_escrow with an And[Hash(S)] policy leaf, settle via
satisfy_escrow on preimage reveal — the same standard the venue-coord
(exchange/coord.py) proved. Agents (or cron) POST /jobs; the desk
generates and HOLDS the preimage (venue role), locks the escrow
on-chain, settles on request. Deterministic — no brains in the path.

Endpoints:
  GET  /health
  GET  /jobs                     list wires
  POST /jobs                   {"payee": ss58, "amount": FLOP,
                                "deadline_blocks"?, "counterparty"?,
                                "chain"?, "btc_sats"?,
                                "btc_locktime_blocks"?} -> locked wire
                                (btc_sats also locks a P2WSH vault on
                                 real BTC under the same hashlock)
  GET  /jobs/<escrow_id>       status (record + on-chain escrow +
                                live btc conf count)
  POST /jobs/<id>/settle       reveal preimage -> satisfy on-chain
                                (gated: needs >=1 conf on btc vault)
  POST /jobs/<id>/reveal       expose the preimage (wire reference)
                                (same gate — S IS the settlement)
  POST /jobs/<id>/btc-claim    spend the vault by reveal (same gate)
  POST /jobs/<id>/refund       refund after deadline

Env: FLOP_RPC (default ws://127.0.0.1:9955 private devnet),
     WIRE_SEED (default //Alice), WIRE_STATE, WIRE_PORT (8803).
Call indices discovered from metadata at connect — never hardcoded.
"""

import json
import os
import struct
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, "/usr/local/lib/flop-ops/pylib")
import hashlib
import secrets

from substrateinterface import SubstrateInterface, Keypair
from scalecodec.base import ScaleBytes

PORT = int(os.environ.get("WIRE_PORT", "8803"))
STATE = Path(os.environ.get("WIRE_STATE", "/var/lib/flop-ops/wire-api"))
SEED = os.environ.get("WIRE_SEED", "//Alice")
RPC = os.environ.get("FLOP_RPC", "ws://127.0.0.1:9955")
FLOP_UNIT = 10**18
BTC_LEG = os.environ.get("BTC_LEG_BIN",
                         "/usr/local/lib/flop-ops/btc-leg.py")
BTC_NET = os.environ.get("BTC_NET", "main")
ESPLORA = os.environ.get("BTC_ESPLORA", "https://mempool.space/api")
MIN_CONFS = int(os.environ.get("WIRE_MIN_CONFS", "1"))


def btc(*args, timeout=90):
    """Call btc-leg.py (the BTC side of the desk). Returns parsed
    stdout json or raises."""
    import subprocess
    env = dict(os.environ, BTC_NET=BTC_NET)
    p = subprocess.run(["python3", BTC_LEG] + [str(a) for a in args],
                       capture_output=True, text=True,
                       timeout=timeout, env=env)
    if p.returncode != 0:
        raise RuntimeError("btc-leg: " +
                           (p.stderr or p.stdout).strip()[:300])
    return json.loads(p.stdout)


def btc_tip():
    import urllib.request
    with urllib.request.urlopen(
            ESPLORA + "/blocks/tip/height", timeout=15) as r:
        return int(r.read())


def btc_confs(txid):
    """Live confirmation count from Esplora (0 if unconfirmed)."""
    import urllib.request
    try:
        with urllib.request.urlopen(
                ESPLORA + "/tx/%s/status" % txid, timeout=15) as r:
            st = json.loads(r.read())
    except Exception:
        return -1
    if not st.get("confirmed"):
        return 0
    return btc_tip() - st["block_height"] + 1


def secret_ok(j):
    """Gate for anything that publishes S: if the job carries a BTC
    leg, the vault lock must have >= MIN_CONFS confirmations. The
    preimage is the settlement itself — never leak it against an
    unconfirmed vault."""
    if not j.get("btc"):
        return True, None
    c = btc_confs(j["btc"]["txid"])
    return c >= MIN_CONFS, c

_si = None
_kp = None
_pallet = None


def compact(n):
    if n < 64:
        return bytes([n << 2])
    if n < 16384:
        return struct.pack("<H", (n << 2) | 1)
    if n < (1 << 30):
        return struct.pack("<I", (n << 2) | 2)
    b = n.to_bytes((n.bit_length() + 7) // 8, "little")
    return bytes([((len(b) - 4) << 2) | 3]) + b


def conn():
    global _si, _kp, _pallet
    if _si is not None:
        try:  # liveness — ws to the validator drops on idle
            _si.get_chain_head()
            return _si
        except Exception:
            _si = None
    _si = SubstrateInterface(url=RPC)
    _si.init_runtime()
    _kp = Keypair.create_from_uri(SEED)
    for p in _si.metadata.pallets:
        if p.name == "HasStation":
            _pallet = p.value["index"]
    if _pallet is None:
        raise RuntimeError("HasStation pallet missing from runtime")
    return _si


def submit(call):
    si = conn()
    co = si.create_scale_object("GenericCall",
                                data=ScaleBytes("0x" + call.hex()))
    co.decode()
    try:
        nonce = int(si.rpc_request(
            "system_accountNextIndex",
            [_kp.ss58_address]).get("result") or 0)
    except Exception:
        nonce = si.get_account_nonce(_kp.ss58_address) or 0
    payload = si.generate_signature_payload(call=co, era="00",
                                            nonce=nonce, tip=0)
    sig = _kp.sign(payload)
    body = (b"\x00" + _kp.public_key + b"\x01" + sig
            + b"\x00" + compact(nonce) + compact(0) + b"\x00" + call)
    ext = compact(len(body) + 1) + b"\x84" + body
    return si.rpc_request("author_submitExtrinsic",
                          ["0x" + ext.hex()]).get("result")


def _call_index(name):
    si = conn()
    cf = si.get_metadata_call_function("HasStation", name)
    v = cf.value if hasattr(cf, "value") else cf
    return v["index"]


def open_escrow(payee_pk, amount_raw, hashlock, deadline_blocks):
    conn()
    call = (bytes([_pallet, _call_index("open_escrow")])
            + payee_pk + amount_raw.to_bytes(16, "little")
            + b"\x00" + compact(1) + b"\x00" + hashlock
            + deadline_blocks.to_bytes(4, "little"))
    return submit(call)


def satisfy_escrow(escrow_id, preimage):
    conn()
    call = (bytes([_pallet, _call_index("satisfy_escrow")])
            + escrow_id + compact(1) + compact(len(preimage)) + preimage)
    return submit(call)


def refund_escrow(escrow_id):
    conn()
    call = bytes([_pallet, _call_index("refund_escrow")]) + escrow_id
    return submit(call)


def escrow_state(escrow_id_hex):
    si = conn()
    v = si.query("HasStation", "Escrows", [escrow_id_hex])
    return v.value if v is not None else None


def find_escrow_id(from_block, funder, payee, amount_units):
    """escrow_id from EscrowOpened events — deterministic, same source
    as flop_client.escrows_opened. Event attrs carry {escrow_id, funder,
    payee, amount, deadline} — NO hashlock — so we match the full
    (funder, payee, amount) tuple scanning FORWARD from the submit
    block: the first matching event after submission is ours. Never
    falls back to map scan (could settle a DIFFERENT escrow owned by
    the same account)."""
    si = conn()
    deadline = time.time() + 20
    while time.time() < deadline:
        head = si.get_block_number(si.get_chain_finalised_head())
        for bn in range(from_block, head + 1):
            for ev in si.get_events(si.get_block_hash(bn)):
                e = ev.value
                if e.get("event_id") != "EscrowOpened":
                    continue
                a = e.get("attributes") or {}
                if a.get("funder") == funder and \
                        a.get("payee") == payee and \
                        a.get("amount") == amount_units:
                    return a.get("escrow_id")
        time.sleep(1)
    return None


def store():
    STATE.mkdir(parents=True, exist_ok=True)
    f = STATE / "jobs.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {}


def save(jobs):
    (STATE / "jobs.json").write_text(json.dumps(jobs, indent=1))


def public(j):
    return {k: v for k, v in j.items() if k != "_preimage"}


def create_job(body):
    payee = body.get("payee")
    amount = float(body.get("amount", 0))
    if not payee or amount <= 0:
        return 400, {"error": "payee (ss58) + positive amount required"}
    deadline = int(body.get("deadline_blocks", 200))
    conn()
    try:
        payee_pk = Keypair(ss58_address=payee).public_key
    except Exception:
        return 400, {"error": "bad payee ss58"}

    pre_image = secrets.token_hex(32)
    hashlock = hashlib.sha256(bytes.fromhex(pre_image)).digest()
    head0 = _si.get_block_number(_si.get_chain_finalised_head())
    amount_units = int(amount * FLOP_UNIT)
    tx = open_escrow(payee_pk, amount_units, hashlock, deadline)
    escrow_id = find_escrow_id(head0, _kp.ss58_address, payee,
                               amount_units)
    rec = {
        "escrow_id": escrow_id, "hash_lock": "0x" + hashlock.hex(),
        "payee": payee, "amount": amount,
        "counterparty": body.get("counterparty"),
        "chain": body.get("chain", "btc"),
        "deadline_blocks": deadline,
        "status": "locked", "create_tx": tx,
        "funder": _kp.ss58_address, "ts": int(time.time()),
        "_preimage": pre_image,
    }
    if body.get("btc_sats"):
        lt = btc_tip() + int(body.get("btc_locktime_blocks", 144))
        rec["btc"] = btc("lock", hashlock.hex(),
                         int(body["btc_sats"]), lt)
        rec["btc_status"] = "locked"
    jobs = store()
    jobs[escrow_id or ("pending-%d" % rec["ts"])] = rec
    save(jobs)
    return 200, public(rec)


def settle_job(eid):
    jobs = store()
    j = jobs.get(eid)
    if not j:
        return 404, {"error": "no such job"}
    if j["status"] != "locked":
        return 400, {"error": "status=%s" % j["status"]}
    ok, confs = secret_ok(j)
    if not ok:
        return 409, {"error": "btc vault unconfirmed",
                     "confs": confs, "min": MIN_CONFS}
    esc = bytes.fromhex((j["escrow_id"] or eid).removeprefix("0x"))
    tx = satisfy_escrow(esc, bytes.fromhex(j["_preimage"]))
    j["status"] = "released"
    j["settle_tx"] = tx
    save(jobs)
    return 200, public(j)


def refund_job(eid):
    jobs = store()
    j = jobs.get(eid)
    if not j:
        return 404, {"error": "no such job"}
    esc = bytes.fromhex((j["escrow_id"] or eid).removeprefix("0x"))
    tx = refund_escrow(esc)
    j["status"] = "refunding"
    j["refund_tx"] = tx
    save(jobs)
    return 200, public(j)


def btc_claim_job(eid):
    jobs = store()
    j = jobs.get(eid)
    if not j:
        return 404, {"error": "no such job"}
    if not j.get("btc"):
        return 400, {"error": "no btc leg"}
    ok, confs = secret_ok(j)
    if not ok:
        return 409, {"error": "btc vault unconfirmed",
                     "confs": confs, "min": MIN_CONFS}
    r = btc("claim", j["btc"]["txid"], j["btc"]["vout"],
            j["_preimage"])
    j["btc_status"] = "claimed"
    j["btc"]["claim_txid"] = r["spend_txid"]
    save(jobs)
    return 200, public(j)


def job_status(eid):
    j = store().get(eid)
    if not j:
        return 404, {"error": "no such job"}
    out = public(j)
    if j.get("btc"):
        out["btc"]["confs"] = btc_confs(j["btc"]["txid"])
    try:
        out["onchain"] = escrow_state(j["escrow_id"] or eid)
    except Exception as e:
        out["onchain_error"] = str(e)[:120]
    return 200, out


class H(BaseHTTPRequestHandler):
    def _reply(self, code, obj):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def do_GET(self):
        if self.path == "/health":
            self._reply(200, {"ok": True, "jobs": len(store())})
        elif self.path == "/jobs":
            self._reply(200, {k: public(v) for k, v in store().items()})
        elif self.path.startswith("/jobs/"):
            self._reply(*job_status(self.path[6:]))
        else:
            self._reply(404, {"error": "no route"})

    def do_POST(self):
        if self.path == "/jobs":
            try:
                self._reply(*create_job(self._body()))
            except Exception as e:
                self._reply(500, {"error": str(e)[:200]})
        elif self.path.endswith("/settle"):
            try:
                self._reply(*settle_job(self.path[6:-7]))
            except Exception as e:
                self._reply(500, {"error": str(e)[:200]})
        elif self.path.endswith("/reveal"):
            j = store().get(self.path[6:-7])
            if not j:
                self._reply(404, {"error": "no such job"})
                return
            ok, confs = secret_ok(j)
            if not ok:
                self._reply(409, {"error": "btc vault unconfirmed",
                                  "confs": confs, "min": MIN_CONFS})
                return
            self._reply(200, {"escrow_id": j["escrow_id"],
                              "preimage": j["_preimage"],
                              "hash_lock": j["hash_lock"]})
        elif self.path.endswith("/btc-claim"):
            try:
                self._reply(*btc_claim_job(self.path[6:-10]))
            except Exception as e:
                self._reply(500, {"error": str(e)[:200]})
        elif self.path.endswith("/refund"):
            try:
                self._reply(*refund_job(self.path[6:-7]))
            except Exception as e:
                self._reply(500, {"error": str(e)[:200]})
        else:
            self._reply(404, {"error": "no route"})


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
