#!/bin/bash
set -xe

python3.13 --version
python3.13 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install --upgrade pip
python -m pip --version
python -m pip install -r requirements.txt
python app.py
# deactivate
# rm -rf .venv
echo "Job Completed Successfully"
