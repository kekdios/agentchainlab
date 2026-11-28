#!/usr/bin/env python3
"""sim-worker — the "miner" half of the sim pair.

Stands in for flop-miner-NN-worker-1: exposes the worker API surface
the ops pipeline touches (/session/info, /version), and runs jobs
against the sim-backend (nano-gpt brain). is_ready is a toggle file
so training can inject serving_not_ready on demand.

Endpoints:
  GET  /session/info  -> {"is_ready": bool, "sessions": n, ...}
  GET  /version       -> {"version": "sim-0.1"}
  POST /job           -> run one "inference job" through the backend
  POST /admin/ready   -> {"ready": true|false} flips is_ready
State: /state/sim-worker.json (shared volume).
"""
import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8645"))
BACKEND = os.environ.get("SIM_BACKEND", "http://backend:8000")
API_KEY = os.environ.get("INFERENCE_API_KEY", "")
STATE = "/state/sim-worker.json"


def state_load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"is_ready": True, "sessions": 0, "jobs_done": 0}


def state_save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=1)


def backend_chat(prompt):
    req = urllib.request.Request(
        BACKEND + "/v1/chat/completions",
        data=json.dumps({
            "model": "qwen/qwen3-1.7b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
        }).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + API_KEY})
    d = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return d["choices"][0]["message"]["content"]


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
        if self.path == "/session/info":
            s = state_load()
            return self._reply(200, {
                "is_ready": s.get("is_ready", False),
                "sessions": s.get("sessions", 0),
                "capacity_gn": 195,
                "audit_handoff": True,
                "worker": "sim-worker-01"})
        if self.path == "/version":
            return self._reply(200, {"version": "sim-0.1",
                                     "image": "0.1.520-sim"})
        self._reply(404, {"error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            d = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._reply(400, {"error": "bad json"})
        if self.path == "/admin/ready":
            s = state_load()
            s["is_ready"] = bool(d.get("ready"))
            state_save(s)
            return self._reply(200, {"is_ready": s["is_ready"]})
        if self.path == "/job":
            s = state_load()
            if not s.get("is_ready"):
                return self._reply(503,
                                   {"error": "worker not ready"})
            try:
                text = backend_chat(d.get("prompt") or "")
            except Exception as ex:
                return self._reply(502, {"error": str(ex)[:200]})
            s["jobs_done"] = s.get("jobs_done", 0) + 1
            s["sessions"] = s.get("sessions", 0) + 1
            state_save(s)
            return self._reply(200, {
                "job": d.get("id", "sim-job"),
                "output": text,
                "proof": {"kind": "sim-toploc",
                          "verified": True}})
        self._reply(404, {"error": "not found"})


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
