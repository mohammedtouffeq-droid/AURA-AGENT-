/**
 * ===================================================================================
 *   AURA AUTOMATIC DEVICE-AWARE OFFLINE ENGINE (100% FREE MOBILE OFFLINE AI)
 * ===================================================================================
 * Strict Worldwide Device Policy:
 *  - Detects device automatically on launch (Phone vs Tablet vs Laptop vs Desktop).
 *  - LAPTOP / DESKTOP OFFLINE: Displays clean Obsidian "Internet Required" gate popup
 *    (offline mode is disabled on Laptop/Desktop; auto-dismisses when Wi-Fi returns).
 *  - MOBILE PHONE OFFLINE: ZERO popup, ZERO UI changes — runs identically to Wi-Fi/Data
 *    mode using AURA's 100% free on-device Offline Sovereign Brain (chat, Hinglish/English,
 *    coding & bug analysis, exact math/unit/finance solver, local memories, workspace files,
 *    study/writing templates) + IndexedDB thread persistence + auto-sync on reconnect.
 * ===================================================================================
 */
(function (global) {
    'use strict';

    const MEM_STORAGE_KEY = 'aura_offline_mobile_memories_v1';
    const FS_STORAGE_KEY = 'aura_offline_mobile_files_v1';
    const LAST_USER_KEY = 'aura_offline_last_user_v1';

    function detectDeviceNow() {
        if (typeof global.getClientDeviceProfile === 'function') {
            try {
                const p = global.getClientDeviceProfile();
                if (p && p.device_class) return p;
            } catch (_) {}
        }
        const ua = (navigator && navigator.userAgent) ? navigator.userAgent : '';
        const platform = (navigator && navigator.platform) ? navigator.platform : '';
        const vw = global.innerWidth || (global.screen && global.screen.width) || 0;
        const vh = global.innerHeight || (global.screen && global.screen.height) || 0;
        const maxTouch = Number((navigator && navigator.maxTouchPoints) || 0);
        const isIpad = /iPad/i.test(ua) || (/MacIntel/i.test(platform) && maxTouch >= 2);
        const isMobileUa = /iPhone|iPod|Android.*Mobile|Mobile|Phone/i.test(ua);
        const isTabletUa = isIpad || (/Android/i.test(ua) && !/Mobile/i.test(ua)) || /Tablet/i.test(ua);
        let deviceClass = 'desktop';
        if (isMobileUa || (vw > 0 && vw < 680 && maxTouch >= 1)) deviceClass = 'mobile';
        else if (isTabletUa) deviceClass = 'tablet';
        else if (vw > 0 && vw <= 1680) deviceClass = 'laptop';
        return {
            user_agent: ua.slice(0, 260),
            platform: platform.slice(0, 60),
            device_class: deviceClass,
            viewport_w: vw,
            viewport_h: vh,
            max_touch_points: maxTouch,
            likely_laptop: deviceClass === 'laptop',
        };
    }

    function getFriendlyDeviceLabel(prof) {
        const p = prof || detectDeviceNow();
        const ua = String(p.user_agent || '').toLowerCase();
        const cls = String(p.device_class || 'desktop').toLowerCase();
        if (cls === 'mobile') {
            if (ua.includes('iphone') || ua.includes('ipod')) return 'iPhone (iOS Mobile)';
            if (ua.includes('android')) return 'Android Phone';
            return 'Mobile Phone';
        }
        if (cls === 'tablet') {
            if (ua.includes('ipad') || (ua.includes('mac') && Number(p.max_touch_points || 0) >= 2)) return 'iPad (iPadOS)';
            return 'Tablet';
        }
        if (cls === 'laptop') {
            if (ua.includes('mac')) return 'MacBook / macOS Laptop';
            if (ua.includes('windows')) return 'Windows Laptop';
            if (ua.includes('cros')) return 'Chromebook Laptop';
            return 'Laptop';
        }
        if (ua.includes('mac')) return 'Mac Desktop';
        if (ua.includes('windows')) return 'Windows Desktop';
        if (ua.includes('linux')) return 'Linux Desktop';
        return 'Desktop Workstation';
    }

    function isMobilePhone() {
        return detectDeviceNow().device_class === 'mobile';
    }

    function isLaptopOrDesktop() {
        const cls = detectDeviceNow().device_class;
        return cls === 'laptop' || cls === 'desktop';
    }

    function isOfflineNow() {
        return typeof navigator !== 'undefined' && navigator.onLine === false;
    }

    function enforceDeviceOfflinePolicy() {
        const modal = document.getElementById('auraDesktopOfflineModal');
        const labelEl = document.getElementById('auraOfflineModalDeviceLabel');
        const prof = detectDeviceNow();
        const friendly = getFriendlyDeviceLabel(prof);

        if (labelEl) labelEl.textContent = friendly;

        // UNIVERSAL 0-COST OFFLINE POLICY:
        // Zero blocking popups & zero "Failed to fetch" errors on ANY device (Phone, Tablet, Laptop, Desktop).
        // When offline or network drops, AURA runs seamlessly via its 0-cost on-device Sovereign Brain.
        if (modal) modal.style.display = 'none';
        return {
            blocked: false,
            device: friendly,
            mode: isOfflineNow() ? 'universal_offline_zero_cost' : 'online',
        };
    }

    // ---------------- Local Offline Memory & File Vault Helpers ----------------
    function _loadJson(key, fallback) {
        try {
            const raw = localStorage.getItem(key);
            if (!raw) return fallback;
            const parsed = JSON.parse(raw);
            return parsed !== null && parsed !== undefined ? parsed : fallback;
        } catch (_) {
            return fallback;
        }
    }

    function _saveJson(key, val) {
        try {
            localStorage.setItem(key, JSON.stringify(val));
        } catch (_) {}
    }

    function saveLastMobileUser(userObj) {
        if (!userObj || !userObj.username) return;
        _saveJson(LAST_USER_KEY, {
            id: userObj.id || 'mobile_local',
            username: String(userObj.username).slice(0, 64),
            role: String(userObj.role || 'user'),
            isGuest: Boolean(userObj.isGuest || String(userObj.username).startsWith('guest_')),
            savedAt: Date.now(),
        });
    }

    function getLastMobileUser() {
        const saved = _loadJson(LAST_USER_KEY, null);
        if (saved && saved.username) return saved;
        return {
            id: 'mobile_offline',
            username: 'AURA_Mobile',
            role: 'user',
            isGuest: true,
        };
    }

    // ---------------- Safe Arithmetic & Unit Solver (No eval!) ----------------
    function _safeEvalMath(exprRaw) {
        const clean = String(exprRaw || '')
            .replace(/×/g, '*')
            .replace(/÷/g, '/')
            .replace(/\^/g, '**')
            .replace(/,/g, '')
            .trim();
        if (!clean || clean.length > 120) return null;
        if (!/^[0-9+\-*/().%\s]+$/.test(clean)) return null;
        const tokens = [];
        let i = 0;
        while (i < clean.length) {
            const ch = clean[i];
            if (/\s/.test(ch)) { i++; continue; }
            if (/[0-9.]/.test(ch)) {
                let num = '';
                while (i < clean.length && /[0-9.]/.test(clean[i])) num += clean[i++];
                const v = Number(num);
                if (!Number.isFinite(v)) return null;
                tokens.push({ t: 'num', v });
                continue;
            }
            if (ch === '*' && clean[i + 1] === '*') {
                tokens.push({ t: 'op', v: '**' });
                i += 2;
                continue;
            }
            if ('+-*/()%'.includes(ch)) {
                tokens.push({ t: ch === '(' || ch === ')' ? ch : 'op', v: ch });
                i++;
                continue;
            }
            return null;
        }
        if (!tokens.length) return null;
        let pos = 0;
        function parseExpr() {
            let left = parseTerm();
            while (pos < tokens.length && tokens[pos].t === 'op' && (tokens[pos].v === '+' || tokens[pos].v === '-')) {
                const op = tokens[pos++].v;
                const right = parseTerm();
                left = op === '+' ? left + right : left - right;
            }
            return left;
        }
        function parseTerm() {
            let left = parsePower();
            while (pos < tokens.length && tokens[pos].t === 'op' && (tokens[pos].v === '*' || tokens[pos].v === '/' || tokens[pos].v === '%')) {
                const op = tokens[pos++].v;
                const right = parsePower();
                if (op === '*') left *= right;
                else if (op === '/') {
                    if (right === 0) throw new Error('Division by zero');
                    left /= right;
                } else left %= right;
            }
            return left;
        }
        function parsePower() {
            let base = parseUnary();
            if (pos < tokens.length && tokens[pos].t === 'op' && tokens[pos].v === '**') {
                pos++;
                const exp = parsePower();
                if (Math.abs(exp) > 200) throw new Error('Exponent too large');
                base = Math.pow(base, exp);
            }
            return base;
        }
        function parseUnary() {
            if (pos < tokens.length && tokens[pos].t === 'op' && (tokens[pos].v === '+' || tokens[pos].v === '-')) {
                const op = tokens[pos++].v;
                const v = parseUnary();
                return op === '-' ? -v : v;
            }
            if (pos < tokens.length && tokens[pos].t === '(') {
                pos++;
                const v = parseExpr();
                if (pos >= tokens.length || tokens[pos].t !== ')') throw new Error('Unmatched parenthesis');
                pos++;
                return v;
            }
            if (pos < tokens.length && tokens[pos].t === 'num') {
                return tokens[pos++].v;
            }
            throw new Error('Invalid expression');
        }
        try {
            const ans = parseExpr();
            if (pos !== tokens.length || !Number.isFinite(ans)) return null;
            return Number.isInteger(ans) ? String(ans) : String(Number(ans.toFixed(6)));
        } catch (_) {
            return null;
        }
    }

    function _detectHinglish(text) {
        return /\b(bhai|yaar|kya|kaise|kaisa|kar|karo|karde|bata|batao|mera|meri|mere|mujhe|nahi|hai|hain|haan|theek|thik|chahiye|banado|banao|samjha|samjhao|yaad|rakhna|shukriya|dhanyawad|namaste|salam|assalam|aaj|kal|kitna|kitne|kaun|kaha|kyu|kyun)\b/i.test(text);
    }

    function _analyzePastedCode(code) {
        const issues = [];
        const lines = code.split('\n');
        lines.forEach((ln, idx) => {
            const n = idx + 1;
            if (/==\s*None\b|!=\s*None\b/.test(ln)) issues.push(`Line ${n}: Use \`is None\` / \`is not None\` instead of \`==\`/\`!=\`.`);
            if (/^\s*except\s*:\s*$/.test(ln)) issues.push(`Line ${n}: Bare \`except:\` catches system exits — use \`except Exception as exc:\`.`);
            if (/\beval\s*\(|\bexec\s*\(/.test(ln)) issues.push(`Line ${n}: Unsafe \`eval()\`/\`exec()\` call — use a safe parser or explicit dispatch.`);
            if (/\.execute\s*\(\s*f['"]/.test(ln)) issues.push(`Line ${n}: **SQL Injection risk** — replace f-string SQL with parameterized \`?\` placeholders.`);
            if (/shell\s*=\s*True/.test(ln)) issues.push(`Line ${n}: **Shell Injection risk** — pass an argument list with \`shell=False\`.`);
            if (/innerHTML\s*[+]?=.*\+/.test(ln)) issues.push(`Line ${n}: **XSS risk** — avoid raw string concatenation into \`innerHTML\`; use \`textContent\` or escaping.`);
            if (/def\s+\w+\([^)]*=\s*(\[\]|\{\})/.test(ln)) issues.push(`Line ${n}: **Mutable default argument** — default to \`None\` and initialize inside the function.`);
        });
        return issues;
    }

    function _buildCodingAnswer(low, isHi) {
        if (/\b(binary\s*search)\b/.test(low)) {
            return (isHi ? 'Yeh raha clean, O(log n) **Binary Search** implementation:\n\n' : 'Here is a clean, `O(log n)` **Binary Search** implementation:\n\n') +
                '```python\ndef binary_search(arr: list[int], target: int) -> int:\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = lo + (hi - lo) // 2\n        if arr[mid] == target:\n            return mid\n        if arr[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1\n```\n\n- **Time Complexity:** `O(log n)` · **Space Complexity:** `O(1)`';
        }
        if (/\b(fibonacci|fib)\b/.test(low)) {
            return (isHi ? 'Yeh raha fast **O(n) Fibonacci** code:\n\n' : 'Here is an optimized `O(n)` iterative **Fibonacci** implementation:\n\n') +
                '```python\ndef fibonacci(n: int) -> list[int]:\n    seq = []\n    a, b = 0, 1\n    for _ in range(max(0, n)):\n        seq.append(a)\n        a, b = b, a + b\n    return seq\n```';
        }
        if (/\b(palindrome)\b/.test(low)) {
            return '```python\ndef is_palindrome(text: str) -> bool:\n    clean = "".join(ch.lower() for ch in text if ch.isalnum())\n    return clean == clean[::-1]\n```';
        }
        if (/\b(sort|quicksort|mergesort)\b/.test(low)) {
            return 'Here is a clean **Merge Sort** (`O(n log n)` guaranteed):\n\n```python\ndef merge_sort(arr: list) -> list:\n    if len(arr) <= 1:\n        return arr\n    mid = len(arr) // 2\n    left = merge_sort(arr[:mid])\n    right = merge_sort(arr[mid:])\n    out, i, j = [], 0, 0\n    while i < len(left) and j < len(right):\n        if left[i] <= right[j]:\n            out.append(left[i]); i += 1\n        else:\n            out.append(right[j]); j += 1\n    return out + left[i:] + right[j:]\n```';
        }
        if (/\b(rest\s*api|fastapi|flask|backend|server|endpoint)\b/.test(low)) {
            return 'Here is a production-ready **FastAPI REST API** starter:\n\n```python\nfrom fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel\n\napp = FastAPI(title="AURA API")\nITEMS: dict[int, dict] = {}\n\nclass Item(BaseModel):\n    name: str\n    price: float\n\n@app.get("/health")\ndef health():\n    return {"status": "ok"}\n\n@app.post("/items/{item_id}")\ndef create_item(item_id: int, item: Item):\n    ITEMS[item_id] = item.model_dump()\n    return {"saved": True, "item": ITEMS[item_id]}\n```';
        }
        if (/\b(html|landing\s*page|website|portfolio|button|css|navbar|login\s*page)\b/.test(low)) {
            return 'Here is a clean responsive **Modern Dark HTML/CSS Card Starter**:\n\n```html\n<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n  <title>AURA Starter</title>\n  <style>\n    body { margin:0; min-height:100vh; display:grid; place-items:center; background:#0b0c0e; color:#f4f5f7; font-family:system-ui,sans-serif; }\n    .card { width:min(92vw,420px); padding:24px; border-radius:14px; background:#14161b; border:1px solid rgba(255,255,255,0.1); }\n    button { width:100%; margin-top:14px; padding:11px; border:0; border-radius:9px; background:#7aa2ff; color:#0b0c0e; font-weight:700; cursor:pointer; }\n  </style>\n</head>\n<body>\n  <main class="card">\n    <h2>Welcome</h2>\n    <p>Clean responsive dark layout ready to customize.</p>\n    <button type="button" onclick="alert(\'Action ready!\')">Continue</button>\n  </main>\n</body>\n</html>\n```';
        }
        if (/\b(sql|database|query|join|table|sqlite|postgres)\b/.test(low)) {
            return 'Here is a parameterized **SQL Schema + Safe Query Pattern**:\n\n```sql\nCREATE TABLE IF NOT EXISTS users (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    username TEXT UNIQUE NOT NULL,\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\n\n-- Always use parameterized queries to prevent SQL injection:\nSELECT id, username, created_at FROM users WHERE username = ?;\n```';
        }
        if (/\b(git|commit|push|branch|merge|rebase|stash)\b/.test(low)) {
            return (isHi ? '### Git Quick Workflow\n\n' : '### Essential Git Workflow\n\n') +
                '```bash\n# Check changes & diff\ngit status -s\ngit diff\n\n# Stage, commit & push cleanly\ngit add <files>\ngit commit -m "Describe your change clearly"\ngit push origin main\n\n# Safe feature branch\ngit checkout -b feature/my-update\n```';
        }
        if (/\b(react|component|hook|usestate|useeffect)\b/.test(low)) {
            return 'Here is a clean **React Functional Component** with `useState`:\n\n```jsx\nimport { useState } from "react";\n\nexport default function CounterCard() {\n  const [count, setCount] = useState(0);\n  return (\n    <div style={{ padding: 20, borderRadius: 12, background: "#111216", color: "#fff" }}>\n      <h3>Count: {count}</h3>\n      <button onClick={() => setCount((c) => c + 1)}>Increment</button>\n    </div>\n  );\n}\n```';
        }
        if (/\b(cyber\s*security|owasp|xss|sql\s*injection|sqli|csrf|encryption|hashing|firewall|secure)\b/.test(low)) {
            return (isHi ? '### Defensive Cybersecurity Essentials\n\n' : '### Defensive Cybersecurity Essentials\n\n') +
                '- **SQL Injection (SQLi):** Always use parameterized queries (`?` / `$1`), never concatenate user input into SQL strings.\n' +
                '- **XSS Defense:** Escape untrusted HTML (`textContent` instead of `innerHTML`) and enforce strict `Content-Security-Policy`.\n' +
                '- **Passwords:** Hash with `scrypt` / `argon2id` + unique per-user random salt, verified with constant-time comparison.\n' +
                '- **Sessions & Auth:** Use `HttpOnly; Secure; SameSite=Lax` cookies, CSRF tokens on state-changing POSTs, and login rate-limiting.';
        }
        if (/\b(ai\s+agent|agentic|llm|rag|transformer|machine\s+learning|neural\s+network)\b/.test(low)) {
            return '### Modern Agentic AI Architecture\n\n' +
                '1. **Planner / Orchestrator:** Breaks a user goal into ordered, verifiable steps.\n' +
                '2. **Tool Runtime:** Executes deterministic actions (code sandbox, file ops, search, APIs) with strict permission guardrails.\n' +
                '3. **Memory Layer:** Combines short-term conversation context with persistent user/project memory.\n' +
                '4. **Verification Loop:** Runs tests/checks after edits and self-heals failures before reporting completion.';
        }
        if (/\b(python|javascript|typescript|java|c\+\+|node\.?js)\b/.test(low) && /\b(example|hello|starter|script|code|function|class|loop|async)\b/.test(low)) {
            if (/\b(javascript|typescript|node)\b/.test(low)) {
                return 'Here is a clean modern **Async JavaScript / Fetch Helper with Retry**:\n\n```js\nasync function fetchWithRetry(url, opts = {}, retries = 2) {\n  for (let i = 0; i <= retries; i++) {\n    try {\n      const res = await fetch(url, opts);\n      if (!res.ok) throw new Error(`HTTP ${res.status}`);\n      return await res.json();\n    } catch (err) {\n      if (i === retries) throw err;\n      await new Promise(r => setTimeout(r, 400 * (i + 1)));\n    }\n  }\n}\n```';
            }
            return 'Here is a clean, production-style **Python Starter Utility**:\n\n```python\nfrom dataclasses import dataclass\n\n@dataclass\nclass Task:\n    title: str\n    done: bool = False\n\ndef summarize(tasks: list[Task]) -> str:\n    done_cnt = sum(1 for t in tasks if t.done)\n    return f"Completed {done_cnt}/{len(tasks)} tasks"\n\nprint(summarize([Task("Design API", True), Task("Ship build")]))\n```';
        }
        return null;
    }

    function generateReply(promptRaw, _history) {
        const prompt = String(promptRaw || '').trim();
        const low = prompt.toLowerCase();
        const isHi = _detectHinglish(prompt);
        const prof = detectDeviceNow();
        const friendlyDev = getFriendlyDeviceLabel(prof);

        if (!prompt) {
            return isHi ? 'Kuch type karo bhai, main sun raha hoon!' : 'Type anything and I will help right away.';
        }

        // 1. Slash commands working 100% locally on Mobile!
        if (prompt.startsWith('/')) {
            const parts = prompt.split(/\s+/);
            const cmd = parts[0].toLowerCase();
            const arg = prompt.slice(cmd.length).trim();

            if (cmd === '/device') {
                return (
                    `### Active Device Profile\n\n` +
                    `- **Device:** \`${friendlyDev}\`\n` +
                    `- **Class:** \`${prof.device_class}\`\n` +
                    `- **Network:** \`${isOfflineNow() ? 'Offline (100% Free Local Mobile Engine Active)' : 'Online'}\`\n` +
                    `- **Chat, Memory, Notes, Code Helper & Calculator:** \`ACTIVE\``
                );
            }
            if (cmd === '/help') {
                return (
                    `### AURA Commands\n\n` +
                    `- \`/calc <expression>\` — Instant exact math & percentage calculator\n` +
                    `- \`/write <filename> <text>\` — Save a file locally on your phone\n` +
                    `- \`/read <filename>\` — Read a saved local file\n` +
                    `- \`/files\` — List saved local workspace files\n` +
                    `- \`/notes\` — View all saved personal memories & notes\n` +
                    `- \`/device\` — View detected device & status\n` +
                    `- Or just chat normally in **English or Hinglish** for coding, writing, study plans, bug checks, math, and daily help!`
                );
            }
            if (cmd === '/calc') {
                const ans = _safeEvalMath(arg);
                return ans !== null
                    ? `\`${arg}\` = **${ans}**`
                    : 'Usage: `/calc (2500 * 18) / 100`';
            }
            if (cmd === '/files' || cmd === '/ls') {
                const fsMap = _loadJson(FS_STORAGE_KEY, {});
                const names = Object.keys(fsMap);
                if (!names.length) return 'No local files saved yet. Use `/write notes.txt Hello AURA` to save one!';
                return `### Local Workspace Files (${names.length})\n\n` + names.map(n => `- \`${n}\` (${String(fsMap[n]).length} chars)`).join('\n');
            }
            if (cmd === '/write') {
                const m = arg.match(/^(\S+)\s+([\s\S]+)$/);
                if (!m) return 'Usage: `/write <filename> <content>`';
                const fsMap = _loadJson(FS_STORAGE_KEY, {});
                fsMap[m[1]] = m[2];
                _saveJson(FS_STORAGE_KEY, fsMap);
                return `Saved \`${m[1]}\` (${m[2].length} chars) cleanly in your local workspace.`;
            }
            if (cmd === '/read' || cmd === '/cat') {
                const fsMap = _loadJson(FS_STORAGE_KEY, {});
                if (!arg || !(arg in fsMap)) return `File \`${arg || '(empty)'}\` not found. Run \`/files\` to see saved files.`;
                return `### \`${arg}\`\n\n\`\`\`\n${fsMap[arg]}\n\`\`\``;
            }
            if (cmd === '/notes') {
                const mems = _loadJson(MEM_STORAGE_KEY, []);
                if (!mems.length) return 'No saved memories yet. Tell me `"Remember that ..."` anytime!';
                return `### Saved Memories (${mems.length})\n\n` + mems.map((m, i) => `${i + 1}. ${m.text}`).join('\n');
            }
        }

        // 2. Identity & Creator
        if (/\b(who\s+(built|created|made|developed|coded)\s+you|tumhe\s+kisne\s+banaya|who\s+are\s+you|tum\s+kaun\s+ho|your\s+name)\b/i.test(prompt)) {
            return isHi
                ? 'Main **AURA** hoon — ek sovereign AI assistant aur coding workspace jise **Mohd Ahmed (Lyberty / AURA Technologies Inc.)** ne design aur build kiya hai. Batao aaj kya help karu?'
                : 'I am **AURA**, an autonomous AI assistant and developer workspace architected by **Mohd Ahmed (Lyberty / AURA Technologies Inc.)**. How can I help you right now?';
        }

        // 3. Memory save & recall ("remember that...", "yaad rakhna...")
        const remMatch = prompt.match(/^(?:please\s+)?(?:remember\s+(?:that\s+)?|save\s+note\s*:?\s*|yaad\s+rakh(?:na|o)?\s*(?:ki\s+)?)(.+)$/i);
        if (remMatch && remMatch[1].trim().length > 2) {
            const noteText = remMatch[1].trim().slice(0, 400);
            const mems = _loadJson(MEM_STORAGE_KEY, []);
            mems.unshift({ text: noteText, at: new Date().toLocaleString() });
            _saveJson(MEM_STORAGE_KEY, mems.slice(0, 80));
            return isHi
                ? `Done bhai! Maine yaad rakh liya:\n> ${noteText}\n\nKabhi bhi \`/notes\` ya *"mere notes dikhao"* bol kar dekh sakte ho.`
                : `Saved to your local memory vault:\n> ${noteText}\n\nAsk *"show my memories"* or run \`/notes\` anytime to recall it.`;
        }
        if (/\b(what\s+did\s+i\s+(?:ask\s+you\s+to\s+)?remember|show\s+(?:my\s+)?(?:notes|memories)|mere\s+notes|yaad\s+kya\s+rakha)\b/i.test(prompt)) {
            const mems = _loadJson(MEM_STORAGE_KEY, []);
            if (!mems.length) {
                return isHi
                    ? 'Abhi koi note save nahi hai. Bas bol do *"Yaad rakhna kal 9 baje exam hai"* aur main save kar lunga!'
                    : 'No memories saved yet. Just say *"Remember that my exam is tomorrow at 9 AM"* and I will store it.';
            }
            return `### Your Saved Memories (${mems.length})\n\n` + mems.map((m, i) => `${i + 1}. **${m.text}** *(${m.at})*`).join('\n');
        }

        // 4. Time & Date
        if (/\b(what\s+time|current\s+time|aaj\s+ki\s+date|today'?s?\s+date|what\s+day\s+is\s+it|kitne\s+baje|samay\s+kya)\b/i.test(prompt)) {
            const now = new Date();
            const tStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const dStr = now.toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
            return isHi
                ? `Abhi **${tStr}** baj rahe hain, aur aaj **${dStr}** hai.`
                : `It is currently **${tStr}** on **${dStr}**.`;
        }

        // 5. Percentage, Math & Unit Conversions
        const pctMatch = prompt.match(/(\d+(?:\.\d+)?)\s*%\s*(?:of|ka)\s*(\d+(?:\.\d+)?)/i);
        if (pctMatch) {
            const pct = Number(pctMatch[1]);
            const base = Number(pctMatch[2]);
            const res = Number(((pct / 100) * base).toFixed(4));
            return `**${pct}% of ${base}** = **${res}**`;
        }
        const unitMatch = prompt.match(/(\d+(?:\.\d+)?)\s*(km|miles?|mi|m|cm|ft|kg|lbs?|g|c|celsius|f|fahrenheit|gb|mb|tb)\s+(?:to|in|into|mein)\s+(km|miles?|mi|m|cm|ft|kg|lbs?|g|c|celsius|f|fahrenheit|gb|mb|tb)/i);
        if (unitMatch) {
            const val = Number(unitMatch[1]);
            const fromU = unitMatch[2].toLowerCase();
            const toU = unitMatch[3].toLowerCase();
            let ans = null;
            if (fromU === 'km' && toU.startsWith('mi')) ans = (val * 0.621371).toFixed(4) + ' miles';
            else if (fromU.startsWith('mi') && toU === 'km') ans = (val * 1.60934).toFixed(4) + ' km';
            else if (fromU === 'kg' && toU.startsWith('lb')) ans = (val * 2.20462).toFixed(4) + ' lbs';
            else if (fromU.startsWith('lb') && toU === 'kg') ans = (val / 2.20462).toFixed(4) + ' kg';
            else if ((fromU === 'c' || fromU === 'celsius') && (toU === 'f' || toU === 'fahrenheit')) ans = ((val * 9) / 5 + 32).toFixed(2) + ' °F';
            else if ((fromU === 'f' || fromU === 'fahrenheit') && (toU === 'c' || toU === 'celsius')) ans = (((val - 32) * 5) / 9).toFixed(2) + ' °C';
            else if (fromU === 'gb' && toU === 'mb') ans = (val * 1024).toFixed(2) + ' MB';
            else if (fromU === 'mb' && toU === 'gb') ans = (val / 1024).toFixed(4) + ' GB';
            else if (fromU === 'tb' && toU === 'gb') ans = (val * 1024).toFixed(2) + ' GB';
            else if (fromU === 'm' && toU === 'cm') ans = (val * 100).toFixed(2) + ' cm';
            else if (fromU === 'm' && toU === 'ft') ans = (val * 3.28084).toFixed(4) + ' ft';
            else if (fromU === 'ft' && toU === 'm') ans = (val * 0.3048).toFixed(4) + ' m';
            if (ans) return `**${val} ${fromU.toUpperCase()}** = **${ans}**`;
        }
        const mathCandidate = prompt.replace(/^(?:calculate|calc|solve|what\s+is|eval|kitna\s+hoga)\s+/i, '').replace(/\?+$/, '').trim();
        if (/[+\-*/^%]/.test(mathCandidate) && /\d/.test(mathCandidate)) {
            const ans = _safeEvalMath(mathCandidate);
            if (ans !== null) return `\`${mathCandidate}\` = **${ans}**`;
        }

        // 6. Pasted Code Bug / Review Analyzer
        if (prompt.includes('\n') && /(def |function |const |let |SELECT |class |import |<\w+)/.test(prompt)) {
            const issues = _analyzePastedCode(prompt);
            if (issues.length) {
                return `### Code Review & Bug Findings (${issues.length})\n\n` + issues.map(x => `- ${x}`).join('\n');
            }
            return isHi
                ? 'Maine aapka code scan kiya — koi obvious syntax ya security red flag (`eval`, SQLi, `shell=True`, bare `except`) nahi mila. Agar koi specific bug ya optimization chahiye toh batao!'
                : 'I scanned your code snippet and found zero critical static red flags (`eval`, SQL injection, `shell=True`, bare `except`). Tell me what behavior or optimization you want to add next!';
        }

        // 7. Coding Patterns & Dev Templates
        const codeAns = _buildCodingAnswer(low, isHi);
        if (codeAns) return codeAns;

        // 8. Writing / Email / Study / Planning Helpers
        if (/\b(email|mail|application|leave\s+letter|sick\s+leave)\b/i.test(low)) {
            return (
                'Here is a crisp, ready-to-send draft:\n\n' +
                '**Subject:** Leave Request / Quick Update\n\n' +
                'Dear Sir/Ma\'am,\n\n' +
                'I am writing to inform you that I am currently unwell and need rest to recover quickly. I will stay updated on any urgent work and resume full attendance as soon as I feel better.\n\n' +
                'Thank you for your understanding.\n\n' +
                'Best regards,\n[Your Name]'
            );
        }
        if (/\b(study\s*plan|timetable|schedule|pomodoro|exam\s+prep|padhai)\b/i.test(low)) {
            return (
                '### Focused Study Sprint Plan (High Retention)\n\n' +
                '1. **Block 1 (45 min):** Core concept reading + active recall notes (phone on silent)\n' +
                '2. **Break (10 min):** Hydrate, stretch, zero scrolling\n' +
                '3. **Block 2 (45 min):** Solve 5–8 practice problems without looking at solutions\n' +
                '4. **Review (15 min):** Write down every mistake in a 1-page error sheet and test yourself once more\n\n' +
                (isHi ? 'Apna subject aur exam date batao, main exact chapter-wise plan bana dunga!' : 'Share your subject and exam date and I will tailor a chapter-by-chapter schedule!')
            );
        }

        // 9. Warm Greetings & Conversational Flow
        if (/^(hi+|hey+|hello+|yo+|hii+|namaste|salam|assalam\s*alaikum|good\s*(morning|afternoon|evening|night)|sup|hola|kaise\s+ho|kya\s+haal)/i.test(prompt)) {
            if (isHi) {
                return 'Hey bhai! Sab badhiya hai — AURA bilkul smooth ready hai. Coding, notes, math, study plan, writing, ya koi bhi sawaal ho, seedha bolo!';
            }
            return 'Hey! AURA is ready and running smoothly. Ask me anything — coding, debugging, calculations, writing, study planning, or notes!';
        }

        if (/\b(fever|bukhar|sick|unwell|tabiyat|headache|tired)\b/i.test(low)) {
            return isHi
                ? 'Apna khayal rakho bhai! Paani aur ORS/electrolytes peete raho, poori neend lo, aur screen time kam rakho. Agar fever 2 din se zyada rahe ya tez ho toh doctor ko zaroor dikhana. Jab rest kar lo tab main yahin hoon!'
                : 'Take care and get plenty of rest! Stay hydrated with water or electrolytes, keep screen time light, and check in with a doctor if a fever persists or spikes. I will be right here whenever you feel better.';
        }

        if (/\b(thank|thanks|shukriya|thx|awesome|great|nice|mast|zabardast)\b/i.test(low)) {
            return isHi
                ? 'Always welcome bhai! Kuch aur help chahiye ho toh bas bol dena.'
                : 'Anytime! Let me know whenever you need help with the next task.';
        }

        // 10. Live-internet-only queries handled gracefully & honestly
        if (/\b(live\s+score|weather\s+now|stock\s+price|bitcoin\s+price|today'?s?\s+news|latest\s+news)\b/i.test(low) && isOfflineNow()) {
            return isHi
                ? 'Live weather/news/prices ke liye internet connection chahiye hota hai — jaise hi Wi-Fi ya mobile data on hoga main real-time fetch kar dunga. Tab tak coding, math, notes, study plan, aur writing 100% chal raha hai!'
                : 'Live real-time news, weather, and market prices require an active internet connection — as soon as your signal returns I will fetch them live. Meanwhile, coding, math, notes, writing, and study help are 100% active right now.';
        }

        // 11. Smart Structured General Response (Never dead-ends or errors!)
        const cleanTopic = prompt.slice(0, 120);
        if (isHi) {
            return (
                `Samajh gaya bhai (**"${cleanTopic}"**). Chalo isko step-by-step clean tareeke se solve karte hain:\n\n` +
                `1. **Core Goal:** Pehle exact output ya requirement lock karo.\n` +
                `2. **Action Step:** Code, text, ya numbers yahan paste karo — main turant analyze, calculate, ya draft kar dunga.\n` +
                `3. **Save / Organize:** Agar kuch yaad rakhna ho toh *"Yaad rakhna ..."* ya \`/write notes.txt ...\` use kar sakte ho.\n\n` +
                `Thoda aur detail ya code/points bhejo, main seedha bana deta hoon!`
            );
        }
        return (
            `Got it — let's break down **"${cleanTopic}"** cleanly:\n\n` +
            `1. **Define the exact target:** Specify the language, format, or numbers you want.\n` +
            `2. **Execute directly:** Paste code to review/debug, write a math/unit expression to solve, or ask for a template (Python, JS, HTML, SQL, email, study plan).\n` +
            `3. **Save for later:** Say *"Remember that ..."* or use \`/write file.txt ...\` to keep it stored right on your phone.\n\n` +
            `Share a quick detail or paste your snippet and I will build it right away.`
        );
    }

    async function streamOfflineChatTurn(opts) {
        const prompt = String(opts.prompt || '');
        const turnData = opts.turnData;
        const renderMd = opts.renderMarkdown;
        const scrollFn = opts.scrollToBottom;
        const onComplete = opts.onComplete;

        const fullReply = generateReply(prompt, opts.history || []);
        if (turnData && turnData.thinking) turnData.thinking.style.display = 'none';

        // Stream smoothly word-by-word just like live SSE
        const words = fullReply.split(/(\s+)/);
        let acc = '';
        const chunkSize = words.length > 120 ? 5 : 2;
        for (let i = 0; i < words.length; i += chunkSize) {
            acc += words.slice(i, i + chunkSize).join('');
            if (turnData && turnData.bubble) {
                turnData.bubble.innerHTML = (typeof renderMd === 'function' ? renderMd(acc) : acc) + '<span class="streaming-cursor"></span>';
            }
            if (typeof scrollFn === 'function') scrollFn();
            await new Promise(r => setTimeout(r, 14));
        }

        if (turnData && turnData.bubble) {
            turnData.bubble.innerHTML = typeof renderMd === 'function' ? renderMd(fullReply) : fullReply;
        }
        if (typeof scrollFn === 'function') scrollFn();
        if (typeof onComplete === 'function') {
            await onComplete(fullReply);
        }
        return fullReply;
    }

    // Auto-enforce device offline policy on load & network transitions
    function initDevicePolicyListeners() {
        enforceDeviceOfflinePolicy();
        global.addEventListener('offline', () => {
            enforceDeviceOfflinePolicy();
        });
        global.addEventListener('online', () => {
            enforceDeviceOfflinePolicy();
            if (typeof global.onAuraBackOnlineSync === 'function') {
                try { global.onAuraBackOnlineSync(); } catch (_) {}
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDevicePolicyListeners);
    } else {
        setTimeout(initDevicePolicyListeners, 0);
    }

    global.AuraOfflineMobile = {
        detectDeviceNow,
        getFriendlyDeviceLabel,
        isMobilePhone,
        isLaptopOrDesktop,
        isOfflineNow,
        enforceDeviceOfflinePolicy,
        saveLastMobileUser,
        getLastMobileUser,
        generateReply,
        streamOfflineChatTurn,
    };
})(window);
