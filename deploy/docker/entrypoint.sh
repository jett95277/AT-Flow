#!/bin/sh
set -eu

mkdir -p /root/.codex /root/.config/opencode

if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
  python -m at_flow.deploy_config write-codex --key "$DEEPSEEK_API_KEY" --out /root/.codex/config.toml
fi

SANDBOX="${AT_CODEX_SANDBOX:-workspace-write}"
python -m at_flow.deploy_config apply-sandbox "$SANDBOX" --config /opt/at-flow/at.config.json
python -m at_flow.deploy_config write-opencode --root /opt/at-flow --out /root/.config/opencode/opencode.jsonc

exec python -m at_flow.web --root /opt/at-flow --host 0.0.0.0 --port 8000
