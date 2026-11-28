#!/usr/bin/env python3
"""sim-backend — vLLM-shaped shim whose "model" is nano-gpt.

Mimics the real flop-miner backend container's API surface so the ops
pipeline (ask_self, health checks, session calls) can be exercised
without a GPU. Replies come from nano-gpt; the advertised model name
is faked to the miner's allowlisted one for realism.

Endpoints (real backend surface):
  GET  /v1/models             -> {"data":[{"id": MODEL_NAME}]}
  POST /v1/chat/completions   -> forwarded to nano-gpt, OpenAI shape
  POST /v1/completions        -> wrapped into a chat call
  GET  /health                -> {"status":"ok"}
Auth: Bearer $INFERENCE_API_KEY when set (mirrors real worker->backend).
"""
import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8000"))
MODEL_NAME = os.environ.get("MODEL_NAME", "qwen/qwen3-1.7b")
NANO_URL = "https://nano-gpt.com/api/v1/chat/completions"
NANO_MODEL = os.environ.get("NANO_MODEL", "minimax/minimax-m3")
API_KEY = os.environ.get("INFERENCE_API_KEY", "")


def nano_reply(messages, max_tokens=512):
    req = urllib.request.Request(
        NANO_URL,
        data=json.dumps({
            "model": NANO_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
        }).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["NANOGPT_API_KEY"],
            "Content-Type": "application/json",
        })
    d = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return d["choices"][0]["message"].get("content") or ""


class H(BaseHTTPRequestHandler):
    def _reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self):
        if not API_KEY:
            return True
        return self.headers.get("Authorization") == "Bearer " + API_KEY

    def log_message(self, *a):
        pass

    def do_GET(self):
        if not self._auth_ok():
            return self._reply(401, {"error": "unauthorized"})
        if self.path == "/v1/models":
            return self._reply(200, {"object": "list", "data": [
                {"id": MODEL_NAME, "object": "model",
                 "created": int(time.time()), "owned_by": "flop-sim"}]})
        if self.path == "/health":
            return self._reply(200, {"status": "ok"})
        self._reply(404, {"error": "not found"})

    def do_POST(self):
        if not self._auth_ok():
            return self._reply(401, {"error": "unauthorized"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            d = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._reply(400, {"error": "bad json"})
        if self.path == "/v1/completions":
            msgs = [{"role": "user",
                     "content": d.get("prompt") or ""}]
            return self._chat(d, msgs)
        if self.path == "/v1/chat/completions":
            return self._chat(d, d.get("messages") or [])
        self._reply(404, {"error": "not found"})

    def _chat(self, d, messages):
        try:
            text = nano_reply(messages, int(d.get("max_tokens", 512)))
        except Exception as ex:
            return self._reply(502, {"error": "nano-gpt: %s"
                                     % str(ex)[:200]})
        return self._reply(200, {
            "id": "sim-%d" % int(time.time() * 1000),
            "object": "chat.completion",
            "model": MODEL_NAME,
            "choices": [{"index": 0, "message": {
                "role": "assistant", "content": text},
                "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                      "total_tokens": 0}})


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
