#!/bin/bash
# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Pre-download the rembg model (saves to ./.u2net)
export U2NET_HOME="$PWD/.u2net"
python -c "from rembg import new_session; new_session('u2netp')"

echo "✅ Model pre-download complete"