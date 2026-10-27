#!/usr/bin/env bash
set -euo pipefail
# Requires the owner's authenticated GitHub CLI. Does not change visibility or license.
repo="joyboyzz/Aether-Grid"
gh repo edit "$repo" \
  --description 'Independent cold-chain software project: signed telemetry, buyer eligibility, operator-reviewed simulated settlement, thermal routing and recovery tests.' \
  --add-topic cold-chain --add-topic aspnet-core --add-topic react --add-topic typescript \
  --add-topic python --add-topic sqlite --add-topic simulation --add-topic routing \
  --add-topic software-engineering --add-topic portfolio-project --add-topic fault-tolerance
printf '\nSocial preview image: assets/github/social-preview.png\nUpload it under repository Settings > General > Social preview.\n'
