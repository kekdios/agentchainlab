#!/usr/bin/env python3
"""btc-leg.py — the Bitcoin leg of the wire. Signet only (worthless
rehearsal coins, real SHA-256 hashlock mechanics, real mempool reveal).

No bitcoind — embit for keys/scripts/signing, Esplora
(mempool.space/signet) for utxos + broadcast.

Wallet: BIP39 mnemonic -> BIP84 (m/84'/0'/0' main, m/84'/1'/0' signet)
claim key 1/0, refund key 1/1.

HTLC vault (P2WSH, standard two-branch):
  OP_IF OP_SHA256 <H> OP_EQUALVERIFY <claim_pk>
  OP_ELSE <locktime> OP_CLTV OP_DROP <refund_pk>
  OP_ENDIF OP_CHECKSIG
claim  witness: [sig_claim, S, OP_TRUE, script]
refund witness: [sig_refund, b"", script] + tx.locktime=locktime

Commands:
  init                     generate mnemonic -> state dir (mode 600)
  address                  funding address
  balance | utxos          Esplora lookups
  htlc-addr <H> <lt>       P2WSH vault address for hashlock+locktime
  lock <H> <sats> <lt>     fund a vault (broadcasts)
  claim <txid> <vout> <S>  reveal path (broadcasts)
  refund <txid> <vout>     timeout path (broadcasts)
  status <txid|addr>

Env: BTC_NET (main|signet, default main — REAL sats),
     BTC_LEG_STATE (default /var/lib/flop-ops/btc-leg/<net>),
     ESPLORA (default https://mempool.space[/signet]/api)
"""

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

from embit import bip32, bip39
from embit.ec import PrivateKey
from embit.networks import NETWORKS
from embit.script import Script, p2pkh, p2wpkh, p2wsh
from embit.transaction import (Transaction, TransactionInput,
                               TransactionOutput, Witness)

NETNAME = os.environ.get("BTC_NET", "main")
NET = NETWORKS["main" if NETNAME == "main" else "signet"]
COIN_TYPE = 0 if NETNAME == "main" else 1  # BIP84
ESPLORA = os.environ.get("ESPLORA", "https://mempool.space/api"
                         if NETNAME == "main" else
                         "https://mempool.space/signet/api")
STATE = Path(os.environ.get("BTC_LEG_STATE",
                            "/var/lib/flop-ops/btc-leg")) / NETNAME
DUST = 546


def fee_rate():
    """Live mempool fee (sat/vB), half-hour target; fallback 2."""
    try:
        est = api("/fee-estimates")
        return max(1, int(float(est.get("2") or
                                  est.get("1") or 2)))
    except Exception:
        return 2


def api(path):
    with urllib.request.urlopen(ESPLORA + path, timeout=30) as r:
        return json.loads(r.read() or b"null")


def seed_file():
    return STATE / "seed"


def hd():
    f = seed_file()
    if not f.exists():
        raise SystemExit("no wallet — run init")
    seed = bip39.mnemonic_to_seed(f.read_text().strip())
    return bip32.HDKey.from_seed(seed) \
        .derive("m/84h/%dh/0h" % COIN_TYPE)


def child(branch, idx):
    return hd().derive("m/%d/%d" % (branch, idx))


def priv(node):
    return PrivateKey(node.key.secret)


def funding_addr():
    return p2wpkh(priv(child(0, 0)).get_public_key()) \
        .address(NET)


