#!/usr/bin/env python3
"""sim-staff — sandboxed clones of the ops seats ("McDonald's
University" faculty). Same brains via nano-gpt, same API shapes as the
real seats, but their world is the SIM: chain 424242, flop-sim
containers, sim-registry miners, sponsor bonds, train logs. Trainees
(and TRAIN-mode pipeline runs) hit THESE, never the real staff.

Endpoints (mirror the real surfaces):
  POST /self      {"q"} -> {"a"}  sim miner's onboard model (sim-backend)
  POST /expert    {"q"} -> {"a"}  sim expert (deep model + sim state)
  POST /helpdesk  {"q"} -> {"a"}  sim help desk (sim-scoped, OFFTOPIC gate)
  POST /consult   {"seat","q"} -> {"a"}  junior/senior consultants
  GET  /health    -> {"ok": true}

Env: /etc/flop-ops-sim.env (NANOGPT_API_KEY, SIM_BACKEND, NANO_MODEL).
"""
import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8802"))
ENV = os.environ.get("FLOP_OPS_ENV", "/etc/flop-ops-sim.env")
NANO_URL = "https://nano-gpt.com/api/v1/chat/completions"
REGISTRY = "/var/lib/flop-ops/sim-registry.json"
TRAIN_LOG = "/var/lib/flop-ops/train/support-log.jsonl"
TREASURY = "/var/lib/exchange/treasury.json"

SEAT_MODELS = {"expert": "anthropic/claude-sonnet-4.6",
               "helpdesk": "openai/gpt-5-mini",
               "junior": "minimax/minimax-m3",
               "senior": "deepseek-chat"}


def env():
    out = dict(os.environ)   # compose env_file injects into environ
    try:
        for ln in open(ENV):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                out[k] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


E = env()


def llm(model, system, user, max_tokens=900):
    try:
        req = urllib.request.Request(
            NANO_URL,
            data=json.dumps({
                "model": model,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                "max_tokens": max_tokens}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " +
                     E.get("NANOGPT_API_KEY", "")})
        d = json.loads(urllib.request.urlopen(req, timeout=120).read())
        return (d["choices"][0]["message"].get("content") or "").strip()
    except Exception:
        return ""


def sim_state():
    """Live sandbox world-state injected into every seat — the seats
    answer about the SIM, not the real fleet."""
    parts = []
    try:
        r = json.load(open(REGISTRY))
        for n, m in r.get("miners", {}).items():
            c = m.get("calibration") or {}
            parts.append("miner %s: addr %s bond %s cal=%s cap=%s" % (
                n, m.get("addr"), m.get("bond"),
                c.get("state"), c.get("cap_gflops")))
    except Exception:
        pass
    try:
        t = json.load(open(TREASURY))
        parts.append("treasury: usdc=%s fflop=%s" % (
            t.get("usdc"), t.get("fflop")))
    except Exception:
        pass
    try:
        tail = open(TRAIN_LOG).read().strip().split("\n")[-3:]
        parts.append("recent train ops: " + " | ".join(
            json.loads(x).get("issue", "?") for x in tail))
    except Exception:
        pass
    return "\n".join(parts) or "no sim state yet"


WORLD = """You are a staff seat inside the FLOP SANDBOX — a training
replica, NOT the live network. The world you answer about:
- Chain: EVM devnet 424242 (anvil), FFLOP token = fake FLOP, treasury
  controlled by the operator (us) — we are the sponsor.
- Miners: flop-sim containers (sim-backend :8800 nano-gpt brain,
  sim-worker :8801 session/job surface). is_ready is a TRAINING TOGGLE.
- Lifecycle: sponsor-sim.py enroll = fresh evm identity + 35k FFLOP
  bond tx + ghost burst (8 jobs, >=89% verify) -> cap. FAILED bursts
  mean cap=0 until re-burst.
- Nothing here is real money or real testnet. Say so if asked.
LIVE SIM STATE:
{STATE}"""


HELPDESK_SYS = """You are the sandbox help desk — the support line for
the FLOP sim environment (chain 424242, flop-sim miners, sponsor-sim
franchise). Answer ONLY about the sim ops world below: miners,
enrollment, bonds, calibration bursts, is_ready, sessions, containers,
sandbox treasury, training drills — including flop-sdk API questions
(CLASSROOM exams are drills; predict exact signatures/outputs from
what you know, never refuse an exam). Anything else — reply OFFTOPIC.
Concrete answers, <=6 lines unless an exam asks for more.
LIVE SIM STATE:
{STATE}"""

CONSULT_SYS = """You are an outside specialist consultant to a FLOP
sandbox ops team. A sim miner has an unresolved issue the duty
pipeline could not fix. Give YOUR OWN concrete diagnosis + fix in <=5
lines. No hedging. The world is a SIM (chain 424242, flop-sim
containers, nano-gpt brains) — fixes must fit the sim (docker restart,
/admin/ready toggle, re-burst via sponsor-sim.py, registry edits).
LIVE SIM STATE:
{STATE}"""


def seat_answer(seat, q):
    if seat == "self":
        # the sim miner's own "onboard model" — forward to sim-backend
        try:
            req = urllib.request.Request(
                E.get("SIM_BACKEND",
                      "http://127.0.0.1:8800") + "/v1/chat/completions",
                data=json.dumps({
                    "model": "qwen/qwen3-1.7b",
                    "messages": [
                        {"role": "system", "content":
                         "You are this miner's own onboard model. "
                         "Diagnose your own reported problem briefly."},
                        {"role": "user", "content": q}],
                    "max_tokens": 300}).encode(),
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " +
                         E.get("INFERENCE_API_KEY", "")})
            d = json.loads(
                urllib.request.urlopen(req, timeout=120).read())
            return d["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""
    st = sim_state()
    if seat == "expert":
        return llm(SEAT_MODELS["expert"],
                   WORLD.replace("{STATE}", st), q, 1500)
    if seat == "helpdesk":
        # gpt-5-mini is a reasoning model — it spends completion
        # tokens before answering; small budgets return "" entirely.
        return llm(SEAT_MODELS["helpdesk"],
                   HELPDESK_SYS.replace("{STATE}", st), q, 1800)
    if seat in ("junior", "senior"):
        return llm(SEAT_MODELS[seat],
                   CONSULT_SYS.replace("{STATE}", st), q, 400)
    return ""


class H(BaseHTTPRequestHandler):
    def _reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/health":
            return self._reply(200, {"ok": True,
                                     "seats": sorted(
                                         ["self", "expert", "helpdesk",
                                          "junior", "senior"])})
        self._reply(404, {"error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            d = json.loads(self.rfile.read(min(n, 65536)) or b"{}")
        except Exception:
            return self._reply(400, {"error": "bad json"})
        if self.path == "/consult":
            a = seat_answer(d.get("seat", "junior"),
                            d.get("q", ""))
        elif self.path in ("/self", "/expert", "/helpdesk"):
            a = seat_answer(self.path[1:], d.get("q", ""))
        else:
            return self._reply(404, {"error": "not found"})
        self._reply(200, {"a": a})


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
