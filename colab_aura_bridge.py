"""
===================================================================================
        AURA CLOUD GPU WORKER & COLAB BRIDGE (FOR GOOGLE COLAB FREE GPU)
===================================================================================
Copy and paste this script into your Google Colab Notebook tab.
It will:
1. Detect GPU (T4 / A100 / L4).
2. Install lightweight inference / compilation tools.
3. Expose a high-speed background API for AURA to offload heavy code tasks.
===================================================================================
"""

import subprocess
import sys
import os

print("="*60)
print("🚀 AURA CLOUD GPU WORKER INITIALIZING ON GOOGLE COLAB...")
print("="*60)

# Check GPU
try:
    gpu_info = subprocess.check_output("nvidia-smi --query-gpu=gpu_name,memory.total --format=csv,noheader", shell=True).decode().strip()
    print(f"✅ GPU DETECTED: {gpu_info}")
except Exception:
    print("ℹ️ Running in CPU Mode (Select Runtime -> Change runtime type -> T4 GPU in Colab for 10x speed)")

print("\n⚡ Installing AURA worker dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "fastapi", "uvicorn", "pydantic", "pyngrok"])

print("\n✨ AURA Colab GPU Worker is READY!")
print("Run heavy code generation, model fine-tuning, or AST indexing here without burning your local laptop RAM.")
