#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
DOTNET="${DOTNET:-dotnet}"
"$DOTNET" restore dotnet/AetherGrid.Server --locked-mode
npm --prefix frontend ci
npm --prefix frontend run build
"$DOTNET" publish dotnet/AetherGrid.Server -c Release -o .runtime --no-restore
mkdir -p .runtime/wwwroot
cp -r frontend/dist/* .runtime/wwwroot/
printf '\nBuilt .runtime. Configure private users/keys/DB and run from .runtime; see README.md.\n'
