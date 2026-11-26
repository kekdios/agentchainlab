#!/bin/bash
# Collect miner status from the Vast VM and write status.json for the ops page.
# Config in /etc/flop-ops.env: VM_SSH_HOST VM_SSH_PORT VM_SSH_KEY ENDPOINT
#   SPEND_SINCE (ISO time the GPU started billing) + SPEND_RATE_HR (usd/hr) +
#   SPEND_BASE (any earlier spend) auto-accrue the spend card; if unset,
#   static SPEND_SO_FAR is used instead.
set -u
. /etc/flop-ops.env 2>/dev/null || true
SITE=/var/www/agentchainlab
OUT="$SITE/status.json.tmp"
now=$(date -u +'%Y-%m-%d %H:%M UTC')
SSH="ssh -i ${VM_SSH_KEY:-/root/.ssh/flop_vast} -o BatchMode=yes -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new -p ${VM_SSH_PORT:-22} root@${VM_SSH_HOST:-127.0.0.1}"

miner="provisioning"; miner_state="warn"
gpu="—"; gpu_state=""
model="—"; model_state=""
cal="not started"; cal_state=""
sess="—"; sess_state=""
ep="${ENDPOINT:-pending}"; ep_state=""
note=""

if REMOTE=$($SSH 'bash -s' <<'EOS' 2>/dev/null
gpu=$(nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -1)
dock=$(docker ps --format '{{.Names}}:{{.Status}}' 2>/dev/null | tr '\n' ';')
tok=$(grep -m1 '^SESSION_AUTH_TOKEN=' /opt/flop-miner/miner.env 2>/dev/null | cut -d= -f2)
info=""; for i in 1 2 3; do
  info=$(curl -sf --max-time 8 ${tok:+-H "Authorization: Bearer $tok"} http://127.0.0.1:8645/session/info 2>/dev/null) && break
  info=""; sleep 2
done
fence=$(curl -sf --max-time 6 ${tok:+-H "Authorization: Bearer $tok"} http://127.0.0.1:8645/internal/signer-fence 2>/dev/null)
# Auto-reconcile: a fence only raises on an unclassifiable watch outcome;
# mode:reconcile re-proves the tx's outcome on-chain and refuses what it
# can't prove. Idempotent — once per fence digest (marker on the box).
fsha=$(echo "$fence" | grep -oE '"fenceSha256"[ :]*"[0-9a-f]+"' | grep -oE '[0-9a-f]{64}' | head -1)
if echo "$fence" | grep -q '"fenced"[ :]*true' && [ -n "$fsha" ] && [ ! -f "/root/.fence-reconcile-$fsha" ]; then
  touch "/root/.fence-reconcile-$fsha"
  rec=$(curl -s -m 150 -X POST ${tok:+-H "Authorization: Bearer $tok"} -H "Content-Type: application/json" \
    -d "{\"mode\":\"reconcile\",\"expectedFenceSha256\":\"$fsha\"}" \
    http://127.0.0.1:8645/internal/signer-fence 2>/dev/null)
  echo "RECONCILE<<$rec>>"
  fence=$(curl -sf --max-time 6 ${tok:+-H "Authorization: Bearer $tok"} http://127.0.0.1:8645/internal/signer-fence 2>/dev/null)
fi
disk=$(df -h / | awk 'NR==2{print $4" free"}')
model=$(basename "$(grep -m1 '^MODEL_NAME=' /opt/flop-miner/miner.env 2>/dev/null | cut -d= -f2-)" 2>/dev/null)
wimg=$(grep -m1 '^FLOP_WORKER_IMAGE=' /opt/flop-miner/miner.env 2>/dev/null | cut -d= -f2-)
echo "GPU=$gpu"
echo "DOCKER=$dock"
echo "DISK=$disk"
echo "MODEL=$model"
echo "WORKER_IMG=$wimg"
echo "SESSION_INFO<<$info>>"
echo "FENCE<<$fence>>"
EOS
); then
  gpu=$(echo "$REMOTE" | sed -n 's/^GPU=//p'); [ -n "$gpu" ] && gpu_state="ok" || gpu_state="bad"
  miner=$(echo "$REMOTE" | sed -n 's/^DOCKER=//p')
  if [ -n "$miner" ]; then miner_state="ok"; else miner="docker down"; miner_state="bad"; fi
  info=$(echo "$REMOTE" | sed -n 's/^SESSION_INFO<<//;s/>>$//p')
  if echo "$info" | grep -q '"ready"[ :]*true'; then
    cap=$(echo "$info" | grep -oE '"capGflopsPerSec"[ :]*"?[0-9]+' | grep -oE '[0-9]+$' | head -1)
    cal="active (cap ${cap:-?} GFLOP/s)"; cal_state="ok"
  elif echo "$info" | grep -q minerAddress; then
    # Real session/info payload but calibration not ready — transient
    # supervisor states (RPC blips) land here.
    if echo "$info" | grep -q '"calibration"'; then cal="in progress"; cal_state="warn";
    else cal="not calibrated"; cal_state=""; fi
  else cal="__KEEP__"; fi
  # Endpoint fetch failed → keep last known calibration instead of flapping.
  if [ "$cal" = "__KEEP__" ]; then
    cal=$(cut -d'|' -f1 /var/lib/flop-ops/last-cal 2>/dev/null)
    cal_state=$(cut -d'|' -f2 /var/lib/flop-ops/last-cal 2>/dev/null)
    [ -z "$cal" ] && { cal="unreachable"; cal_state="warn"; }
  else
    mkdir -p /var/lib/flop-ops; echo "$cal|$cal_state" > /var/lib/flop-ops/last-cal
  fi
  # Signer fence: worker halted all submissions after an unclassifiable
  # watch outcome — it dominates whatever calibration reports. The remote
  # side auto-attempts mode:reconcile once per digest; report the outcome.
  signer_fenced=$(echo "$REMOTE" | sed -n 's/^FENCE<<//;s/>>$//p' \
    | grep -oE '"fenced"[ :]*(true|false)' | grep -oE 'true|false' | head -1)
  recon=$(echo "$REMOTE" | sed -n 's/^RECONCILE<<//;s/>>$//p' \
    | grep -oE '"outcome"[ :]*"[a-z]+"' | grep -oE '[a-z]+"$' | tr -d '"')
  if [ "$signer_fenced" = "true" ]; then
    cal="signer fenced"; cal_state="warn"
    echo "$cal|$cal_state" > /var/lib/flop-ops/last-cal
    note="signer fenced — reconcile ${recon:+attempted ($recon), still blocked}${recon:-pending}${note:+; }$note"
  elif [ -n "$recon" ]; then
    note="signer fence auto-reconciled ($recon)${note:+; }$note"
  fi
  sess=$(echo "$info" | grep -oE '"sessions"[ :]*[0-9]+' | grep -oE '[0-9]+' | head -1); sess=${sess:-0}
  note=$(echo "$REMOTE" | sed -n 's/^DISK=//p')
  model=$(echo "$REMOTE" | sed -n 's/^MODEL=//p'); [ -n "$model" ] && model_state="ok" || model="—"
else
  miner="unreachable"; miner_state="bad"; ep_state="bad"; note="ssh to VM failed"
fi

# gpu.ai instance truth — distinguishes a dead ssh link from a destroyed
# box (prepaid balance exhaustion terminates, it does not stop) and
# anchors the spend counter to terminated_at.
gpuai_status=""; gpuai_reason=""; gpuai_term_at=""
if [ -n "${GPUAI_API_KEY:-}" ]; then
  gpuai=$(curl -fsm12 -H "Authorization: Bearer $GPUAI_API_KEY" \
    "https://api.gpu.ai/v1/instances/${GPUAI_INSTANCE:-gpu-3469b363}" 2>/dev/null || true)
  if [ -n "$gpuai" ]; then
    gpuai_status=$(echo "$gpuai" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("status",""))' 2>/dev/null || true)
    gpuai_reason=$(echo "$gpuai" | python3 -c 'import json,sys;print((json.load(sys.stdin).get("status_reason") or "")[:140])' 2>/dev/null || true)
    gpuai_term_at=$(echo "$gpuai" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("terminated_at") or "")' 2>/dev/null || true)
  fi
fi
if [ "$miner" = "unreachable" ] && [ "$gpuai_status" = "terminated" ]; then
  miner="terminated"; note="GPU instance terminated: ${gpuai_reason:-unknown}"
fi

# Prepaid balance runway — the 11-18 termination caught us with zero
# warning. Threshold = ~2 days of burn; feeds the sig so crossing it
# emails once (debounced), not per-collect.
gpuai_bal=""; bal_bucket="?"
if [ -n "${GPUAI_API_KEY:-}" ]; then
  bal_json=$(curl -fsm12 -H "Authorization: Bearer $GPUAI_API_KEY" \
    "https://api.gpu.ai/v1/billing/balance" 2>/dev/null || true)
  gpuai_bal=$(echo "$bal_json" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("balance_dollars",""))' 2>/dev/null || true)
  if [ -n "$gpuai_bal" ]; then
    low_at=$(awk -v r="${SPEND_RATE_HR:-0.13}" 'BEGIN{printf "%.2f", r*48}')
    bal_bucket=$(awk -v b="$gpuai_bal" -v t="$low_at" 'BEGIN{print (b+0 < t+0) ? "LOW" : "ok"}')
    if [ "$bal_bucket" = "LOW" ]; then
      hrs=$(awk -v b="$gpuai_bal" -v r="${SPEND_RATE_HR:-0.13}" 'BEGIN{printf "%.0f", b/r}')
      note="${note:+$note; }gpu.ai balance \$$gpuai_bal (~${hrs}h runway) — top up"
    fi
  fi
fi

# Worker image drift: compare pinned digest on the box against releases.json.
# Stale worker images get fenced by runtime upgrades — alert via the sig path.
# Also track cli.latest: a new CLI build may support the current runtime spec
# (unblocks self-custodial spend + declare-gpu) — sig change emails on bump.
drift=$(cat /var/lib/flop-ops/last-drift 2>/dev/null || echo "?")
cliver=$(cat /var/lib/flop-ops/last-cliver 2>/dev/null || echo "?")
wimg=$(echo "${REMOTE:-}" | sed -n 's/^WORKER_IMG=//p')
rel_json=$(curl -fsm10 https://flop.network/releases.json 2>/dev/null || true)
rel=$(echo "$rel_json" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("miner-worker",{}).get("image","")+"\t"+d.get("cli",{}).get("latest",""))' 2>/dev/null || true)
# Testnet tripwire: releases.json is where pack/image/node artifacts will
# land on launch day. Track the artifact key-set (sig diff emails on any
# addition) and flag an explicit "testnet" mention in the payload.
if [ -z "$rel_json" ]; then
  # Fetch failed — keep last-known artifact set; "?" would flap the sig.
  relkeys=$(cat /var/lib/flop-ops/last-relkeys 2>/dev/null || echo "?")
else
  relkeys=$(echo "$rel_json" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(",".join(sorted(k for k in d if k!="models")))' 2>/dev/null || echo "?")
  [ "$relkeys" != "?" ] && echo "$relkeys" > /var/lib/flop-ops/last-relkeys
fi
case "$rel_json" in *[Tt]estnet*) note="TESTNET DETECTED in releases.json; $note";; esac
rel_img=$(echo "$rel" | cut -f1); cli_new=$(echo "$rel" | cut -f2)
if [ -n "$rel_img" ] && [ -n "$wimg" ]; then
  if [ "$wimg" = "$rel_img" ]; then drift="current"; else drift="STALE"; fi
  mkdir -p /var/lib/flop-ops; echo "$drift" > /var/lib/flop-ops/last-drift
fi
if [ -n "$cli_new" ] && [ "$cli_new" != "$cliver" ]; then
  cliver="$cli_new"
  mkdir -p /var/lib/flop-ops; echo "$cliver" > /var/lib/flop-ops/last-cliver
fi
[ "$drift" = "STALE" ] && note="${note:+$note; }worker image stale — upgrade to releases.json pin"

# Spend accrues continuously: base + rate * elapsed since SPEND_SINCE.
if [ -n "${SPEND_SINCE:-}" ] && [ -n "${SPEND_RATE_HR:-}" ]; then
  spend=$(awk -v iso="$SPEND_SINCE" -v r="$SPEND_RATE_HR" -v b="${SPEND_BASE:-0}" -v end="$gpuai_term_at" 'BEGIN{
    c="date -d \"" iso "\" +%s"; c|getline t0; close(c);
    t1=systime();
    if (end != "") { c2="date -d \"" end "\" +%s"; c2|getline te; close(c2);
      if (te > 0 && te < t1) t1 = te }
    printf "$%.2f", b + r*(t1-t0)/3600 }')
else
  spend="${SPEND_SO_FAR:-unknown}"
fi

# Exchange stack liveness — a dead coord/api/wash/evm unit hangs swaps
# silently. Feeds the sig so a transition emails once.
svc_bad=""
for u in evm-devnet exchange-coord exchange-api exchange-wash; do
  systemctl is-active --quiet "$u" || svc_bad="${svc_bad:+$svc_bad,}$u"
done
if [ -n "$svc_bad" ]; then
  svc_bucket="DOWN:"; note="${note:+$note; }exchange services down: $svc_bad"
else
  svc_bucket="up"
fi

cat > "$OUT" <<JSON
{"updated":"$now","miner":"$miner","miner_state":"$miner_state",
"gpu":"$gpu","gpu_state":"$gpu_state",
"model":"$model","model_state":"$model_state",
"calibration":"$cal","calibration_state":"$cal_state",
"sessions":"$sess","sessions_state":"$sess_state",
"spend":"$spend","spend_state":"",
"endpoint":"$ep","endpoint_state":"$ep_state","drift":"$drift","cli":"$cliver","signer_fenced":"${signer_fenced:-}","gpuai_balance":"$gpuai_bal","exchange_svc":"${svc_bad:-up}","note":"$note"}
JSON
mv "$OUT" "$SITE/status.json"

# Email alert when the state signature changes (miner|gpu|calibration|sessions).
# Signature stored in /var/lib/flop-ops/last-sig; first run seeds it silently.
STATE_DIR=/var/lib/flop-ops
case "$sess" in *[1-9]*) sess_bucket=live;; *) sess_bucket=idle;; esac
sig="$miner_state|$gpu_state|$cal|$sess_bucket|$drift|cli:$cliver|rel:$relkeys|bal:$bal_bucket|fen:${signer_fenced:-?}|svc:$svc_bucket"
mkdir -p "$STATE_DIR"
prev=$(cat "$STATE_DIR/last-sig" 2>/dev/null || true)
# Debounce: a new signature must persist 2 consecutive collects (~6 min
# at */3) before it emails — kills single-read flaps like
# active<->in-progress from worker RPC blips.
pend=$(cat "$STATE_DIR/pending-sig" 2>/dev/null || true)
if [ "$sig" = "$prev" ]; then
  rm -f "$STATE_DIR/pending-sig"
elif [ "$sig" = "$pend" ]; then
  echo "$sig" > "$STATE_DIR/last-sig"; rm -f "$STATE_DIR/pending-sig"
  [ -n "$prev" ] && /usr/local/lib/flop-ops/notify.py "$prev" "$sig" "miner,gpu,calibration,sessions,drift,cli,artifacts,balance,fence,exchange" >>/var/log/flop-ops-notify.log 2>&1 &
else
  echo "$sig" > "$STATE_DIR/pending-sig"
fi
