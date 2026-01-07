#!/bin/bash
set -xe

python3.13 --version
python3.13 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install --upgrade pip
python -m pip --version

# 1. Install dev dependencies
python -m pip install -r requirements-dev.txt

# 2. Install pre-commit hooks
pre-commit install

# 3. Run pre-commit on all files
pre-commit run --all-files

# 4. Test the application
python app.py

# deactivate
# rm -rf .venv
echo "Job Completed Successfully"
