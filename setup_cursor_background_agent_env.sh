#!/usr/bin/env bash
set -e  # Exit on any error

# 0. Ensure apt utilities are available
sudo apt-get update
sudo apt-get install -y curl gnupg lsb-release software-properties-common

# 1. Install Poetry
if ! command -v poetry &> /dev/null; then
  echo "Installing Poetry..."
  curl -sSL https://install.python-poetry.org | python3 -
  export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Install PostgreSQL + pgvector
chmod +x codex_environment_setup_scripts/install_pgvector_cursor_background_agent_env.sh
./codex_environment_setup_scripts/install_pgvector_cursor_background_agent_env.sh

# 3. Backend setup
cd drsearch_backend
cp .example.env .env
poetry lock
poetry install --all-extras

# 4. Frontend setup
cd ../drsearch_frontend
cp .example.env .env
yarn install
yarn playwright install

echo "✅ All setup steps complete!"
