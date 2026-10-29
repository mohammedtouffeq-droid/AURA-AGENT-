import os
import sys
import urllib.request
import zipfile
import subprocess
from pathlib import Path

def setup_godot():
    target_dir = Path(r"c:\Users\hp\AURA-Agent\engines\godot")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    godot_exe = target_dir / "godot.exe"
    if godot_exe.exists():
        print(f"[OK] Godot binary already exists at: {godot_exe}")
        return verify_godot(godot_exe)

    url = "https://github.com/godotengine/godot/releases/download/4.3-stable/Godot_v4.3-stable_win64.exe.zip"
    zip_path = target_dir / "godot_temp.zip"
    
    print(f"[*] Downloading Godot 4.3 Stable (~54 MB) from {url}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    with urllib.request.urlopen(req, timeout=60) as response, open(zip_path, 'wb') as out_file:
        total_size = int(response.headers.get('Content-Length', 0))
        downloaded = 0
        chunk_size = 1024 * 512 # 512 KB
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            downloaded += len(chunk)
            out_file.write(chunk)
            if total_size > 0:
                percent = (downloaded / total_size) * 100
                sys.stdout.write(f"\rDownloading: {downloaded / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB ({percent:.1f}%)")
                sys.stdout.flush()
    print("\n[OK] Download complete.")
    
    print(f"[*] Extracting {zip_path.name}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.namelist():
            if member.endswith(".exe"):
                print(f"Extracting executable: {member} -> godot.exe")
                with zip_ref.open(member) as source, open(godot_exe, "wb") as target:
                    target.write(source.read())
                break
                
    if zip_path.exists():
        zip_path.unlink()
        print("[*] Cleaned up temporary zip.")
        
    return verify_godot(godot_exe)

def verify_godot(exe_path: Path):
    if not exe_path.exists():
        print(f"[FAIL] Godot executable not found at {exe_path}")
        return False
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Binary found: {exe_path} ({size_mb:.2f} MB)")
    
    try:
        res = subprocess.run([str(exe_path), "--version", "--headless"], capture_output=True, text=True, timeout=10)
        version = res.stdout.strip()
        print(f"[SUCCESS] Godot Engine Verified! Version: {version}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to run godot binary: {e}")
        return False

if __name__ == "__main__":
    success = setup_godot()
    sys.exit(0 if success else 1)
