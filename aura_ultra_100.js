/**
 * ===================================================================================
 *   AURA ULTRA — 100 ANTIGRAVITY CAPABILITIES MATRIX + ASK-PERMISSION GUARDRAIL UI
 * ===================================================================================
 * 1. Interactive 100-Capability AURA Ultra Command Matrix (10 Pillars x 10 Powers):
 *    - Searchable, filterable by pillar, showing live ACTIVE vs LOCKED tier state.
 *    - Every single capability launches or executes its real backing AURA engine
 *      (Live Browser, Screen/Computer Use, VS Code Work IDE, Self-Healing Memory,
 *      4-Agent War Room, Security AST Audit, VOX Ultra Call, 4K Studio, Reports, etc.).
 * 2. Universal Ask-Permission Safety Modal (`window.requestAuraActionPermission`):
 *    - Protects Live Browser Control clicks/submits/agents AND Screen/Desktop Control
 *      actions with an explicit Allow Once / Allow This Session / Deny confirmation!
 * ===================================================================================
 */
(function (global) {
    'use strict';

    const state = {
        mounted: false,
        open: false,
        data: null,
        unlocked: false,
        activePillar: 'all',
        search: '',
        sessionAllowedCategories: new Set(),
    };

    function _esc(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    async function _api(path, opts) {
        if (typeof global.apiFetch === 'function') {
            const res = await global.apiFetch(path, opts || {});
            const data = typeof global.safeParseJson === 'function' ? await global.safeParseJson(res) : await res.json();
            return { ok: res.ok, status: res.status, data };
        }
        const res = await fetch(path, Object.assign({ credentials: 'same-origin' }, opts || {}));
        return { ok: res.ok, status: res.status, data: await res.json().catch(() => ({})) };
    }

    // =========================================================================
    // 1. UNIVERSAL ASK-PERMISSION GUARDRAIL POPUP (Browser + Screen + OS)
    // =========================================================================
    function requestAuraActionPermission(spec) {
        const opts = spec || {};
        const category = String(opts.category || 'action').toLowerCase();
        const title = String(opts.title || 'AURA Permission Request');
        const actionLabel = String(opts.action || 'Execute action');
        const target = String(opts.target || 'Active workspace / viewport');
        const risk = String(opts.risk || 'MEDIUM').toUpperCase();
        const forcePrompt = Boolean(opts.forcePrompt);

        if (!forcePrompt && state.sessionAllowedCategories.has(category)) {
            return Promise.resolve({ allowed: true, mode: 'session_cached' });
        }

        return new Promise((resolve) => {
            let ov = document.getElementById('auraAskPermOverlay');
            if (!ov) {
                ov = document.createElement('div');
                ov.id = 'auraAskPermOverlay';
                ov.style.cssText = 'position:fixed;inset:0;z-index:100080;background:rgba(4,6,11,0.82);backdrop-filter:blur(16px);display:none;align-items:center;justify-content:center;padding:18px;font-family:var(--font-sans,system-ui);';
                document.body.appendChild(ov);
            }
            const riskCol = risk === 'HIGH' ? '#f87171' : (risk === 'LOW' ? '#34d399' : '#fbbf24');
            ov.innerHTML = `
                <div style="width:min(490px,100%);background:linear-gradient(160deg,#111520,#090b10);border:1px solid rgba(255,255,255,0.16);border-radius:18px;padding:24px;box-shadow:0 36px 100px rgba(0,0,0,0.85);color:#f8fafc;">
                    <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
                        <div style="display:inline-flex;align-items:center;gap:8px;padding:4px 10px;border-radius:999px;background:rgba(56,189,248,0.14);border:1px solid rgba(56,189,248,0.4);color:#7dd3fc;font-size:10.5px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">
                            AURA Safety Guardrail · Ask Permission
                        </div>
                        <span style="font-family:var(--font-code,monospace);font-size:10.5px;font-weight:800;color:${riskCol};padding:3px 8px;border-radius:6px;background:rgba(255,255,255,0.06);border:1px solid ${riskCol}55;">${_esc(risk)} RISK</span>
                    </div>
                    <h3 style="margin:14px 0 6px;font-size:19px;font-weight:800;letter-spacing:-0.02em;color:#ffffff;">${_esc(title)}</h3>
                    <p style="margin:0 0 14px;font-size:12.5px;color:#94a3b8;line-height:1.55;">AURA is requesting your explicit permission before controlling this surface. You remain in 100% control at all times.</p>
                    <div style="padding:12px 14px;border-radius:12px;background:rgba(0,0,0,0.42);border:1px solid rgba(255,255,255,0.08);font-family:var(--font-code,monospace);font-size:11.5px;display:flex;flex-direction:column;gap:6px;margin-bottom:18px;">
                        <div><span style="color:#64748b;">ACTION :</span> <strong style="color:#f8fafc;">${_esc(actionLabel)}</strong></div>
                        <div><span style="color:#64748b;">TARGET :</span> <span style="color:#93c5fd;word-break:break-all;">${_esc(target)}</span></div>
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;">
                        <button type="button" id="apBtnDeny" style="height:36px;padding:0 15px;border-radius:10px;border:1px solid rgba(248,113,113,0.45);background:rgba(248,113,113,0.14);color:#fecaca;font-weight:700;font-size:12px;cursor:pointer;">Deny</button>
                        <button type="button" id="apBtnSession" style="height:36px;padding:0 15px;border-radius:10px;border:1px solid rgba(255,255,255,0.18);background:rgba(255,255,255,0.07);color:#f8fafc;font-weight:700;font-size:12px;cursor:pointer;">Allow This Session</button>
                        <button type="button" id="apBtnOnce" style="height:36px;padding:0 18px;border-radius:10px;border:none;background:linear-gradient(135deg,#f8fafc,#cbd5e1);color:#090b10;font-weight:800;font-size:12px;cursor:pointer;">Allow Once ✓</button>
                    </div>
                </div>
            `;
            ov.style.display = 'flex';
            const done = (allowed, mode) => {
                ov.style.display = 'none';
                resolve({ allowed, mode });
            };
            document.getElementById('apBtnDeny').onclick = () => {
                if (typeof global.showBridgeToast === 'function') global.showBridgeToast('Action denied by user safety guardrail.', '#f87171');
                done(false, 'denied');
            };
            document.getElementById('apBtnOnce').onclick = () => done(true, 'once');
            document.getElementById('apBtnSession').onclick = () => {
                state.sessionAllowedCategories.add(category);
                if (typeof global.showBridgeToast === 'function') global.showBridgeToast(`Allowed ${category} control for this session.`, '#34d399');
                done(true, 'session');
            };
        });
    }

    function resetSessionPermissions() {
        state.sessionAllowedCategories.clear();
        if (typeof global.showBridgeToast === 'function') global.showBridgeToast('All session permissions reset to Ask-Every-Time.', '#fbbf24');
    }

    // =========================================================================
    // 2. AURA ULTRA 100-CAPABILITY COMMAND MATRIX UI
    // =========================================================================
    function _injectStyles() {
        if (document.getElementById('auraUltra100Styles')) return;
        const st = document.createElement('style');
        st.id = 'auraUltra100Styles';
        st.textContent = `
            #auraUltra100Overlay {
                position: fixed; inset: 0; z-index: 100040;
                background: rgba(3, 5, 10, 0.86); backdrop-filter: blur(22px);
                display: none; align-items: center; justify-content: center; padding: 18px;
                font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Inter', sans-serif);
            }
            #auraUltra100Overlay.open { display: flex; }
            .au100-shell {
                width: min(1180px, 100%); height: min(88vh, 840px);
                background: linear-gradient(160deg, #0e121c 0%, #07090e 100%);
                border: 1px solid rgba(248, 250, 252, 0.22); border-radius: 20px;
                box-shadow: 0 40px 120px rgba(0,0,0,0.9), 0 0 60px rgba(56,189,248,0.14);
                display: flex; flex-direction: column; overflow: hidden; color: #f8fafc;
            }
            .au100-head {
                padding: 18px 22px; border-bottom: 1px solid rgba(255,255,255,0.1);
                background: linear-gradient(90deg, rgba(56,189,248,0.1), rgba(248,250,252,0.04));
                display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap;
            }
            .au100-toolbar {
                padding: 12px 22px; border-bottom: 1px solid rgba(255,255,255,0.08);
                display: flex; flex-direction: column; gap: 10px; background: rgba(7,9,14,0.7);
            }
            .au100-pills { display: flex; gap: 6px; flex-wrap: wrap; }
            .au100-pill {
                height: 28px; padding: 0 11px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.12);
                background: rgba(255,255,255,0.04); color: #94a3b8; font-size: 11px; font-weight: 700;
                cursor: pointer; white-space: nowrap; transition: all 0.15s ease;
            }
            .au100-pill:hover { color: #ffffff; border-color: rgba(255,255,255,0.28); }
            .au100-pill.active { background: #f8fafc; color: #090b10; border-color: #f8fafc; }
            .au100-body {
                flex: 1; overflow-y: auto; padding: 18px 22px;
                display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px; align-content: start;
            }
            @media (max-width: 820px) { .au100-body { grid-template-columns: 1fr; } }
            .au100-card {
                padding: 13px 14px; border-radius: 13px; background: rgba(16, 20, 30, 0.84);
                border: 1px solid rgba(255,255,255,0.09); display: flex; flex-direction: column; gap: 7px;
                transition: border-color 0.16s ease, transform 0.16s ease;
            }
            .au100-card:hover { border-color: rgba(56,189,248,0.45); transform: translateY(-1px); }
            .au100-run-btn {
                height: 26px; padding: 0 11px; border-radius: 7px; border: 1px solid rgba(248,250,252,0.22);
                background: rgba(248,250,252,0.09); color: #ffffff; font-size: 11px; font-weight: 700;
                cursor: pointer; white-space: nowrap;
            }
            .au100-run-btn:hover { background: #f8fafc; color: #090b10; }
            .au100-out {
                padding: 10px 22px; border-top: 1px solid rgba(255,255,255,0.09);
                background: #090c12; font-family: var(--font-code, monospace); font-size: 11.5px;
                color: #6ee7b7; display: none; max-height: 110px; overflow-y: auto; white-space: pre-wrap;
            }
        `;
        document.head.appendChild(st);
    }

    function _mount() {
        if (state.mounted) return;
        _injectStyles();
        const ov = document.createElement('div');
        ov.id = 'auraUltra100Overlay';
        ov.setAttribute('role', 'dialog');
        ov.setAttribute('aria-modal', 'true');
        ov.setAttribute('aria-label', 'AURA Ultra — 100 Antigravity Capabilities');
        ov.onclick = (e) => { if (e.target === ov) close(); };
        ov.innerHTML = `
            <div class="au100-shell" onclick="event.stopPropagation()">
                <div class="au100-head">
                    <div>
                        <div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;">
                            <span style="font-size:17px;font-weight:800;letter-spacing:-0.02em;color:#ffffff;">AURA ULTRA · 100 Antigravity Capabilities</span>
                            <span id="au100StatusPill" style="font-family:var(--font-code,monospace);font-size:10.5px;font-weight:800;padding:3px 9px;border-radius:999px;background:rgba(56,189,248,0.16);border:1px solid rgba(56,189,248,0.45);color:#7dd3fc;">CHECKING...</span>
                        </div>
                        <div style="font-size:12px;color:#94a3b8;margin-top:3px;">10 Flagship Pillars × 10 Executable Powers — Live Browser, Screen Control (Ask-Permission), Full VS Code Work IDE, Self-Healing Memory, 4-Agent Swarm &amp; VOX Ultra.</div>
                    </div>
                    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                        <button type="button" class="au100-run-btn" onclick="AuraUltra100.launchBrowserWithPerm()">Live Browser</button>
                        <button type="button" class="au100-run-btn" onclick="AuraUltra100.launchScreenWithPerm()">Screen Control</button>
                        <button type="button" class="au100-run-btn" onclick="AuraUltra100.close()">Close</button>
                    </div>
                </div>
                <div class="au100-toolbar">
                    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                        <input id="au100Search" type="search" placeholder="Search all 100 Ultra Antigravity capabilities (e.g. browser, screen, permission, vs code, self-heal, swarm, voice)..." oninput="AuraUltra100.setSearch(this.value)" style="flex:1;min-width:240px;height:34px;background:#0a0d14;color:#f8fafc;border:1px solid rgba(255,255,255,0.14);border-radius:9px;padding:0 12px;font-size:12.5px;outline:none;">
                        <span id="au100MatchCount" style="font-family:var(--font-code,monospace);font-size:11.5px;color:#94a3b8;">100 / 100</span>
                    </div>
                    <div class="au100-pills" id="au100PillarPills"></div>
                </div>
                <div class="au100-body" id="au100Grid"></div>
                <div class="au100-out" id="au100OutputBar"></div>
            </div>
        `;
        document.body.appendChild(ov);
        state.mounted = true;
    }

    function _render() {
        const data = state.data;
        if (!data) return;
        const pill = document.getElementById('au100StatusPill');
        if (pill) {
            pill.textContent = state.unlocked ? '100 / 100 ULTRA ACTIVE' : 'PREVIEW · UNLOCK WITH AURA ULTRA ($149)';
            pill.style.color = state.unlocked ? '#6ee7b7' : '#fcd34d';
            pill.style.borderColor = state.unlocked ? 'rgba(52,211,153,0.48)' : 'rgba(251,191,36,0.48)';
            pill.style.background = state.unlocked ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)';
        }
        const pillsWrap = document.getElementById('au100PillarPills');
        if (pillsWrap) {
            const pBtns = [`<button type="button" class="au100-pill ${state.activePillar === 'all' ? 'active' : ''}" onclick="AuraUltra100.setPillar('all')">All 100</button>`];
            (data.pillars || []).forEach(p => {
                pBtns.push(`<button type="button" class="au100-pill ${state.activePillar === p.id ? 'active' : ''}" onclick="AuraUltra100.setPillar('${_esc(p.id)}')">${p.num}. ${_esc(p.title.split(' ')[0])} (${p.count})</button>`);
            });
            pillsWrap.innerHTML = pBtns.join('');
        }
        const q = state.search.trim().toLowerCase();
        const items = (data.capabilities || []).filter(c => {
            if (state.activePillar !== 'all' && c.pillar_id !== state.activePillar) return false;
            if (q && !(c.name + ' ' + c.description + ' ' + c.pillar_title + ' ' + c.id).toLowerCase().includes(q)) return false;
            return true;
        });
        const cntEl = document.getElementById('au100MatchCount');
        if (cntEl) cntEl.textContent = `${items.length} / ${data.total_count || 100} Capabilities`;
        const grid = document.getElementById('au100Grid');
        if (grid) {
            grid.innerHTML = items.map(c => `
                <div class="au100-card">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
                        <div style="min-width:0;">
                            <div style="font-family:var(--font-code,monospace);font-size:10px;color:${_esc(c.accent || '#38bdf8')};font-weight:700;letter-spacing:0.06em;">#${String(c.index).padStart(3, '0')} · PILLAR ${c.pillar_num} · ${_esc(c.pillar_title.toUpperCase())}</div>
                            <div style="font-size:13.5px;font-weight:700;color:#ffffff;margin-top:2px;">${_esc(c.name)}</div>
                        </div>
                        <button type="button" class="au100-run-btn" onclick="AuraUltra100.execute('${_esc(c.id)}', '${_esc(c.action)}')">${state.unlocked ? 'Launch →' : 'Unlock'}</button>
                    </div>
                    <div style="font-size:12px;color:#94a3b8;line-height:1.48;">${_esc(c.description)}</div>
                </div>
            `).join('');
        }
    }

    function _showOutput(msg, color) {
        const bar = document.getElementById('au100OutputBar');
        if (!bar) return;
        bar.style.display = 'block';
        bar.style.color = color || '#6ee7b7';
        bar.textContent = msg;
    }

    async function launchBrowserWithPerm() {
        const perm = await requestAuraActionPermission({
            category: 'live_browser',
            title: 'Allow AURA Live Browser Control?',
            action: 'Open Multi-Tab AI Browser & Autonomous DOM Controller',
            target: 'Isolated AURA Live Browser Workspace',
            risk: 'MEDIUM',
            forcePrompt: true,
        });
        if (!perm.allowed) return;
        close();
        if (typeof global.toggleAgentWorkspace === 'function') global.toggleAgentWorkspace('browser');
    }

    async function launchScreenWithPerm() {
        const perm = await requestAuraActionPermission({
            category: 'screen_control',
            title: 'Allow AURA Screen & Desktop Control?',
            action: 'Enable Live Screen Share / Computer Use with Human Take-Control & Kill Switch',
            target: 'Local Screen / Display Viewport',
            risk: 'HIGH',
            forcePrompt: true,
        });
        if (!perm.allowed) return;
        close();
        if (typeof global.toggleAgentWorkspace === 'function') global.toggleAgentWorkspace('computer');
    }

    async function execute(capId, action) {
        if (!state.unlocked) {
            close();
            if (typeof global.openModelSettings === 'function') global.openModelSettings('membership');
            if (typeof global.showBridgeToast === 'function') global.showBridgeToast('Activate an AURA Ultra ($149) key to unlock all 100 Antigravity powers!', '#38bdf8');
            return;
        }
        // UI surface actions dispatch immediately to real interactive engines!
        if (action === 'open_browser') { close(); if (typeof global.toggleAgentWorkspace === 'function') global.toggleAgentWorkspace('browser'); return; }
        if (action === 'open_computer') { close(); if (typeof global.toggleAgentWorkspace === 'function') global.toggleAgentWorkspace('computer'); return; }
        if (action === 'permission_demo_browser') { await launchBrowserWithPerm(); return; }
        if (action === 'permission_demo_screen') { await launchScreenWithPerm(); return; }
        if (action === 'open_work') { close(); if (typeof global.setAuraWorkspaceMode === 'function') global.setAuraWorkspaceMode('work'); return; }
        if (action === 'open_work_ext') { close(); if (global.AuraWorkIDE) { await global.AuraWorkIDE.open(); global.AuraWorkIDE.setRail('extensions'); } return; }
        if (action === 'open_work_memory') { close(); if (global.AuraWorkIDE) { await global.AuraWorkIDE.open(); global.AuraWorkIDE.setRail('memory'); } return; }
        if (action === 'open_studio') { close(); if (typeof global.openApexStudio === 'function') global.openApexStudio(); return; }
        if (action === 'open_vox_call') { close(); if (typeof global.openVoiceCallHud === 'function') global.openVoiceCallHud(true); return; }
        if (action === 'open_vox_console') { close(); if (typeof global.openJarvisConsole === 'function') global.openJarvisConsole(); return; }
        if (action === 'open_settings_appearance') { close(); if (typeof global.openModelSettings === 'function') global.openModelSettings('appearance'); return; }
        if (action === 'open_settings_voice') { close(); if (typeof global.openModelSettings === 'function') global.openModelSettings('voice'); return; }
        if (action === 'open_settings_security') { close(); if (typeof global.openModelSettings === 'function') global.openModelSettings('security'); return; }
        if (action === 'open_settings_memory') { close(); if (typeof global.openModelSettings === 'function') global.openModelSettings('memory'); return; }
        if (action === 'open_settings_reports') { close(); if (typeof global.openModelSettings === 'function') global.openModelSettings('reports'); return; }
        if (action === 'open_settings_membership') { close(); if (typeof global.openModelSettings === 'function') global.openModelSettings('membership'); return; }
        if (action === 'open_settings_ai') { close(); if (typeof global.openModelSettings === 'function') global.openModelSettings('ai'); return; }
        if (action === 'open_admin') { close(); if (typeof global.openAdminCommandCenter === 'function') global.openAdminCommandCenter('users'); return; }
        if (action === 'replay_intro') { close(); if (global.AuraCinematicIntro) global.AuraCinematicIntro.play({ username: (global.currentUser && global.currentUser.username) || 'Ultra Member' }); return; }
        if (action === 'switch_offline_20') { close(); if (typeof global.selectAuraModelTier === 'function') global.selectAuraModelTier('aura-2.0'); return; }
        if (action === 'open_remote') { global.open('/remote', '_blank', 'noopener'); return; }

        // Backend real execution via /api/ultra/execute
        _showOutput(`Executing ${capId} on AURA Ultra Flagship Engine...`, '#93c5fd');
        const { ok, data } = await _api('/api/ultra/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ capability_id: capId }),
        });
        if (ok && data && data.success) {
            _showOutput(`[${data.capability_name}] ✓ ${data.summary || JSON.stringify(data.result || {}).slice(0, 400)}`, '#6ee7b7');
        } else {
            _showOutput(`Error: ${(data && data.error) || 'Execution failed'}`, '#fca5a5');
        }
    }

    async function open(initialPillar) {
        _mount();
        state.activePillar = initialPillar || 'all';
        const ov = document.getElementById('auraUltra100Overlay');
        if (ov) ov.classList.add('open');
        state.open = true;
        const { ok, data } = await _api('/api/ultra/capabilities', { method: 'GET' });
        if (ok && data && data.success) {
            state.data = data;
            state.unlocked = Boolean(data.unlocked);
            _render();
        }
    }

    function close() {
        const ov = document.getElementById('auraUltra100Overlay');
        if (ov) ov.classList.remove('open');
        state.open = false;
    }

    function setPillar(pid) { state.activePillar = pid; _render(); }
    function setSearch(q) { state.search = String(q || ''); _render(); }

    global.requestAuraActionPermission = requestAuraActionPermission;
    global.AuraUltra100 = {
        open,
        close,
        setPillar,
        setSearch,
        execute,
        launchBrowserWithPerm,
        launchScreenWithPerm,
        requestPermission: requestAuraActionPermission,
        resetSessionPermissions,
    };
})(window);