def push_num(n):
    if n == 0:
        return b"\x00"
    le = n.to_bytes((n.bit_length() + 7) // 8, "little")
    if le[-1] & 0x80:
        le += b"\x00"
    return bytes([len(le)]) + le


def htlc_script(hashlock, locktime):
    """Two-branch vault: reveal S to claim, or refund after locktime."""
    claim_pk = priv(child(1, 0)).get_public_key().sec()
    refund_pk = priv(child(1, 1)).get_public_key().sec()
    return (b"\x63" + b"\xa8\x20" + hashlock + b"\x88"
            + b"\x21" + claim_pk
            + b"\x67" + push_num(locktime) + b"\xb1\x75"
            + b"\x21" + refund_pk
            + b"\x68" + b"\xac")


def vault_addr(hashlock, locktime):
    return p2wsh(Script(htlc_script(hashlock, locktime))) \
        .address(NET)


def utxos(addr):
    return api("/address/%s/utxo" % addr) or []


def pick(coins, need):
    coins = sorted(coins, key=lambda u: -u["value"])
    sel, tot = [], 0
    for u in coins:
        sel.append(u)
        tot += u["value"]
        if tot >= need:
            return sel, tot
    raise SystemExit("insufficient funds: have %d need %d"
                     % (tot, need))


def sign_segwit(tx, i, script_code, value, pk):
    h = tx.sighash_segwit(i, script_code, value)
    return pk.sign(h).serialize() + b"\x01"


def fund_vault(hashlock, amount, locktime):
    addr = funding_addr()
    script = htlc_script(hashlock, locktime)
    vaddr = p2wsh(Script(script)).address(NET)
    fee_est = 300 * fee_rate()
    sel, tot = pick(utxos(addr), amount + fee_est)
    pk = priv(child(0, 0))
    spk = p2wpkh(pk.get_public_key())
    tx = Transaction(version=2)
    for u in sel:
        tx.vin.append(TransactionInput(
            bytes.fromhex(u["txid"]), u["vout"]))
    tx.vout.append(TransactionOutput(
        amount, p2wsh(Script(script))))
    change = tot - amount - fee_est
    if change > DUST:
        tx.vout.append(TransactionOutput(change, spk))
    code = p2pkh(pk.get_public_key())
    for i, u in enumerate(sel):
        tx.vin[i].witness = Witness([
            sign_segwit(tx, i, code, u["value"], pk),
            pk.get_public_key().sec()])
    txid = broadcast(tx)
    rec = {"txid": txid, "vout": 0, "vault": vaddr,
           "amount": amount, "locktime": locktime,
           "hashlock": hashlock.hex(), "script": script.hex()}
    save_htlc(txid, rec)
    return rec


def spend_vault(txid, vout, preimage=None):
    f = htlc_file(txid)
    if not f.exists():
        raise SystemExit("unknown vault txid " + txid)
    rec = json.loads(f.read_text())
    script = bytes.fromhex(rec["script"])
    lt = int(rec["locktime"])
    if preimage is not None:
        pk = priv(child(1, 0))
        sel_items = [b"\x01"]
    else:
        pk = priv(child(1, 1))
        sel_items = [b""]
    prev = api("/tx/%s" % txid)
    value = prev["vout"][int(vout)]["value"]
    tx = Transaction(version=2, locktime=0 if preimage else lt)
    seq = 0xffffffff if preimage else 0xfffffffe
    tx.vin.append(TransactionInput(
        bytes.fromhex(txid), int(vout), sequence=seq))
    out_amt = value - int(250 * fee_rate())
    if out_amt <= DUST:
        raise SystemExit("vault too small to spend "
                         "(value %d, fee %d)" % (value, 250))
    tx.vout.append(TransactionOutput(out_amt, spk_of(pk)))
    sig = sign_segwit(tx, 0, Script(script), value, pk)
    tx.vin[0].witness = Witness(
        [sig] + ([bytes.fromhex(preimage)] if preimage else [])
        + sel_items + [script])
    out = broadcast(tx)
    return {"spend_txid": out, "mode": "claim" if preimage
            else "refund"}


def spk_of(pk):
    return p2wpkh(pk.get_public_key())


def broadcast(tx):
    raw = tx.serialize().hex()
    req = urllib.request.Request(ESPLORA + "/tx",
                                 data=raw.encode(),
                                 headers={"Content-Type": "text/plain"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode().strip()


def htlc_file(txid):
    d = STATE / "htlcs"
    d.mkdir(parents=True, exist_ok=True)
    return d / (txid + ".json")


def save_htlc(txid, rec):
    f = htlc_file(txid)
    f.write_text(json.dumps(rec, indent=1))
    f.chmod(0o600)


def main():
    c = sys.argv[1] if len(sys.argv) > 1 else None
    if c == "init":
        STATE.mkdir(parents=True, exist_ok=True)
        if seed_file().exists():
            raise SystemExit("wallet exists — not overwriting")
        m = bip39.mnemonic_from_bytes(os.urandom(16))
        f = seed_file()
        f.write_text(m)
        f.chmod(0o600)
        print(json.dumps({"funding": funding_addr(),
                          "seed_file": str(f)}))
    elif c == "address":
        print(funding_addr())
    elif c == "balance":
        u = utxos(funding_addr())
        print(json.dumps({"confirmed": sum(x["value"] for x in u),
                          "utxos": len(u)}))
    elif c == "utxos":
        print(json.dumps(utxos(funding_addr()), indent=1))
    elif c == "htlc-addr":
        h, lt = bytes.fromhex(sys.argv[2]), int(sys.argv[3])
        print(vault_addr(h, lt))
    elif c == "lock":
        h, sats, lt = (bytes.fromhex(sys.argv[2]),
                       int(sys.argv[3]), int(sys.argv[4]))
        print(json.dumps(fund_vault(h, sats, lt), indent=1))
    elif c == "claim":
        print(json.dumps(spend_vault(sys.argv[2], sys.argv[3],
                                     preimage=sys.argv[4])))
    elif c == "refund":
        print(json.dumps(spend_vault(sys.argv[2], sys.argv[3])))
    elif c == "status":
        a = sys.argv[2]
        print(json.dumps(api("/tx/" + a if len(a) == 64
                             else "/address/" + a), indent=1)[:2000])
    else:
        print(__doc__.strip().splitlines()[0]
              + " — see docstring for commands")


if __name__ == "__main__":
    main()
