# preload_model.py
import os
from rembg import new_session

# Download model into the local .u2net folder (will be part of the build)
os.makedirs(".u2net", exist_ok=True)
os.environ["U2NET_HOME"] = os.path.abspath(".u2net")
new_session("u2netp")
print("Model pre-downloaded to", os.environ["U2NET_HOME"])
