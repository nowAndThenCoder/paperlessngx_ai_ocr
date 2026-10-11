#!/bin/bash
# Setup routine for the OCR Engine development environment

echo -e "\e[36mStarting environment setup...\e[0m"

# 1. Create Virtual Environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo -e "\e[33mCreating virtual environment (.venv)...\e[0m"
    python3 -m venv .venv
else
    echo -e "\e[90mVirtual environment (.venv) already exists.\e[0m"
fi

# 2. Upgrade pip and install requirements
echo -e "\e[33mInstalling dependencies from requirements.txt...\e[0m"
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt

# 3. Verification
echo -e "\e[33mVerifying installation...\e[0m"
./.venv/bin/python --version
./.venv/bin/pip list

echo -e "\e[32mSetup completed successfully!\e[0m"
