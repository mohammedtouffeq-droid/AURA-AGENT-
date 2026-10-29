import urllib.request
import json

# 1. Test GET /
req = urllib.request.urlopen('http://localhost:5050/')
html = req.read().decode('utf-8')
assert 'toggleTerminalDrawer()' in html, "toggleTerminalDrawer() missing from HTML"
assert 'toggleStudioDrawer()' in html, "toggleStudioDrawer() missing from HTML"
assert 'toggleCyberLabModal()' in html, "toggleCyberLabModal() missing from HTML"
assert 'function toggleTerminalDrawer' in html, "function toggleTerminalDrawer missing from script"
assert 'function toggleStudioDrawer' in html, "function toggleStudioDrawer missing from script"
assert 'function toggleCyberLabModal' in html, "function toggleCyberLabModal missing from script"
print("TEST 1: GET / - Status 200 OK, JS functions fully present")

# 2. Test GET /api/workspace/tree
req = urllib.request.urlopen('http://localhost:5050/api/workspace/tree')
data = json.loads(req.read().decode('utf-8'))
assert data.get('success') is True
assert len(data.get('files', [])) > 0
print(f"TEST 2: GET /api/workspace/tree - OK, found {data['total_files']} files")

# 3. Test POST /api/terminal/exec
post_data = json.dumps({'command': 'Write-Output "AURA_TERMINAL_ONLINE_PROVEN"'}).encode('utf-8')
req = urllib.request.Request('http://localhost:5050/api/terminal/exec', data=post_data, headers={'Content-Type': 'application/json'})
res = urllib.request.urlopen(req)
data = json.loads(res.read().decode('utf-8'))
assert 'AURA_TERMINAL_ONLINE_PROVEN' in data['stdout'], f"Unexpected stdout: {data}"
print(f"TEST 3: POST /api/terminal/exec - OK, PowerShell stdout: {data['stdout'].strip()}")

# 4. Test GET /api/cyberheist/status
req = urllib.request.urlopen('http://localhost:5050/api/cyberheist/status')
data = json.loads(req.read().decode('utf-8'))
assert data['missions_count'] == 60
print(f"TEST 4: GET /api/cyberheist/status - OK, {data['missions_count']} missions, {data['labs_count']} labs")

print("\n==============================================")
print("ALL 4 LIVE HTTP ENDPOINT TESTS PASSED 100% OK!")
print("==============================================")
