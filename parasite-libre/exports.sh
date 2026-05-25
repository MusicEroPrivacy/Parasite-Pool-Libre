#!/usr/bin/env bash
set -euo pipefail

# Get JWT_SECRET from auth container if not set
if [[ -z "${JWT_SECRET:-}" ]] && command -v docker >/dev/null 2>&1; then
  jwt_secret_from_auth=""
  
  for auth_container in auth umbrel-auth umbrel_auth; do
    jwt_secret_from_auth="$(
      docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "${auth_container}" 2>/dev/null \
        | sed -n 's/^JWT_SECRET=//p' \
        | tail -n 1
    )"
    if [[ -n "${jwt_secret_from_auth:-}" ]]; then
      break
    fi
  done
  
  if [[ -n "${jwt_secret_from_auth:-}" ]]; then
    export JWT_SECRET="${jwt_secret_from_auth}"
  fi
fi

export JWT_SECRET="${JWT_SECRET:-DEADBEEF}"
export LIBRE_RPC_PASSWORD="m4dTOS5_11fL4YY84kFDgUyBW-p1WzSXjD8wXd5a_Iw="
