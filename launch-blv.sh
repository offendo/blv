#!/bin/bash

# Defaults
LEAN_VERSION="v4.18.0"
PROJECT_PATH=""
SKIP_INSTALL="false"
N_WORKERS=10

USAGE="Script to install/launch blv.\n Usage:\n  bash launch-blv.sh --redis-db <n> --lean-version v4.XX.X [--n-workers <n>] [--project-path /path/to/lean/project] [--skip-install]"

while [[ $# -gt 0 ]]; do
  case $1 in
    --redis-db)
      REDIS_DB="$2"
      shift # past argument
      shift # past value
      ;;
    --skip-install)
      SKIP_INSTALL="true"
      shift # past argument
      ;;
    --project-path)
      PROJECT_PATH="$2"
      shift # past argument
      shift # past value
      ;;
    --lean-version)
      LEAN_VERSION="$2"
      shift # past argument
      shift # past value
      ;;
    -n|--n-workers)
      N_WORKERS="$2"
      shift # past argument
      shift # past value
      ;;
    -h|--help)
      echo -e "$USAGE"
      exit 0
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
    *)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

if [ -z "$REDIS_DB" ]; then
  echo "Error: please supply redis DB with --redis-db <n>"
  exit 1
fi

if [ "$SKIP_INSTALL" != "true" ]; then
  git clone https://github.com/offendo/blv.git
  cd blv
  
  # Create empty venv
  python -m venv .venv
  source .venv/bin/activate
  
  # Install python lib
  pip install -U -e .
fi

# Set up .env file
cat << EOF > .env
# self-explanatory
LEAN_VERSION=${LEAN_VERSION}

# Path to Lean project (optional if not using a '-light' image)
PROJECT_PATH=${PROJECT_PATH}

# Number of REPL instances to have at once. You should set this to the number of CPUs your machine has for the highest speed. 
N_WORKERS=${N_WORKERS}

# Which Redis DB to launch workers on
REDIS_DB=${REDIS_DB}
EOF

# Launch workers
docker compose -f compose.yaml up -d
