#!/bin/bash
# build.sh

# Install dependencies (Render will already run pip install from requirements.txt,
# but you can add extra commands here)

# Pre-download the rembg model into a persistent directory
export U2NET_HOME="$PWD/.u2net"
python -c "from rembg import new_session; new_session('u2netp')"

echo "Model pre-download complete"