#!/usr/bin/env bash
set -euo pipefail

echo "Installing Containerlab..."
bash -c "$(curl -sL https://get.containerlab.dev)"

echo "Installing Python dependencies..."
pip install --user -r requirements.txt

echo "Pulling the FRR image..."
docker pull frrouting/frr:v8.4.1

echo "Done. Run: make deploy"
