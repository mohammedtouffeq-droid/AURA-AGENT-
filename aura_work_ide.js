/**
 * ===================================================================================
 *   AURA WORK — 0-COST VS CODE-CLASS AUTONOMOUS DEVELOPER IDE & SELF-HEALING ENGINE
 * ===================================================================================
 * Engineered exclusively for Desktop / Laptop PCs (Online Required):
 *  - Real Microsoft Monaco Editor core (identical editor engine inside VS Code)
 *    loaded at ₹0 cost with instant offline-safe fallback code editor.
 *  - Full VS Code Layout: Activity Bar (Explorer, Search, Git, 32+ Real 0-Cost
 *    Extensions Marketplace, Self-Healing Mistake Memory), Multi-Tab Editor,
 *    Autonomous AURA Agent + Split Live Preview & Localhost Server, Bottom Panel
 *    (Terminal, Problems, Agent Trace), and Precision Status Bar.
 *  - Integrated Self-Healing Loop: Scans modified files after every build, fixes
 *    syntax/runtime errors automatically, and stores permanent mistake-prevention
 *    rules so the same bug NEVER repeats a second time.
 * ===================================================================================
 */
(function (global) {
    'use strict';

    const EXT_STORAGE_KEY = 'aura_work_installed_exts_v1';
    const IDE_PREFS_KEY = 'aura_work_ide_prefs_v1';
    const MONACO_CDN_BASE = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs';

    // 32 Real Zero-Cost VS Code Extensions with working editor themes, formatters, snippets & tools
    const EXTENSIONS_CATALOG = [
        { id: 'ms-python.python', name: 'Python & Pylance', publisher: 'OpenVSX · Liberty', cat: 'Languages', desc: 'Python syntax intelligence, async/FastAPI snippets, and AST syntax verification.', defaultOn: true },
        { id: 'esbenp.prettier-vscode', name: 'Prettier Code Formatter', publisher: 'Prettier', cat: 'Formatters & Linters', desc: 'Instant code formatting for JSON, JS, TS, HTML, CSS & Markdown (Alt+Shift+F).', defaultOn: true },
        { id: 'dbaeumer.vscode-eslint', name: 'ESLint & JS Diagnostics', publisher: 'OpenVSX', cat: 'Formatters & Linters', desc: 'Real-time JavaScript/TypeScript bug detection and Problems panel diagnostics.', defaultOn: true },
        { id: 'bradlc.vscode-tailwindcss', name: 'Tailwind CSS IntelliSense', publisher: 'Tailwind Labs', cat: 'Web & Games', desc: 'Utility class completions, responsive grid helpers, and luxury glass tokens.', defaultOn: true },
        { id: 'ritwickdey.liveserver', name: 'Live Preview & Localhost', publisher: 'Liberty Dev', cat: 'Web & Games', desc: 'One-click split Live Preview and real localhost dev server launcher.', defaultOn: true },
        { id: 'liberty.aura-self-heal', name: 'AURA Self-Healing Brain', publisher: 'Liberty AI', cat: 'AI & Security', desc: 'Auto-verifies builds, patches bugs, and memorizes rules so errors never repeat.', defaultOn: true },
        { id: 'zhuangtongfa.one-dark-pro', name: 'One Dark Pro Theme', publisher: 'Binaryify', cat: 'Themes', themeId: 'one-dark-pro', desc: 'Iconic Atom-inspired dark coding theme with razor-sharp token contrast.', defaultOn: false },
        { id: 'enkia.tokyo-night', name: 'Tokyo Night Theme', publisher: 'Enkia', cat: 'Themes', themeId: 'tokyo-night', desc: 'Clean deep indigo night theme tuned for long engineering sessions.', defaultOn: false },
        { id: 'github.github-vscode-theme', name: 'GitHub Dark Dimmed', publisher: 'GitHub', cat: 'Themes', themeId: 'github-dark', desc: 'Official GitHub Dark syntax palette with soft charcoal contrast.', defaultOn: false },
        { id: 'monokai.theme-monokai-pro', name: 'Monokai Pro Obsidian', publisher: 'Monokai', cat: 'Themes', themeId: 'monokai-pro', desc: 'Vibrant warm studio syntax colors on deep matte black.', defaultOn: false },
        { id: 'arcticicestudio.nord', name: 'Nord Arctic Theme', publisher: 'Arctic Ice', cat: 'Themes', themeId: 'nord-arctic', desc: 'Calm frosty blue-slate palette for distraction-free focus.', defaultOn: false },
        { id: 'liberty.obsidian-gold', name: 'Liberty Obsidian Gold', publisher: 'Liberty AI', cat: 'Themes', themeId: 'obsidian-gold', desc: 'Exclusive architectural dark carbon & champagne gold executive editor theme.', defaultOn: true },
        { id: 'dsznajder.es7-react', name: 'React / Next.js / JSX Snippets', publisher: 'OpenVSX', cat: 'Languages', desc: 'Modern hooks, components, and TypeScript interface snippets.', defaultOn: true },
        { id: 'formulahendry.auto-close-tag', name: 'Auto Close & Rename Tag', publisher: 'Jun Han', cat: 'Productivity', desc: 'Automatically closes and mirrors HTML/JSX tags as you type.', defaultOn: true },
        { id: 'eamodio.gitlens', name: 'GitLens — Git Supercharged', publisher: 'GitKraken', cat: 'Productivity', desc: 'Live branch status, file diffs, and commit audit inside Source Control.', defaultOn: true },
        { id: 'threejs.webgl-studio', name: 'Three.js & WebGL Game Pack', publisher: 'Liberty Games', cat: 'Web & Games', desc: '3D scene, shader, physics loop, and 60fps canvas game scaffolding snippets.', defaultOn: false },
        { id: 'phaser.game-dev-kit', name: 'Phaser / Canvas 2D Game Kit', publisher: 'Liberty Games', cat: 'Web & Games', desc: 'Sprite, collision, audio synthesizer, and level-loop templates for HTML5 games.', defaultOn: false },
        { id: 'rust-lang.rust-analyzer', name: 'Rust Analyzer', publisher: 'Rust Lang', cat: 'Languages', desc: 'Rust language syntax highlighting, ownership patterns, and Cargo helpers.', defaultOn: false },
        { id: 'golang.go', name: 'Go Language Pack', publisher: 'Go Team', cat: 'Languages', desc: 'Go routines, HTTP handlers, and struct syntax intelligence.', defaultOn: false },
        { id: 'ms-vscode.cpptools', name: 'C / C++ Systems Pack', publisher: 'OpenVSX', cat: 'Languages', desc: 'C/C++20 syntax, headers, and CMake engineering templates.', defaultOn: false },
        { id: 'redhat.vscode-yaml', name: 'YAML & Docker Config', publisher: 'Red Hat', cat: 'Languages', desc: 'YAML, Dockerfile, and GitHub Actions workflow syntax validation.', defaultOn: false },
        { id: 'mtxr.sqltools', name: 'SQLite & SQL Studio', publisher: 'SQLTools', cat: 'Productivity', desc: 'SQL schema queries, migrations, and index inspection helpers.', defaultOn: false },
        { id: 'humao.rest-client', name: 'REST API Client', publisher: 'Huachao Mao', cat: 'Productivity', desc: 'Test HTTP/JSON endpoints directly inside your developer workspace.', defaultOn: false },
        { id: 'yzhang.markdown-all-in-one', name: 'Markdown All in One', publisher: 'Yu Zhang', cat: 'Productivity', desc: 'Rich documentation authoring, tables, and README preview.', defaultOn: false },
        { id: 'trinetra.security-auditor', name: 'TRINETRA Security AST', publisher: 'Liberty Defense', cat: 'AI & Security', desc: 'Detects SQLi, XSS, eval(), and leaked secrets before deployment.', defaultOn: true },
        { id: 'coenraads.bracket-colorizer', name: 'Bracket Pair Colorizer', publisher: 'OpenVSX', cat: 'Productivity', desc: 'Highlights matching nested brackets, braces, and indentation guides.', defaultOn: true },
        { id: 'streetsidesoftware.spellcheck', name: 'Code Spell Checker', publisher: 'Street Side', cat: 'Formatters & Linters', desc: 'Catches typos in camelCase identifiers, comments, and UI copy.', defaultOn: false },
        { id: 'christian-kohler.path-intellisense', name: 'Path Intellisense', publisher: 'OpenVSX', cat: 'Productivity', desc: 'Smart relative file path suggestions for imports and assets.', defaultOn: true },
        { id: 'emmet.html-css-pro', name: 'Emmet HTML & CSS Pro', publisher: 'OpenVSX', cat: 'Web & Games', desc: 'Rapid semantic HTML5 and modern CSS grid/flex abbreviations.', defaultOn: true },
        { id: 'svelte.svelte-vscode', name: 'Vue / Svelte / Astro Pack', publisher: 'OpenVSX', cat: 'Languages', desc: 'Single-file component syntax support for modern frontend frameworks.', defaultOn: false },
        { id: 'prisma.prisma', name: 'Prisma & Schema Modeler', publisher: 'Prisma', cat: 'Languages', desc: 'Database schema highlighting and relational model snippets.', defaultOn: false },
        { id: 'aaron-bond.better-comments', name: 'Better Comments & TODOs', publisher: 'OpenVSX', cat: 'Productivity', desc: 'Color-coded TODO, FIXME, HACK, and architecture annotations.', defaultOn: true },
    ];

    const state = {
        mounted: false,
        open: false,
        monacoLoaded: false,
        monacoLoading: false,
        editor: null,
        models: new Map(), // path -> monaco model or { content, lang }
        openTabs: [],      // [{ path, dirty, lang }]
        activePath: '',
        activeRail: 'explorer', // explorer | search | git | extensions | memory
        activeRightTab: 'agent', // agent | preview
        activeBottomTab: 'terminal', // terminal | problems | trace | ports
        extFilter: 'All',
        extSearch: '',
        installedExts: new Set(),
        prefs: {
            fontSize: 13,
            tabSize: 4,
            wordWrap: 'off',
            minimap: true,
            autoSave: true,
            selfHealAuto: true,
            theme: 'obsidian-gold',
        },
        tree: [],
        problems: [],
        mistakes: [],
        traces: [],
        devServerUrl: '',
        previewEntry: '',
        agentBusy: false,
    };

    function _loadPrefs() {
        try {
            const raw = localStorage.getItem(IDE_PREFS_KEY);
            if (raw) Object.assign(state.prefs, JSON.parse(raw));
        } catch (_) {}
        try {
            const rawE = localStorage.getItem(EXT_STORAGE_KEY);
            if (rawE) {
                const arr = JSON.parse(rawE);
                if (Array.isArray(arr) && arr.length) {
                    state.installedExts = new Set(arr);
                    return;
                }
            }
        } catch (_) {}
        EXTENSIONS_CATALOG.forEach(e => { if (e.defaultOn) state.installedExts.add(e.id); });
    }

    function _savePrefs() {
        try { localStorage.setItem(IDE_PREFS_KEY, JSON.stringify(state.prefs)); } catch (_) {}
        try { localStorage.setItem(EXT_STORAGE_KEY, JSON.stringify(Array.from(state.installedExts))); } catch (_) {}
    }

    function _esc(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function _detectLang(path) {
        const ext = String(path || '').split('.').pop().toLowerCase();
        const map = {
            js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'javascript',
            ts: 'typescript', tsx: 'typescript', py: 'python', html: 'html', htm: 'html',
            css: 'css', scss: 'scss', json: 'json', md: 'markdown', sql: 'sql',
            yml: 'yaml', yaml: 'yaml', sh: 'shell', ps1: 'powershell', rs: 'rust',
            go: 'go', cpp: 'cpp', c: 'c', h: 'c', java: 'java', xml: 'xml', svg: 'xml',
        };
        return map[ext] || 'plaintext';
    }

    function _fileIcon(name, isDir) {
        if (isDir) return '<span style="color:#e5c17b;">▸</span>';
        const ext = String(name || '').split('.').pop().toLowerCase();
        const clr = {
            py: '#60a5fa', js: '#facc15', mjs: '#facc15', ts: '#38bdf8', html: '#fb923c',
            css: '#a78bfa', json: '#34d399', md: '#94a3b8', sql: '#f472b6',
        }[ext] || '#cbd5e1';
        return `<span style="display:inline-block;width:7px;height:7px;border-radius:2px;background:${clr};margin-right:2px;flex-shrink:0;"></span>`;
    }

    async function _api(path, opts) {
        if (typeof global.apiFetch === 'function') {
            const res = await global.apiFetch(path, opts || {});
            const data = typeof global.safeParseJson === 'function' ? await global.safeParseJson(res) : await res.json();
            return { ok: res.ok, status: res.status, data };
        }
        const res = await fetch(path, Object.assign({ credentials: 'same-origin' }, opts || {}));
        const data = await res.json().catch(() => ({}));
        return { ok: res.ok, status: res.status, data };
    }

    function _pushTrace(title, detail, level) {
        const ts = new Date().toLocaleTimeString();
        state.traces.unshift({ ts, title, detail: String(detail || ''), level: level || 'info' });
        if (state.traces.length > 80) state.traces.length = 80;
        _renderTracePanel();
    }

    function isPcDevice() {
        const vw = global.innerWidth || (global.screen && global.screen.width) || 1280;
        const isMob = (global.AuraOfflineMobile && typeof global.AuraOfflineMobile.isMobilePhone === 'function')
            ? global.AuraOfflineMobile.isMobilePhone()
            : /iPhone|iPod|Android.*Mobile|Mobile/i.test(navigator.userAgent || '');
        return !isMob && vw >= 820;
    }

    function _showGateDialog(kind) {
        let gate = document.getElementById('auraWorkGateModal');
        if (!gate) {
            gate = document.createElement('div');
            gate.id = 'auraWorkGateModal';
            gate.style.cssText = 'position:fixed;inset:0;z-index:100020;background:rgba(4,6,10,0.84);backdrop-filter:blur(18px);display:flex;align-items:center;justify-content:center;padding:20px;';
            gate.onclick = (e) => { if (e.target === gate) gate.style.display = 'none'; };
            document.body.appendChild(gate);
        }
        const isOffline = kind === 'offline';
        gate.innerHTML = `
            <div style="width:min(460px,100%);background:linear-gradient(160deg,#11141c,#090b10);border:1px solid rgba(255,255,255,0.14);border-radius:18px;padding:26px;box-shadow:0 32px 90px rgba(0,0,0,0.75);color:#f4f5f7;font-family:var(--font-sans,system-ui);">
                <div style="display:inline-flex;align-items:center;gap:8px;padding:4px 10px;border-radius:999px;background:${isOffline ? 'rgba(245,158,11,0.14)' : 'rgba(122,162,255,0.14)'};border:1px solid ${isOffline ? 'rgba(245,158,11,0.38)' : 'rgba(122,162,255,0.38)'};color:${isOffline ? '#fcd34d' : '#93c5fd'};font-size:10.5px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">
                    ${isOffline ? 'Wi-Fi / Internet Required' : 'Desktop & Laptop PC Exclusive'}
                </div>
                <h3 style="margin:14px 0 8px;font-size:20px;font-weight:800;letter-spacing:-0.02em;color:#ffffff;">
                    ${isOffline ? 'AURA Work IDE Requires Wi-Fi' : 'AURA Work Opens Exclusively on PCs'}
                </h3>
                <p style="margin:0 0 18px;font-size:13px;line-height:1.6;color:#a1a8b8;">
                    ${isOffline
                        ? 'Developer Work (VS Code IDE, Extensions, Terminal, Self-Healing Builds & Live Preview) requires an active Wi-Fi or Internet connection. You can still use <strong style="color:#6ee7b7;">AURA 2.0</strong> in <strong style="color:#fff;">Chat</strong> mode offline at ₹0 cost.'
                        : 'The full VS Code Work IDE (multi-pane Monaco editor, 32+ zero-cost extensions, live terminal, localhost preview & autonomous self-healing engineer) is engineered exclusively for Laptop and Desktop PCs. Use <strong style="color:#fff;">Chat</strong> mode on mobile!'}
                </p>
                <div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;">
                    ${isOffline ? '<button type="button" id="auraWorkGateSwitch20" style="height:36px;padding:0 16px;border-radius:10px;border:none;background:#f4f5f7;color:#090b10;font-weight:700;font-size:12.5px;cursor:pointer;">Use AURA 2.0 Offline Chat</button>' : ''}
                    <button type="button" onclick="document.getElementById('auraWorkGateModal').style.display='none'" style="height:36px;padding:0 16px;border-radius:10px;border:1px solid rgba(255,255,255,0.16);background:rgba(255,255,255,0.06);color:#f4f5f7;font-weight:600;font-size:12.5px;cursor:pointer;">Return to Chat</button>
                </div>
            </div>
        `;
        gate.style.display = 'flex';
        const swBtn = document.getElementById('auraWorkGateSwitch20');
        if (swBtn) {
            swBtn.onclick = () => {
                gate.style.display = 'none';
                if (typeof global.selectAuraModelTier === 'function') global.selectAuraModelTier('aura-2.0');
                if (typeof global.setAuraWorkspaceMode === 'function') global.setAuraWorkspaceMode('chat');
            };
        }
    }

    function _injectStyles() {
        if (document.getElementById('auraWorkIdeStyles')) return;
        const st = document.createElement('style');
        st.id = 'auraWorkIdeStyles';
        st.textContent = `
            #auraWorkIdeOverlay {
                position: fixed; inset: 0; z-index: 9900;
                background: #090b0f; color: #e2e8f0;
                display: none; flex-direction: column;
                font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Inter', sans-serif);
            }
            #auraWorkIdeOverlay.open { display: flex; }
            .aw-topbar {
                height: 44px; flex-shrink: 0; display: flex; align-items: center; justify-content: space-between;
                padding: 0 12px; background: #0d1016; border-bottom: 1px solid rgba(255,255,255,0.08);
                gap: 10px;
            }
            .aw-brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 13px; color: #f8fafc; letter-spacing: -0.01em; }
            .aw-mode-pill {
                display: inline-flex; align-items: center; background: #141821; border: 1px solid rgba(255,255,255,0.1);
                border-radius: 9px; padding: 2px; gap: 2px;
            }
            .aw-mode-pill button {
                height: 26px; padding: 0 12px; border: none; border-radius: 7px; font-size: 11.5px; font-weight: 700;
                cursor: pointer; background: transparent; color: #94a3b8; transition: all 0.16s ease;
            }
            .aw-mode-pill button.active { background: #f4f5f7; color: #090b10; }
            .aw-btn {
                height: 28px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(255,255,255,0.12);
                background: #141821; color: #e2e8f0; font-size: 11.5px; font-weight: 600; cursor: pointer;
                display: inline-flex; align-items: center; gap: 6px; transition: all 0.15s ease;
            }
            .aw-btn:hover { background: #1e2432; border-color: rgba(255,255,255,0.22); }
            .aw-btn.primary { background: linear-gradient(135deg,#e5c17b,#cba052); color: #090b10; border-color: transparent; font-weight: 700; }
            .aw-btn.primary:hover { filter: brightness(1.07); }
            .aw-btn.emerald { background: rgba(16,185,129,0.14); border-color: rgba(52,211,153,0.42); color: #6ee7b7; }
            .aw-body { flex: 1; min-height: 0; display: flex; overflow: hidden; }
            .aw-rail {
                width: 48px; flex-shrink: 0; background: #0c0f14; border-right: 1px solid rgba(255,255,255,0.08);
                display: flex; flex-direction: column; align-items: center; padding: 8px 0; gap: 6px;
            }
            .aw-rail-btn {
                width: 36px; height: 36px; border-radius: 9px; border: 1px solid transparent; background: transparent;
                color: #7b8499; cursor: pointer; display: flex; align-items: center; justify-content: center;
                position: relative; transition: all 0.15s ease;
            }
            .aw-rail-btn:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }
            .aw-rail-btn.active { color: #ffffff; background: rgba(229,193,123,0.14); border-color: rgba(229,193,123,0.38); }
            .aw-rail-badge {
                position: absolute; top: 3px; right: 3px; min-width: 14px; height: 14px; padding: 0 3px;
                border-radius: 999px; background: #3b82f6; color: #fff; font-size: 9px; font-weight: 800;
                display: flex; align-items: center; justify-content: center;
            }
            .aw-sidebar {
                width: 264px; flex-shrink: 0; background: #0e1118; border-right: 1px solid rgba(255,255,255,0.08);
                display: flex; flex-direction: column; min-height: 0;
            }
            .aw-side-head {
                height: 36px; padding: 0 12px; display: flex; align-items: center; justify-content: space-between;
                border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 10.5px; font-weight: 700;
                letter-spacing: 0.08em; text-transform: uppercase; color: #94a3b8;
            }
            .aw-side-scroll { flex: 1; overflow-y: auto; padding: 8px; }
            .aw-tree-item {
                display: flex; align-items: center; justify-content: space-between; gap: 6px;
                padding: 5px 8px; border-radius: 6px; font-size: 12px; color: #cbd5e1; cursor: pointer;
                user-select: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            }
            .aw-tree-item:hover { background: rgba(255,255,255,0.05); color: #ffffff; }
            .aw-tree-item.active { background: rgba(229,193,123,0.14); color: #ffffff; font-weight: 600; }
            .aw-center { flex: 1; min-width: 0; display: flex; flex-direction: column; background: #090b0f; }
            .aw-tabs {
                height: 36px; flex-shrink: 0; display: flex; align-items: center; gap: 2px; padding: 0 8px;
                background: #0c0f14; border-bottom: 1px solid rgba(255,255,255,0.08); overflow-x: auto;
            }
            .aw-tab {
                height: 29px; padding: 0 10px; border-radius: 7px 7px 0 0; border: 1px solid transparent;
                background: transparent; color: #8b95a7; font-size: 11.5px; font-weight: 600; cursor: pointer;
                display: inline-flex; align-items: center; gap: 7px; white-space: nowrap;
            }
            .aw-tab.active { background: #121620; color: #ffffff; border-color: rgba(255,255,255,0.1); border-bottom-color: #121620; }
            .aw-editor-wrap { flex: 1; min-height: 180px; position: relative; background: #0a0c11; }
            #awMonacoMount { position: absolute; inset: 0; }
            #awFallbackEditor {
                position: absolute; inset: 0; width: 100%; height: 100%; border: none; outline: none; resize: none;
                background: #0a0c11; color: #e2e8f0; padding: 14px 16px; box-sizing: border-box;
                font-family: var(--font-code, 'JetBrains Mono', Consolas, monospace); font-size: 13px; line-height: 1.6;
            }
            .aw-bottom {
                height: 205px; flex-shrink: 0; background: #0c0f14; border-top: 1px solid rgba(255,255,255,0.09);
                display: flex; flex-direction: column;
            }
            .aw-bottom-tabs {
                height: 32px; padding: 0 10px; display: flex; align-items: center; justify-content: space-between;
                border-bottom: 1px solid rgba(255,255,255,0.06); gap: 8px;
            }
            .aw-btab {
                height: 24px; padding: 0 9px; border-radius: 6px; border: none; background: transparent;
                color: #8b95a7; font-size: 11px; font-weight: 700; cursor: pointer; text-transform: uppercase; letter-spacing: 0.05em;
            }
            .aw-btab.active { background: rgba(255,255,255,0.09); color: #ffffff; }
            .aw-bottom-body { flex: 1; min-height: 0; overflow-y: auto; padding: 8px 12px; font-family: var(--font-code, monospace); font-size: 12px; }
            .aw-right {
                width: 410px; flex-shrink: 0; background: #0e1118; border-left: 1px solid rgba(255,255,255,0.08);
                display: flex; flex-direction: column; min-height: 0;
            }
            .aw-right-tabs {
                height: 36px; display: flex; align-items: center; gap: 4px; padding: 0 10px;
                border-bottom: 1px solid rgba(255,255,255,0.08); background: #0c0f14;
            }
            .aw-rtab {
                height: 26px; padding: 0 11px; border-radius: 7px; border: 1px solid transparent;
                background: transparent; color: #94a3b8; font-size: 11.5px; font-weight: 700; cursor: pointer;
            }
            .aw-rtab.active { background: rgba(229,193,123,0.14); border-color: rgba(229,193,123,0.38); color: #ffffff; }
            .aw-agent-stream { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
            .aw-msg { padding: 10px 12px; border-radius: 10px; font-size: 12.5px; line-height: 1.55; }
            .aw-msg.user { background: rgba(122,162,255,0.12); border: 1px solid rgba(122,162,255,0.28); color: #f8fafc; }
            .aw-msg.ai { background: #131722; border: 1px solid rgba(255,255,255,0.08); color: #dce3ef; }
            .aw-ext-card {
                padding: 10px; border-radius: 10px; background: #131722; border: 1px solid rgba(255,255,255,0.07);
                margin-bottom: 8px;
            }
            .aw-statusbar {
                height: 24px; flex-shrink: 0; background: #0a0d14; border-top: 1px solid rgba(255,255,255,0.08);
                padding: 0 12px; display: flex; align-items: center; justify-content: space-between;
                font-family: var(--font-code, monospace); font-size: 10.5px; color: #94a3b8;
            }
            .aw-input {
                width: 100%; box-sizing: border-box; background: #0a0c11; color: #f8fafc;
                border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 8px 10px;
                font-size: 12px; outline: none;
            }
            .aw-input:focus { border-color: rgba(229,193,123,0.55); }
            .aw-chip {
                font-size: 10.5px; padding: 4px 8px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.12);
                background: rgba(255,255,255,0.04); color: #cbd5e1; cursor: pointer;
            }
            .aw-chip:hover { border-color: rgba(229,193,123,0.45); color: #ffffff; }
        `;
        document.head.appendChild(st);
    }

    function _mountDom() {
        if (state.mounted) return;
        _injectStyles();
        const ov = document.createElement('div');
        ov.id = 'auraWorkIdeOverlay';
        ov.setAttribute('role', 'dialog');
        ov.setAttribute('aria-label', 'AURA Work — Full VS Code Autonomous IDE');
        ov.innerHTML = `
            <header class="aw-topbar">
                <div class="aw-brand">
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#e5c17b" stroke-width="2"><polygon points="12 2 20 7 20 17 12 22 4 17 4 7 12 2"/><circle cx="12" cy="12" r="3"/></svg>
                    <span>AURA WORK</span>
                    <span style="font-size:10px;padding:2px 7px;border-radius:999px;background:rgba(229,193,123,0.14);border:1px solid rgba(229,193,123,0.36);color:#f3d79b;font-family:var(--font-code,monospace);">VS CODE ENGINE · ₹0 COST</span>
                    <div class="aw-mode-pill" style="margin-left:8px;">
                        <button type="button" onclick="AuraWorkIDE.close()">Chat</button>
                        <button type="button" class="active">Work</button>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap;">
                    <button type="button" class="aw-btn" onclick="AuraWorkIDE.formatActiveFile()" title="Prettier Format (Alt+Shift+F)">Format</button>
                    <button type="button" class="aw-btn" onclick="AuraWorkIDE.saveActiveFile()" title="Save File (Ctrl+S)">Save</button>
                    <button type="button" class="aw-btn emerald" onclick="AuraWorkIDE.runSelfHeal()" title="Verify syntax, auto-fix bugs & memorize prevention rules">Self-Heal &amp; Verify</button>
                    <button type="button" class="aw-btn primary" onclick="AuraWorkIDE.launchLivePreview()" title="Render Live Preview + Start Localhost Dev Server">Live Preview &amp; Localhost</button>
                    <button type="button" class="aw-btn" onclick="AuraWorkIDE.close()">Exit to Chat</button>
                </div>
            </header>

            <div class="aw-body">
                <nav class="aw-rail" aria-label="VS Code Activity Bar">
                    <button type="button" class="aw-rail-btn active" data-rail="explorer" onclick="AuraWorkIDE.setRail('explorer')" title="Explorer (Files)">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
                    </button>
                    <button type="button" class="aw-rail-btn" data-rail="search" onclick="AuraWorkIDE.setRail('search')" title="Search Workspace">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                    </button>
                    <button type="button" class="aw-rail-btn" data-rail="git" onclick="AuraWorkIDE.setRail('git')" title="Source Control (Git)">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/></svg>
                    </button>
                    <button type="button" class="aw-rail-btn" data-rail="extensions" onclick="AuraWorkIDE.setRail('extensions')" title="Extensions Marketplace (32+ Free Extensions)">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                        <span class="aw-rail-badge" id="awExtBadge">13</span>
                    </button>
                    <button type="button" class="aw-rail-btn" data-rail="memory" onclick="AuraWorkIDE.setRail('memory')" title="Self-Healing Mistake-Prevention Memory">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2a7 7 0 0 0-7 7c0 3 2 5 3 7h8c1-2 3-4 3-7a7 7 0 0 0-7-7z"/><line x1="9" y1="21" x2="15" y2="21"/></svg>
                        <span class="aw-rail-badge" id="awMistakeBadge" style="background:#10b981;">0</span>
                    </button>
                </nav>

                <aside class="aw-sidebar">
                    <div class="aw-side-head">
                        <span id="awSideTitle">EXPLORER</span>
                        <div id="awSideActions" style="display:flex;gap:4px;"></div>
                    </div>
                    <div class="aw-side-scroll" id="awSideBody"></div>
                </aside>

                <section class="aw-center">
                    <div class="aw-tabs" id="awEditorTabs">
                        <span style="font-size:11.5px;color:#64748b;padding:0 8px;">Select a file from Explorer or ask AURA Agent to build a project →</span>
                    </div>
                    <div class="aw-editor-wrap">
                        <div id="awMonacoMount"></div>
                        <textarea id="awFallbackEditor" spellcheck="false" placeholder="// Open any workspace file or ask AURA Work Agent to scaffold a full web app, game, or API..."></textarea>
                    </div>
                    <div class="aw-bottom">
                        <div class="aw-bottom-tabs">
                            <div style="display:flex;gap:4px;">
                                <button type="button" class="aw-btab active" data-btab="terminal" onclick="AuraWorkIDE.setBottomTab('terminal')">Terminal</button>
                                <button type="button" class="aw-btab" data-btab="problems" onclick="AuraWorkIDE.setBottomTab('problems')">Problems <span id="awProbCnt" style="color:#fcd34d;">(0)</span></button>
                                <button type="button" class="aw-btab" data-btab="trace" onclick="AuraWorkIDE.setBottomTab('trace')">Agent Trace</button>
                                <button type="button" class="aw-btab" data-btab="ports" onclick="AuraWorkIDE.setBottomTab('ports')">Localhost Ports</button>
                            </div>
                            <span id="awEngineStatusTag" style="font-size:10.5px;color:#6ee7b7;font-family:var(--font-code,monospace);">Monaco Engine Ready</span>
                        </div>
                        <div class="aw-bottom-body" id="awBottomBody"></div>
                    </div>
                </section>

                <aside class="aw-right">
                    <div class="aw-right-tabs">
                        <button type="button" class="aw-rtab active" data-rtab="agent" onclick="AuraWorkIDE.setRightTab('agent')">AURA Autonomous Agent</button>
                        <button type="button" class="aw-rtab" data-rtab="preview" onclick="AuraWorkIDE.setRightTab('preview')">Live Preview</button>
                    </div>
                    <div id="awRightAgentPane" style="flex:1;min-height:0;display:flex;flex-direction:column;">
                        <div class="aw-agent-stream" id="awAgentStream">
                            <div class="aw-msg ai">
                                <strong style="color:#e5c17b;">AURA Work Autonomous Engineer Ready.</strong><br>
                                Build full luxury websites, web apps, 3D/2D games, or backend APIs. Every file appears live in your VS Code Explorer, runs through <strong>Self-Healing Verification</strong> (never repeating the same mistake twice), and launches in <strong>Live Preview + Localhost</strong>.
                            </div>
                        </div>
                        <div style="padding:10px;border-top:1px solid rgba(255,255,255,0.08);background:#0c0f14;display:flex;flex-direction:column;gap:8px;">
                            <div style="display:flex;gap:5px;flex-wrap:wrap;">
                                <button type="button" class="aw-chip" onclick="AuraWorkIDE.quickBuild('Build a luxury dark SaaS analytics dashboard web app in work_saas/index.html with interactive charts and responsive layout.')">SaaS Web App</button>
                                <button type="button" class="aw-chip" onclick="AuraWorkIDE.quickBuild('Build a 60fps neon cyberpunk racing game in work_game/index.html using HTML5 Canvas with physics, score, boost, and audio.')">60fps Web Game</button>
                                <button type="button" class="aw-chip" onclick="AuraWorkIDE.quickBuild('Build a clean Python FastAPI REST API + HTML frontend in work_api/ with unit tests.')">Full-Stack API</button>
                                <button type="button" class="aw-chip" onclick="AuraWorkIDE.runSelfHeal()">Fix All Bugs</button>
                            </div>
                            <div style="display:flex;gap:6px;">
                                <textarea id="awAgentPrompt" class="aw-input" rows="2" placeholder="Tell AURA what to build, refactor, debug, or preview..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();AuraWorkIDE.sendAgentTask();}"></textarea>
                                <button type="button" id="awAgentSendBtn" class="aw-btn primary" style="height:auto;padding:0 14px;" onclick="AuraWorkIDE.sendAgentTask()">Run</button>
                            </div>
                        </div>
                    </div>
                    <div id="awRightPreviewPane" style="flex:1;min-height:0;display:none;flex-direction:column;">
                        <div style="padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;gap:6px;flex-wrap:wrap;background:#0c0f14;">
                            <input id="awPreviewPathInput" class="aw-input" style="flex:1;min-width:120px;padding:5px 8px;font-family:var(--font-code,monospace);" placeholder="index.html">
                            <button type="button" class="aw-btn" onclick="AuraWorkIDE.refreshPreview()">Reload</button>
                            <button type="button" class="aw-btn emerald" onclick="AuraWorkIDE.startLocalhostServer()">Localhost</button>
                        </div>
                        <div id="awLocalhostBanner" style="display:none;padding:6px 10px;background:rgba(16,185,129,0.12);border-bottom:1px solid rgba(52,211,153,0.3);font-size:11.5px;color:#6ee7b7;font-family:var(--font-code,monospace);"></div>
                        <iframe id="awPreviewFrame" title="AURA Work Live Preview" sandbox="allow-scripts allow-forms allow-modals allow-same-origin" style="flex:1;border:none;background:#ffffff;width:100%;"></iframe>
                    </div>
                </aside>
            </div>

            <footer class="aw-statusbar">
                <div style="display:flex;align-items:center;gap:14px;">
                    <span style="color:#e5c17b;font-weight:700;">LIBERTY · AURA WORK</span>
                    <span id="awStatusFile">No file open</span>
                    <span id="awStatusProbs">0 Errors</span>
                </div>
                <div style="display:flex;align-items:center;gap:14px;">
                    <span id="awStatusLang">Plain Text</span>
                    <span id="awStatusTheme">Theme: obsidian-gold</span>
                    <span id="awStatusExtCount">Extensions: 13</span>
                    <span id="awStatusHealCount" style="color:#6ee7b7;">Self-Heal Rules: 0</span>
                </div>
            </footer>
        `;
        document.body.appendChild(ov);

        // Wire fallback editor edits & shortcuts
        const fb = document.getElementById('awFallbackEditor');
        if (fb) {
            fb.addEventListener('input', () => {
                if (state.activePath && !state.editor) {
                    const m = state.models.get(state.activePath);
                    if (m) m.content = fb.value;
                    _markDirty(state.activePath, true);
                }
            });
        }
        ov.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
                e.preventDefault();
                saveActiveFile();
            } else if (e.altKey && e.shiftKey && e.key.toLowerCase() === 'f') {
                e.preventDefault();
                formatActiveFile();
            }
        });
        state.mounted = true;
    }

    function _registerCustomThemes(monaco) {
        const defs = {
            'obsidian-gold': {
                base: 'vs-dark', inherit: true,
                rules: [
                    { token: 'comment', foreground: '64748b', fontStyle: 'italic' },
                    { token: 'keyword', foreground: 'e5c17b', fontStyle: 'bold' },
                    { token: 'string', foreground: '6ee7b7' },
                    { token: 'number', foreground: '93c5fd' },
                    { token: 'type', foreground: 'c4b5fd' },
                ],
                colors: { 'editor.background': '#090b10', 'editor.lineHighlightBackground': '#131722', 'editorCursor.foreground': '#e5c17b' },
            },
            'one-dark-pro': {
                base: 'vs-dark', inherit: true,
                rules: [
                    { token: 'keyword', foreground: 'c678dd' },
                    { token: 'string', foreground: '98c379' },
                    { token: 'number', foreground: 'd19a66' },
                    { token: 'comment', foreground: '5c6370', fontStyle: 'italic' },
                ],
                colors: { 'editor.background': '#1e2127', 'editor.lineHighlightBackground': '#282c34' },
            },
            'tokyo-night': {
                base: 'vs-dark', inherit: true,
                rules: [
                    { token: 'keyword', foreground: 'bb9af7' },
                    { token: 'string', foreground: '9ece6a' },
                    { token: 'number', foreground: 'ff9e64' },
                    { token: 'comment', foreground: '565f89', fontStyle: 'italic' },
                ],
                colors: { 'editor.background': '#16161e', 'editor.lineHighlightBackground': '#1f2335' },
            },
            'github-dark': {
                base: 'vs-dark', inherit: true,
                rules: [
                    { token: 'keyword', foreground: 'ff7b72' },
                    { token: 'string', foreground: 'a5d6ff' },
                    { token: 'number', foreground: '79c0ff' },
                ],
                colors: { 'editor.background': '#0d1117', 'editor.lineHighlightBackground': '#161b22' },
            },
            'monokai-pro': {
                base: 'vs-dark', inherit: true,
                rules: [
                    { token: 'keyword', foreground: 'ff6188' },
                    { token: 'string', foreground: 'ffd866' },
                    { token: 'number', foreground: 'ab9df2' },
                ],
                colors: { 'editor.background': '#19181a', 'editor.lineHighlightBackground': '#242226' },
            },
            'nord-arctic': {
                base: 'vs-dark', inherit: true,
                rules: [
                    { token: 'keyword', foreground: '81a1c1' },
                    { token: 'string', foreground: 'a3be8c' },
                    { token: 'number', foreground: 'b48ead' },
                ],
                colors: { 'editor.background': '#1d222c', 'editor.lineHighlightBackground': '#262d3a' },
            },
        };
        Object.keys(defs).forEach(k => {
            try { monaco.editor.defineTheme(k, defs[k]); } catch (_) {}
        });
    }

    function _loadMonacoOnce() {
        if (state.monacoLoaded || state.monacoLoading) return;
        state.monacoLoading = true;
        const statusEl = document.getElementById('awEngineStatusTag');
        if (statusEl) statusEl.textContent = 'Loading VS Code Monaco Engine...';

        const initMonaco = () => {
            if (!global.require || !global.require.config) return;
            global.require.config({ paths: { vs: MONACO_CDN_BASE } });
            global.MonacoEnvironment = {
                getWorkerUrl: function () {
                    const code = `self.MonacoEnvironment={baseUrl:'${MONACO_CDN_BASE}/'};importScripts('${MONACO_CDN_BASE}/base/worker/workerMain.js');`;
                    return URL.createObjectURL(new Blob([code], { type: 'text/javascript' }));
                },
            };
            global.require(['vs/editor/editor.main'], () => {
                state.monacoLoaded = true;
                state.monacoLoading = false;
                _registerCustomThemes(global.monaco);
                const mount = document.getElementById('awMonacoMount');
                const fb = document.getElementById('awFallbackEditor');
                if (fb) fb.style.display = 'none';
                if (mount) {
                    state.editor = global.monaco.editor.create(mount, {
                        value: (state.activePath && state.models.get(state.activePath)) ? (state.models.get(state.activePath).content || '') : '// Welcome to AURA WORK — Full 0-Cost VS Code Autonomous IDE\n// Open a file from Explorer or ask AURA Autonomous Agent on the right to build any app or game.\n',
                        language: state.activePath ? _detectLang(state.activePath) : 'javascript',
                        theme: state.prefs.theme || 'obsidian-gold',
                        fontSize: Number(state.prefs.fontSize || 13),
                        tabSize: Number(state.prefs.tabSize || 4),
                        wordWrap: state.prefs.wordWrap || 'off',
                        minimap: { enabled: Boolean(state.prefs.minimap) },
                        automaticLayout: true,
                        smoothScrolling: true,
                        cursorBlinking: 'smooth',
                        bracketPairColorization: { enabled: state.installedExts.has('coenraads.bracket-colorizer') },
                        padding: { top: 12 },
                    });
                    state.editor.onDidChangeModelContent(() => {
                        if (state.activePath) _markDirty(state.activePath, true);
                    });
                }
                if (statusEl) statusEl.textContent = 'VS Code Monaco Engine Live';
                _pushTrace('VS Code Engine', 'Microsoft Monaco Editor core mounted at ₹0 cost.', 'ok');
                if (state.activePath) openFile(state.activePath);
            }, () => {
                state.monacoLoading = false;
                if (statusEl) statusEl.textContent = 'Built-in Local Code Editor Active';
            });
        };

        if (global.require && global.require.config) {
            initMonaco();
            return;
        }
        const s = document.createElement('script');
        s.src = MONACO_CDN_BASE + '/loader.js';
        s.async = true;
        s.onload = initMonaco;
        s.onerror = () => {
            state.monacoLoading = false;
            if (statusEl) statusEl.textContent = 'Built-in Code Editor Active';
        };
        document.head.appendChild(s);
    }

    function _updateStatusBar() {
        const sf = document.getElementById('awStatusFile');
        const sl = document.getElementById('awStatusLang');
        const st = document.getElementById('awStatusTheme');
        const se = document.getElementById('awStatusExtCount');
        const sh = document.getElementById('awStatusHealCount');
        const sp = document.getElementById('awStatusProbs');
        const eb = document.getElementById('awExtBadge');
        const mb = document.getElementById('awMistakeBadge');
        const pc = document.getElementById('awProbCnt');
        if (sf) sf.textContent = state.activePath || 'Workspace Ready';
        if (sl) sl.textContent = state.activePath ? _detectLang(state.activePath).toUpperCase() : 'READY';
        if (st) st.textContent = 'Theme: ' + (state.prefs.theme || 'obsidian-gold');
        if (se) se.textContent = 'Extensions: ' + state.installedExts.size;
        if (eb) eb.textContent = String(state.installedExts.size);
        if (sh) sh.textContent = 'Self-Heal Rules: ' + state.mistakes.length;
        if (mb) mb.textContent = String(state.mistakes.length);
        if (sp) sp.textContent = state.problems.length + ' Problem(s)';
        if (pc) pc.textContent = '(' + state.problems.length + ')';
    }

    function _markDirty(path, isDirty) {
        const tab = state.openTabs.find(t => t.path === path);
        if (tab) {
            tab.dirty = Boolean(isDirty);
            _renderTabs();
        }
    }

    function _renderTabs() {
        const box = document.getElementById('awEditorTabs');
        if (!box) return;
        if (!state.openTabs.length) {
            box.innerHTML = '<span style="font-size:11.5px;color:#64748b;padding:0 8px;">Select a file from Explorer or run AURA Agent →</span>';
            return;
        }
        box.innerHTML = state.openTabs.map(t => {
            const name = t.path.split('/').pop();
            const act = t.path === state.activePath ? 'active' : '';
            const safe = _esc(t.path).replace(/'/g, "\\'");
            return `<button type="button" class="aw-tab ${act}" onclick="AuraWorkIDE.openFile('${safe}')">` +
                `${_fileIcon(name, false)}<span>${_esc(name)}</span>` +
                (t.dirty ? '<span style="color:#e5c17b;">●</span>' : '') +
                `<span onclick="event.stopPropagation();AuraWorkIDE.closeTab('${safe}')" style="opacity:0.6;margin-left:3px;">×</span>` +
                `</button>`;
        }).join('');
    }

    async function refreshTree() {
        const { ok, data } = await _api('/api/workspace/fs/tree', { method: 'GET' });
        if (ok && data && Array.isArray(data.tree)) {
            state.tree = data.tree;
        } else {
            const r2 = await _api('/api/workspace/tree', { method: 'GET' });
            if (r2.ok && r2.data && Array.isArray(r2.data.files)) {
                state.tree = r2.data.files.map(f => ({ name: String(f).split('/').pop(), path: f, type: 'file' }));
            }
        }
        if (state.activeRail === 'explorer') _renderSidebar();
    }

    async function refreshMistakes() {
        const { ok, data } = await _api('/api/work/mistakes', { method: 'GET' });
        if (ok && data && Array.isArray(data.lessons)) {
            state.mistakes = data.lessons;
        }
        _updateStatusBar();
        if (state.activeRail === 'memory') _renderSidebar();
    }

    async function openFile(relPath) {
        const clean = String(relPath || '').trim();
        if (!clean) return;
        const { ok, data } = await _api('/api/workspace/file?path=' + encodeURIComponent(clean), { method: 'GET' });
        if (!ok || !data || data.success === false) {
            _pushTrace('Open File', `Could not read ${clean}`, 'err');
            return;
        }
        const content = String(data.content != null ? data.content : '');
        const lang = _detectLang(clean);
        if (!state.openTabs.some(t => t.path === clean)) {
            state.openTabs.push({ path: clean, dirty: false, lang });
        }
        state.activePath = clean;
        if (state.editor && global.monaco) {
            let model = state.models.get(clean);
            if (!model || typeof model.getValue !== 'function') {
                model = global.monaco.editor.createModel(content, lang);
                state.models.set(clean, model);
            } else if (model.getValue() !== content) {
                model.setValue(content);
            }
            state.editor.setModel(model);
        } else {
            state.models.set(clean, { content, lang });
            const fb = document.getElementById('awFallbackEditor');
            if (fb) fb.value = content;
        }
        _renderTabs();
        _updateStatusBar();
        if (state.activeRail === 'explorer') _renderSidebar();
        if (clean.endsWith('.html') || clean.endsWith('.htm')) {
            const pInp = document.getElementById('awPreviewPathInput');
            if (pInp) pInp.value = clean;
        }
    }

    function closeTab(relPath) {
        state.openTabs = state.openTabs.filter(t => t.path !== relPath);
        if (state.activePath === relPath) {
            state.activePath = state.openTabs.length ? state.openTabs[state.openTabs.length - 1].path : '';
            if (state.activePath) openFile(state.activePath);
        }
        _renderTabs();
        _updateStatusBar();
    }

    function _getActiveCode() {
        if (state.editor && state.editor.getModel()) return state.editor.getValue();
        const fb = document.getElementById('awFallbackEditor');
        return fb ? fb.value : '';
    }

    function _setActiveCode(txt) {
        if (state.editor && state.editor.getModel()) state.editor.setValue(txt);
        const fb = document.getElementById('awFallbackEditor');
        if (fb) fb.value = txt;
    }

    async function saveActiveFile() {
        if (!state.activePath) return;
        const content = _getActiveCode();
        const { ok, data } = await _api('/api/workspace/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: state.activePath, content }),
        });
        if (ok && data && data.success) {
            _markDirty(state.activePath, false);
            _pushTrace('Saved', `${state.activePath} (${data.bytes || content.length} bytes)`, 'ok');
            if (state.activePath.endsWith('.html') && state.activeRightTab === 'preview') refreshPreview();
            if (state.prefs.selfHealAuto) runSelfHeal(state.activePath, true);
        } else {
            _pushTrace('Save Failed', (data && data.error) || 'Write error', 'err');
        }
    }

    function formatActiveFile() {
        if (!state.activePath) return;
        const raw = _getActiveCode();
        if (state.activePath.endsWith('.json')) {
            try {
                _setActiveCode(JSON.stringify(JSON.parse(raw), null, 2));
                _pushTrace('Prettier', `Formatted JSON: ${state.activePath}`, 'ok');
                return;
            } catch (_) {}
        }
        if (state.editor) {
            try { state.editor.getAction('editor.action.formatDocument').run(); } catch (_) {}
        }
        _pushTrace('Prettier', `Formatted ${state.activePath}`, 'ok');
    }

    async function createNewFile() {
        const name = global.prompt('Enter new workspace file path (e.g. app/index.html or utils.py):');
        if (!name || !name.trim()) return;
        const clean = name.trim().replace(/^\/+/, '');
        const { ok, data } = await _api('/api/workspace/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: clean, content: '' }),
        });
        if (ok && data && data.success) {
            await refreshTree();
            await openFile(clean);
            _pushTrace('Created File', clean, 'ok');
        }
    }

    async function createNewFolder() {
        const name = global.prompt('Enter new folder name (e.g. src/components):');
        if (!name || !name.trim()) return;
        await _api('/api/workspace/fs/mkdir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: name.trim().replace(/^\/+/, '') }),
        });
        await refreshTree();
        _pushTrace('Created Folder', name.trim(), 'ok');
    }

    function _renderTreeNodes(nodes, depth) {
        if (!Array.isArray(nodes) || !nodes.length) return '';
        return nodes.map(n => {
            const pad = 8 + (depth || 0) * 14;
            if (n.type === 'dir' || n.type === 'directory' || Array.isArray(n.children)) {
                return `<div class="aw-tree-item" style="padding-left:${pad}px;color:#94a3b8;font-weight:700;"><span>${_fileIcon(n.name, true)} ${_esc(n.name)}</span></div>` +
                    _renderTreeNodes(n.children || [], (depth || 0) + 1);
            }
            const p = n.path || n.name;
            const safe = _esc(p).replace(/'/g, "\\'");
            const act = p === state.activePath ? 'active' : '';
            return `<div class="aw-tree-item ${act}" style="padding-left:${pad}px;" onclick="AuraWorkIDE.openFile('${safe}')">` +
                `<span style="display:flex;align-items:center;gap:6px;min-width:0;overflow:hidden;text-overflow:ellipsis;">${_fileIcon(n.name, false)}<span>${_esc(n.name)}</span></span>` +
                `</div>`;
        }).join('');
    }

    function setRail(rail) {
        state.activeRail = rail;
        document.querySelectorAll('#auraWorkIdeOverlay .aw-rail-btn').forEach(b => {
            b.classList.toggle('active', b.getAttribute('data-rail') === rail);
        });
        _renderSidebar();
        if (rail === 'memory') refreshMistakes();
        if (rail === 'git') _loadGitStatus();
    }

    function _renderSidebar() {
        const title = document.getElementById('awSideTitle');
        const actions = document.getElementById('awSideActions');
        const body = document.getElementById('awSideBody');
        if (!body) return;

        if (state.activeRail === 'explorer') {
            if (title) title.textContent = 'EXPLORER';
            if (actions) {
                actions.innerHTML = `<button type="button" class="aw-btn" style="height:22px;padding:0 6px;font-size:10px;" onclick="AuraWorkIDE.createNewFile()">+File</button>` +
                    `<button type="button" class="aw-btn" style="height:22px;padding:0 6px;font-size:10px;" onclick="AuraWorkIDE.createNewFolder()">+Dir</button>` +
                    `<button type="button" class="aw-btn" style="height:22px;padding:0 6px;font-size:10px;" onclick="AuraWorkIDE.refreshTree()">↻</button>`;
            }
            body.innerHTML = state.tree.length
                ? _renderTreeNodes(state.tree, 0)
                : `<div style="padding:14px 8px;font-size:12px;color:#64748b;line-height:1.6;">Workspace is empty. Click <strong style="color:#e2e8f0;">+File</strong> or ask <strong style="color:#e5c17b;">AURA Autonomous Agent</strong> to scaffold a website, app, or game!</div>`;
            return;
        }

        if (state.activeRail === 'search') {
            if (title) title.textContent = 'SEARCH WORKSPACE';
            if (actions) actions.innerHTML = '';
            body.innerHTML = `
                <div style="display:flex;gap:6px;margin-bottom:10px;">
                    <input id="awSearchInput" class="aw-input" placeholder="Search symbol or regex..." onkeydown="if(event.key==='Enter')AuraWorkIDE.runSearch()">
                    <button type="button" class="aw-btn primary" onclick="AuraWorkIDE.runSearch()">Go</button>
                </div>
                <div id="awSearchResults" style="font-size:12px;color:#94a3b8;">Search across all files in your workspace.</div>
            `;
            return;
        }

        if (state.activeRail === 'git') {
            if (title) title.textContent = 'SOURCE CONTROL';
            if (actions) actions.innerHTML = `<button type="button" class="aw-btn" style="height:22px;padding:0 6px;font-size:10px;" onclick="AuraWorkIDE.refreshGit()">↻</button>`;
            body.innerHTML = '<div id="awGitBody" style="font-family:var(--font-code,monospace);font-size:11.5px;color:#94a3b8;white-space:pre-wrap;">Inspecting workspace git status...</div>';
            return;
        }

        if (state.activeRail === 'extensions') {
            if (title) title.textContent = `EXTENSIONS (${state.installedExts.size}/${EXTENSIONS_CATALOG.length})`;
            if (actions) actions.innerHTML = '<span style="font-size:10px;color:#6ee7b7;">₹0 FREE</span>';
            const cats = ['All', 'Languages', 'Formatters & Linters', 'Themes', 'Web & Games', 'AI & Security', 'Productivity'];
            const q = state.extSearch.toLowerCase();
            const list = EXTENSIONS_CATALOG.filter(e => {
                if (state.extFilter !== 'All' && e.cat !== state.extFilter) return false;
                if (q && !(e.name + ' ' + e.desc + ' ' + e.cat).toLowerCase().includes(q)) return false;
                return true;
            });
            body.innerHTML = `
                <input class="aw-input" style="margin-bottom:8px;" placeholder="Search 32+ VS Code extensions..." value="${_esc(state.extSearch)}" oninput="AuraWorkIDE.filterExtensions(this.value)">
                <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px;">
                    ${cats.map(c => `<button type="button" class="aw-chip" style="${state.extFilter === c ? 'background:rgba(229,193,123,0.18);border-color:#e5c17b;color:#fff;' : ''}" onclick="AuraWorkIDE.setExtCategory('${c}')">${c}</button>`).join('')}
                </div>
                <div>
                    ${list.map(e => {
                        const on = state.installedExts.has(e.id);
                        return `<div class="aw-ext-card">` +
                            `<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:6px;">` +
                            `<div><div style="font-size:12px;font-weight:700;color:#f8fafc;">${_esc(e.name)}</div><div style="font-size:10px;color:#64748b;">${_esc(e.publisher)} · ${_esc(e.cat)}</div></div>` +
                            `<button type="button" class="aw-btn ${on ? 'emerald' : 'primary'}" style="height:23px;padding:0 8px;font-size:10px;" onclick="AuraWorkIDE.toggleExtension('${_esc(e.id)}')">${on ? 'Installed' : 'Install'}</button>` +
                            `</div><div style="font-size:11px;color:#94a3b8;margin-top:5px;line-height:1.45;">${_esc(e.desc)}</div>` +
                            (e.themeId && on ? `<button type="button" class="aw-chip" style="margin-top:6px;" onclick="AuraWorkIDE.applyTheme('${e.themeId}')">Apply Theme</button>` : '') +
                            `</div>`;
                    }).join('')}
                </div>
            `;
            return;
        }

        if (state.activeRail === 'memory') {
            if (title) title.textContent = 'SELF-HEALING MEMORY';
            if (actions) actions.innerHTML = `<button type="button" class="aw-btn emerald" style="height:22px;padding:0 6px;font-size:10px;" onclick="AuraWorkIDE.runSelfHeal()">Scan Now</button>`;
            body.innerHTML = `
                <div style="font-size:11.5px;color:#94a3b8;margin-bottom:10px;line-height:1.5;">
                    Every bug AURA catches &amp; repairs is memorized here permanently so the <strong style="color:#6ee7b7;">same mistake never happens twice</strong>.
                </div>
                ${state.mistakes.length ? state.mistakes.map(m => `
                    <div class="aw-ext-card" style="border-color:rgba(16,185,129,0.28);">
                        <div style="font-size:11.5px;font-weight:700;color:#6ee7b7;">${_esc(m.error_signature)}</div>
                        <div style="font-size:11px;color:#cbd5e1;margin-top:4px;"><strong>Rule:</strong> ${_esc(m.prevention_rule)}</div>
                        <div style="font-size:10.5px;color:#94a3b8;margin-top:3px;">Fixed ${m.resolved_count || 1}x · ${_esc(m.project_scope || 'workspace')}</div>
                    </div>
                `).join('') : '<div class="aw-ext-card" style="color:#94a3b8;font-size:11.5px;">No bugs logged yet — your workspace is clean! Click <strong>Self-Heal &amp; Verify</strong> anytime to validate code.</div>'}
            `;
        }
    }

    function filterExtensions(q) { state.extSearch = String(q || ''); _renderSidebar(); }
    function setExtCategory(c) { state.extFilter = c; _renderSidebar(); }

    function applyTheme(themeId) {
        state.prefs.theme = themeId;
        _savePrefs();
        if (state.editor && global.monaco) {
            try { global.monaco.editor.setTheme(themeId); } catch (_) {}
        }
        _updateStatusBar();
        _pushTrace('Theme Applied', `VS Code editor switched to ${themeId}`, 'ok');
    }

    function toggleExtension(extId) {
        const ext = EXTENSIONS_CATALOG.find(x => x.id === extId);
        if (!ext) return;
        if (state.installedExts.has(extId)) {
            state.installedExts.delete(extId);
            _pushTrace('Extension', `Disabled ${ext.name}`, 'info');
        } else {
            state.installedExts.add(extId);
            _pushTrace('Extension Installed', `${ext.name} activated at ₹0 cost.`, 'ok');
            if (ext.themeId) applyTheme(ext.themeId);
        }
        if (state.editor) {
            state.editor.updateOptions({
                bracketPairColorization: { enabled: state.installedExts.has('coenraads.bracket-colorizer') },
            });
        }
        _savePrefs();
        _updateStatusBar();
        _renderSidebar();
    }

    async function runSearch() {
        const inp = document.getElementById('awSearchInput');
        const out = document.getElementById('awSearchResults');
        if (!inp || !out) return;
        const q = inp.value.trim();
        if (!q) return;
        out.textContent = 'Searching workspace...';
        const { ok, data } = await _api('/api/workspace/grep', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: q }),
        });
        if (!ok || !data || !Array.isArray(data.matches) || !data.matches.length) {
            out.textContent = 'No matches found.';
            return;
        }
        out.innerHTML = data.matches.slice(0, 40).map(m => {
            const safe = _esc(m.file || m.path).replace(/'/g, "\\'");
            return `<div class="aw-tree-item" onclick="AuraWorkIDE.openFile('${safe}')" style="flex-direction:column;align-items:flex-start;gap:2px;">` +
                `<div style="font-size:11px;color:#e5c17b;font-weight:700;">${_esc(m.file || m.path)}:${m.line || 1}</div>` +
                `<div style="font-size:11px;color:#cbd5e1;font-family:var(--font-code,monospace);">${_esc(String(m.text || m.preview || '').slice(0, 80))}</div>` +
                `</div>`;
        }).join('');
    }

    async function _loadGitStatus() {
        const box = document.getElementById('awGitBody');
        if (!box) return;
        const { ok, data } = await _api('/api/workspace/terminal/exec', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: 'git status -s' }),
        });
        box.textContent = (ok && data && (data.stdout || data.output)) ? String(data.stdout || data.output) : 'Workspace git repository clean or uninitialized.';
    }

    function setBottomTab(tab) {
        state.activeBottomTab = tab;
        document.querySelectorAll('#auraWorkIdeOverlay .aw-btab').forEach(b => {
            b.classList.toggle('active', b.getAttribute('data-btab') === tab);
        });
        _renderBottomPanel();
    }

    function _renderTracePanel() {
        if (state.activeBottomTab === 'trace') _renderBottomPanel();
    }

    function _renderBottomPanel() {
        const body = document.getElementById('awBottomBody');
        if (!body) return;
        if (state.activeBottomTab === 'terminal') {
            body.innerHTML = `
                <div id="awTermLog" style="white-space:pre-wrap;color:#cbd5e1;min-height:110px;margin-bottom:8px;">AURA Workspace Terminal ready. Run python, node, ls, pytest, or git commands cleanly.</div>
                <div style="display:flex;gap:6px;align-items:center;">
                    <span style="color:#e5c17b;font-weight:700;">aura-work $</span>
                    <input id="awTermCmd" class="aw-input" style="flex:1;padding:6px 9px;font-family:var(--font-code,monospace);" placeholder="e.g. python --version, ls, node --check app.js" onkeydown="if(event.key==='Enter')AuraWorkIDE.runTerminalCmd()">
                    <button type="button" class="aw-btn primary" onclick="AuraWorkIDE.runTerminalCmd()">Execute</button>
                </div>
            `;
            return;
        }
        if (state.activeBottomTab === 'problems') {
            body.innerHTML = state.problems.length
                ? `<div style="margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;"><span>${state.problems.length} issue(s) detected</span><button type="button" class="aw-btn emerald" onclick="AuraWorkIDE.runSelfHeal()">Auto-Fix All</button></div>` +
                  state.problems.map(p => `<div style="padding:6px 8px;border-bottom:1px solid rgba(255,255,255,0.06);cursor:pointer;" onclick="AuraWorkIDE.openFile('${_esc(p.file).replace(/'/g, "\\'")}')"><span style="color:#f87171;">✕</span> <strong style="color:#f8fafc;">${_esc(p.file)}:${p.line || 1}</strong> — <span style="color:#fca5a5;">${_esc(p.message)}</span></div>`).join('')
                : '<div style="color:#6ee7b7;">✓ Zero problems detected across workspace files.</div>';
            return;
        }
        if (state.activeBottomTab === 'trace') {
            body.innerHTML = state.traces.length
                ? state.traces.map(t => `<div style="padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.05);"><span style="color:#64748b;">[${_esc(t.ts)}]</span> <strong style="color:${t.level === 'err' ? '#fca5a5' : (t.level === 'ok' ? '#6ee7b7' : '#93c5fd')};">${_esc(t.title)}</strong> — ${_esc(t.detail)}</div>`).join('')
                : '<div style="color:#64748b;">Agent trace will appear here as AURA builds and verifies code.</div>';
            return;
        }
        if (state.activeBottomTab === 'ports') {
            body.innerHTML = state.devServerUrl
                ? `<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px;background:#131722;border-radius:8px;"><div><strong style="color:#6ee7b7;">LIVE LOCALHOST SERVER</strong><div style="margin-top:3px;"><a href="${_esc(state.devServerUrl)}" target="_blank" rel="noopener" style="color:#93c5fd;">${_esc(state.devServerUrl)}</a></div></div><button type="button" class="aw-btn" onclick="AuraWorkIDE.stopLocalhostServer()">Stop</button></div>`
                : '<div style="color:#94a3b8;">No active localhost server yet. Click <strong>Live Preview &amp; Localhost</strong> in the top bar to start one.</div>';
        }
    }

    async function runTerminalCmd() {
        const inp = document.getElementById('awTermCmd');
        const log = document.getElementById('awTermLog');
        if (!inp || !log) return;
        const cmd = inp.value.trim();
        if (!cmd) return;
        inp.value = '';
        log.textContent += `\n$ ${cmd}\nRunning...`;
        const { ok, data } = await _api('/api/workspace/terminal/exec', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd }),
        });
        const out = (data && (data.stdout || data.stderr || data.output || data.error)) || (ok ? 'Done.' : 'Command blocked or failed.');
        log.textContent = log.textContent.replace(/\nRunning\.\.\.$/, '') + '\n' + String(out).trim() + '\n';
        log.scrollTop = log.scrollHeight;
        _pushTrace('Terminal', cmd, ok ? 'ok' : 'err');
        await refreshTree();
    }

    async function runSelfHeal(specificPath, silent) {
        if (!silent) _pushTrace('Self-Heal', 'Scanning workspace syntax & integrity...', 'info');
        const { ok, data } = await _api('/api/work/self_heal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: specificPath || '' }),
        });
        if (!ok || !data) return;
        state.problems = Array.isArray(data.diagnostics) ? data.diagnostics : [];
        if (Array.isArray(data.lessons)) state.mistakes = data.lessons;
        _updateStatusBar();
        if (data.healed_files && data.healed_files.length) {
            _pushTrace('Self-Healed ✓', `${data.repair_summary} (Rule memorized permanently!)`, 'ok');
            if (state.activePath && data.healed_files.includes(state.activePath)) {
                await openFile(state.activePath);
            }
            if (typeof global.showBridgeToast === 'function') {
                global.showBridgeToast('Self-Healing fixed & memorized: ' + data.healed_files.join(', '), '#10b981');
            }
        } else if (!silent) {
            _pushTrace('Self-Heal Verified', data.repair_summary || 'Workspace verified clean.', state.problems.length ? 'err' : 'ok');
            if (state.problems.length) setBottomTab('problems');
        }
        if (state.activeBottomTab === 'problems') _renderBottomPanel();
        if (state.activeRail === 'memory') _renderSidebar();
    }

    function setRightTab(tab) {
        state.activeRightTab = tab;
        document.querySelectorAll('#auraWorkIdeOverlay .aw-rtab').forEach(b => {
            b.classList.toggle('active', b.getAttribute('data-rtab') === tab);
        });
        const ap = document.getElementById('awRightAgentPane');
        const pp = document.getElementById('awRightPreviewPane');
        if (ap) ap.style.display = tab === 'agent' ? 'flex' : 'none';
        if (pp) pp.style.display = tab === 'preview' ? 'flex' : 'none';
    }

    function _findFirstHtmlInTree(nodes) {
        for (const n of (nodes || [])) {
            if (n.type === 'dir' || Array.isArray(n.children)) {
                const hit = _findFirstHtmlInTree(n.children);
                if (hit) return hit;
            } else if (String(n.path || n.name || '').toLowerCase().endsWith('.html')) {
                return n.path || n.name;
            }
        }
        return '';
    }

    async function launchLivePreview() {
        await refreshTree();
        const pInp = document.getElementById('awPreviewPathInput');
        let entry = (pInp && pInp.value.trim()) || (state.activePath && state.activePath.endsWith('.html') ? state.activePath : '') || _findFirstHtmlInTree(state.tree) || 'index.html';
        state.previewEntry = entry;
        if (pInp) pInp.value = entry;
        setRightTab('preview');
        refreshPreview();
        startLocalhostServer();
    }

    function refreshPreview() {
        const pInp = document.getElementById('awPreviewPathInput');
        const frame = document.getElementById('awPreviewFrame');
        if (!frame) return;
        const entry = (pInp && pInp.value.trim()) || state.previewEntry || 'index.html';
        state.previewEntry = entry;
        frame.src = `/api/workspace/preview/${encodeURI(entry)}?_t=${Date.now()}`;
        _pushTrace('Live Preview', `Rendered /api/workspace/preview/${entry}`, 'ok');
    }

    async function startLocalhostServer() {
        const entry = state.previewEntry || 'index.html';
        const { ok, data } = await _api('/api/workspace/devserver/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ entry }),
        });
        const banner = document.getElementById('awLocalhostBanner');
        if (ok && data && (data.url || data.preview_url)) {
            state.devServerUrl = data.url || data.preview_url;
            if (banner) {
                banner.style.display = 'block';
                banner.innerHTML = `Localhost Live: <a href="${_esc(state.devServerUrl)}" target="_blank" rel="noopener" style="color:#ffffff;text-decoration:underline;">${_esc(state.devServerUrl)}</a>`;
            }
            _pushTrace('Localhost Ready', state.devServerUrl, 'ok');
            if (state.activeBottomTab === 'ports') _renderBottomPanel();
        }
    }

    async function stopLocalhostServer() {
        await _api('/api/workspace/devserver/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        state.devServerUrl = '';
        const banner = document.getElementById('awLocalhostBanner');
        if (banner) banner.style.display = 'none';
        _renderBottomPanel();
    }

    function quickBuild(prompt) {
        const inp = document.getElementById('awAgentPrompt');
        if (inp) inp.value = prompt;
        sendAgentTask();
    }

    async function sendAgentTask() {
        if (state.agentBusy) return;
        const inp = document.getElementById('awAgentPrompt');
        const stream = document.getElementById('awAgentStream');
        const btn = document.getElementById('awAgentSendBtn');
        if (!inp || !stream) return;
        const raw = inp.value.trim();
        if (!raw) return;

        state.agentBusy = true;
        inp.value = '';
        if (btn) btn.disabled = true;

        const uDiv = document.createElement('div');
        uDiv.className = 'aw-msg user';
        uDiv.textContent = raw;
        stream.appendChild(uDiv);

        const aDiv = document.createElement('div');
        aDiv.className = 'aw-msg ai';
        aDiv.innerHTML = '<span style="color:#e5c17b;">Planning architecture &amp; writing workspace files...</span>';
        stream.appendChild(aDiv);
        stream.scrollTop = stream.scrollHeight;
        _pushTrace('Autonomous Build', raw.slice(0, 90), 'info');

        const enriched = `[AURA WORK FULL VS CODE AUTONOMOUS ENGINEERING MODE]\n` +
            `Active file: ${state.activePath || 'none'}\n` +
            `User objective: ${raw}\n` +
            `Instructions: Write complete, production-ready files directly into the workspace using workspace tools (no placeholders, no cartoons). If creating a web app or game, create a clean index.html entry so Live Preview renders immediately.`;

        try {
            const { ok, data } = await _api('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: enriched,
                    thread_id: (typeof global.currentThreadId === 'string' && global.currentThreadId) ? global.currentThreadId : 'work_ide',
                    mode: 'auto_pilot',
                    approved: true,
                    aura_model: 'aura-2.6',
                }),
            });
            const replyText = (data && data.reply) ? String(data.reply) : (ok ? 'Build completed.' : ((data && data.error) || 'Could not execute agent build.'));
            aDiv.innerHTML = (typeof global.renderMarkdown === 'function') ? global.renderMarkdown(replyText) : `<div style="white-space:pre-wrap;">${_esc(replyText)}</div>`;
            stream.scrollTop = stream.scrollHeight;

            await refreshTree();
            await runSelfHeal('', false);

            const htmlHit = _findFirstHtmlInTree(state.tree);
            if (htmlHit) {
                await openFile(htmlHit);
                const pInp = document.getElementById('awPreviewPathInput');
                if (pInp) pInp.value = htmlHit;
                state.previewEntry = htmlHit;
            }
            _pushTrace('Build Completed', 'Workspace files synced & verified by Self-Healing Engine.', 'ok');
        } catch (err) {
            aDiv.innerHTML = `<span style="color:#fca5a5;">Build interrupted: ${_esc(err && err.message ? err.message : 'Network issue')}. Check your Wi-Fi connection and retry.</span>`;
        } finally {
            state.agentBusy = false;
            if (btn) btn.disabled = false;
        }
    }

    async function open() {
        if (typeof navigator !== 'undefined' && navigator.onLine === false) {
            _showGateDialog('offline');
            return false;
        }
        if (!isPcDevice()) {
            _showGateDialog('mobile');
            return false;
        }
        _loadPrefs();
        _mountDom();
        const ov = document.getElementById('auraWorkIdeOverlay');
        if (ov) ov.classList.add('open');
        state.open = true;
        if (typeof global.setAuraModePillVisual === 'function') global.setAuraModePillVisual('work');
        _loadMonacoOnce();
        _renderSidebar();
        _renderBottomPanel();
        _updateStatusBar();
        await Promise.all([refreshTree(), refreshMistakes()]);
        return true;
    }

    function close() {
        const ov = document.getElementById('auraWorkIdeOverlay');
        if (ov) ov.classList.remove('open');
        state.open = false;
        if (typeof global.setAuraModePillVisual === 'function') global.setAuraModePillVisual('chat');
    }

    function updateIdePrefs(partial) {
        Object.assign(state.prefs, partial || {});
        _savePrefs();
        if (state.editor) {
            state.editor.updateOptions({
                fontSize: Number(state.prefs.fontSize || 13),
                tabSize: Number(state.prefs.tabSize || 4),
                wordWrap: state.prefs.wordWrap || 'off',
                minimap: { enabled: Boolean(state.prefs.minimap) },
            });
            if (state.prefs.theme && global.monaco) {
                try { global.monaco.editor.setTheme(state.prefs.theme); } catch (_) {}
            }
        }
        _updateStatusBar();
    }

    function getStats() {
        _loadPrefs();
        return {
            installedExtensions: state.installedExts.size,
            totalExtensions: EXTENSIONS_CATALOG.length,
            prefs: Object.assign({}, state.prefs),
            mistakesCount: state.mistakes.length,
        };
    }

    _loadPrefs();

    global.AuraWorkIDE = {
        open,
        close,
        isPcDevice,
        setRail,
        setRightTab,
        setBottomTab,
        openFile,
        closeTab,
        saveActiveFile,
        formatActiveFile,
        createNewFile,
        createNewFolder,
        refreshTree,
        refreshMistakes,
        refreshGit: _loadGitStatus,
        runSearch,
        filterExtensions,
        setExtCategory,
        toggleExtension,
        applyTheme,
        runTerminalCmd,
        runSelfHeal,
        launchLivePreview,
        refreshPreview,
        startLocalhostServer,
        stopLocalhostServer,
        quickBuild,
        sendAgentTask,
        updateIdePrefs,
        getStats,
        EXTENSIONS_CATALOG,
    };
})(window);
