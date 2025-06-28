#!/usr/bin/env bash
set -e  # Exit on first error

# 0. Prep apt for adding PPAs and key management
sudo apt-get update
sudo apt-get install -y software-properties-common curl gnupg lsb-release

# 1. Install Python 3.12.4 (via deadsnakes) and set it as default for Poetry
if ! command -v python3.12 >/dev/null; then
  echo "Adding deadsnakes PPA for Python 3.12..."
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update
  echo "Installing Python 3.12..."
  sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
fi

# 2. Install Poetry (if needed) and configure it to use Python 3.12
if ! command -v poetry >/dev/null; then
  echo "Installing Poetry..."
  curl -sSL https://install.python-poetry.org | python3.12 -
  export PATH="$HOME/.local/bin:$PATH"
fi

# Ensure Poetry uses Python 3.12 for this project
poetry env use python3.12

# 3. Install PostgreSQL + pgvector
chmod +x codex_environment_setup_scripts/install_pgvector_cursor_background_agent_env.sh
./codex_environment_setup_scripts/install_pgvector_cursor_background_agent_env.sh

# 4. Backend setup with Poetry (now using Python 3.12)
cd drsearch_backend
cp .example.env .env
poetry lock
poetry install --all-extras

# 5. Frontend setup
cd ../drsearch_frontend
cp .example.env .env
yarn install
yarn playwright install

echo "✅ Setup complete with Python 3.12.4, PostgreSQL+pgvector, backend & frontend dependencies installed."
