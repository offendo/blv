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
# Docker/launch args
# ==================

# self-explanatory
BLV_VERSION=0.2.2
LEAN_VERSION=${LEAN_VERSION}

# Path to Lean project on your machine (optional). Useful if you're processing
# theorems with additional dependencies other than just mathlib.
# **IMPORTANT:** If you set a PROJECT_PATH, make sure you also uncomment
#                BLV_PROJECT_PATH, and mount PROJECT_PATH:BLV_PROJECT_PATH in
#                the compose.yaml file 

PROJECT_PATH=${PROJECT_PATH}
# BLV_PROJECT_PATH=/project

# Number of REPL instances to have at once. More is faster, but
# will also consume more memory if you're loading big libraries like Mathlib.
N_WORKERS=${N_WORKERS}
            

# Which Redis DB to launch workers on. 0 is default, but if you use Redis for
# something else and you don't want the data from that DB to be flushed, you
# can set this to something else. You should also then set redis_db=... in
# blv.verify_theorems when you use it.
REDIS_DB=${REDIS_DB}

# self-explanatory
LEAN_VERSION=${LEAN_VERSION}

# You can customize the default imports for the workers, comma separated.
BLV_IMPORTS="import Mathlib,import Aesop"
EOF

# Launch workers
docker compose -f compose.yaml up -d
