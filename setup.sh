#!/bin/bash
set -e  # Exit on first error

chmod +x codex_environment_setup_scripts/install_pgvector.sh
./codex_environment_setup_scripts/install_pgvector.sh

cd drsearch_backend
cp .example.env .env
poetry lock
poetry install --all-extras

cd ../drsearch_frontend
cp .example.env .env
yarn install
yarn playwright install
