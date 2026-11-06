#!/usr/bin/env bash
# Self-healing / persistence checks against the REAL docker compose stack.
# Usage: API_PORT=8001 bash backend/tests/e2e/recovery.sh [--yes]
# Scenario (a) runs `docker compose down -v` (DESTROYS the dev DB volume and its
# conversations); it needs --yes or CONFIRM=1, otherwise it is SKIPPED.
set -euo pipefail

cd "$(dirname "$0")/../../.."          # repo root (compose file lives here)
PORT="${API_PORT:-8000}"; export API_PORT="$PORT"
BASE="http://localhost:$PORT"
JSON=/app/data/processed/actuators.json
EXPECTED=68
PASS=0; FAIL=0; SKIP=0
CONFIRM="${CONFIRM:-0}"; [ "${1:-}" = "--yes" ] && CONFIRM=1

psql_db() { docker compose exec -T db psql -U series76 -d series76 -tA "$@"; }
in_api()  { docker compose exec -T api "$@"; }

wait_healthy() {
  for _ in $(seq 60); do
    curl -fs "$BASE/health" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}
actuators_count() {
  curl -fs "$BASE/health" | python3 -c 'import sys,json; print(json.load(sys.stdin)["actuators"])'
}
json_rows_in_container() {
  in_api python -c "import json; d=json.load(open('$JSON')); print(len(d['rows']))" 2>/dev/null || echo "invalid"
}
report() {  # report <name> <ok:0|1> <reason>
  if [ "$2" = 0 ]; then echo "PASS  $1"; PASS=$((PASS+1)); else echo "FAIL  $1 -- $3"; FAIL=$((FAIL+1)); fi
}
# NB: scenarios run inside `if`, where `set -e` is off, so failures must `|| return 1`.
# Common check after a restart: healthy, 68 actuators, valid 68-row JSON in the container.
check_healed() {
  wait_healthy || { echo "API not healthy after 120 s"; return 1; }
  local n rows; n=$(actuators_count); rows=$(json_rows_in_container)
  [ "$n" = "$EXPECTED" ] || { echo "/health actuators=$n (want $EXPECTED)"; return 1; }
  [ "$rows" = "$EXPECTED" ] || { echo "container JSON rows=$rows (want $EXPECTED)"; return 1; }
}
run() {  # run <name> <function>; the function prints its failure reason
  local reason; if reason=$("$2" 2>&1); then report "$1" 0 ""; else report "$1" 1 "$(echo "$reason" | tail -1)"; fi
}

scn_a() {
  docker compose down -v >/dev/null 2>&1
  make up >/dev/null 2>&1 || { echo "make up failed"; return 1; }
  wait_healthy || { echo "not healthy"; return 1; }
  local n; n=$(actuators_count)
  [ "$n" = "$EXPECTED" ] || { echo "actuators=$n after fresh volume"; return 1; }
}
scn_b() {
  in_api sh -c "rm $JSON"
  docker compose restart api >/dev/null 2>&1
  check_healed || return 1
}
scn_c() {
  psql_db -c "DELETE FROM actuators WHERE part_number LIKE '764%'" >/dev/null
  local before; before=$(psql_db -c "SELECT count(*) FROM actuators")
  [ "$before" -lt "$EXPECTED" ] || { echo "delete removed nothing"; return 1; }
  docker compose restart api >/dev/null 2>&1
  check_healed || return 1
  local after; after=$(psql_db -c "SELECT count(*) FROM actuators")
  [ "$after" = "$EXPECTED" ] || { echo "DB rows=$after after restart"; return 1; }
}
scn_d() {
  in_api sh -c "echo '{not json' > $JSON"
  docker compose restart api >/dev/null 2>&1
  check_healed || return 1
  in_api sh -c "ls ${JSON}.corrupt-*" >/dev/null 2>&1 || { echo "no actuators.json.corrupt-* file"; return 1; }
}
scn_e() {
  # Sessions belong to a user since login (D-43): own it by the seeded test user ana.
  local uid; uid=$(psql_db -c "SELECT id FROM users WHERE email = 'ana@konecto.test'" | head -1)
  [ -n "$uid" ] || { echo "seeded user ana missing"; return 1; }
  local sid; sid=$(psql_db -c "INSERT INTO sessions (title, user_id) VALUES ('recovery-check', '$uid') RETURNING id" | head -1)
  psql_db -c "INSERT INTO messages (session_id, role, content) VALUES ('$sid','user','recovery-message')" >/dev/null
  docker compose restart api >/dev/null 2>&1
  wait_healthy || { echo "not healthy"; return 1; }
  local token; token=$(curl -fs -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' \
    -d '{"email":"ana@konecto.test","password":"ana-series76"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
  [ -n "$token" ] || { echo "login failed"; return 1; }
  local auth="Authorization: Bearer $token" rc=0
  curl -fs -H "$auth" "$BASE/api/sessions?limit=200" | grep -q "$sid" || { echo "session $sid not listed"; rc=1; }
  [ $rc = 0 ] && { curl -fs -H "$auth" "$BASE/api/sessions/$sid/messages" | grep -q recovery-message || { echo "message missing"; rc=1; }; }
  psql_db -c "DELETE FROM sessions WHERE id='$sid'" >/dev/null   # cleanup (cascades)
  return $rc
}

if [ "$CONFIRM" = 1 ]; then
  run "(a) down -v + make up -> DB rebuilt from JSON" scn_a
else
  echo "WARNING: scenario (a) runs 'docker compose down -v' and DELETES the dev DB volume."
  echo "         Re-run with --yes (or CONFIRM=1) to include it."
  echo "SKIPPED  (a) down -v + make up"; SKIP=$((SKIP+1))
fi
wait_healthy || { echo "stack is not up; run 'make up' first"; exit 1; }
run "(b) JSON deleted -> rebuilt from DB"            scn_b
run "(c) DB rows deleted -> reloaded from JSON"      scn_c
run "(d) JSON corrupted -> moved aside and rebuilt"  scn_d
run "(e) conversation survives API restart"          scn_e

# Leave the stack in its original state: fresh container = image's original JSON.
docker compose up -d --force-recreate api >/dev/null 2>&1
wait_healthy && echo "Stack left UP and healthy." || { echo "FAIL  stack not healthy at end"; FAIL=$((FAIL+1)); }

echo "Summary: $PASS passed, $FAIL failed, $SKIP skipped"
[ "$FAIL" = 0 ]
