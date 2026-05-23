#!/bin/bash

VENV_PATH="/workspaces/audiobookshelf-ai/.venv"

python -m venv $VENV_PATH

source $VENV_PATH/bin/activate

pip install --no-cache-dir -r requirements.txt

# Auto activate venv in future bash sessions
if ! grep -q "$VENV_PATH/bin/activate" ~/.bashrc; then
    {
        echo ""
        echo "# Auto activate venv"
        echo "if [ -f $VENV_PATH/bin/activate ]; then"
        echo "    source $VENV_PATH/bin/activate"
        echo "fi"
    } >> ~/.bashrc
fi