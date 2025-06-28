#!/usr/bin/env bash
set -e  # Exit on first error

### 0. Install base build tools & utilities ###
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  curl \
  git \
  libbz2-dev \
  libffi-dev \
  liblzma-dev \
  libncurses5-dev \
  libreadline-dev \
  libsqlite3-dev \
  libssl-dev \
  lsb-release \
  make \
  software-properties-common \
  tk-dev \
  wget \
  zlib1g-dev \
  gnupg

### 1. Install Python 3.12.4 from source ###
PYTHON_VERSION=3.12.4
if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Downloading Python $PYTHON_VERSION..."
  cd /tmp
  wget "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"
  tar xzf "Python-${PYTHON_VERSION}.tgz"
  cd "Python-${PYTHON_VERSION}"
  ./configure --enable-optimizations --with-ensurepip=install
  make -j"$(nproc)"
  sudo make altinstall
  cd /tmp
  rm -rf "Python-${PYTHON_VERSION}"*
fi

### 2. Install Poetry and set its Python ###
if ! command -v poetry >/dev/null 2>&1; then
  echo "Installing Poetry..."
  curl -sSL https://install.python-poetry.org | python3.12 -
  export PATH="$HOME/.local/bin:$PATH"
fi

# Tell Poetry to use Python 3.12 by default in this project
poetry env use python3.12

### 3. Install PostgreSQL 15 + pgvector ###
chmod +x codex_environment_setup_scripts/install_pgvector_cursor_background_agent_env.sh
./codex_environment_setup_scripts/install_pgvector_cursor_background_agent_env.sh

### 4. Backend setup ###
cd drsearch_backend
cp .example.env .env
poetry lock
poetry install --all-extras

### 5. Frontend setup ###
cd ../drsearch_frontend
cp .example.env .env
yarn install
yarn playwright install

echo "✅ Setup complete! Python 3.12.4, PostgreSQL+pgvector, backend & frontend dependencies are installed."
