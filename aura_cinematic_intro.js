/**
 * ===================================================================================
 *   AURA BY LIBERTY — 60-SECOND RARE ANIMATED CINEMATIC LOGIN EXPERIENCE & SLIDES
 * ===================================================================================
 * Plays on login / registration (and replayable anytime from Settings):
 *  - 60-second (6 x 10s) real-time 60fps HTML5 Canvas motion-graphics choreography
 *    + verified 4K architectural/developer/automotive showcase photography slides.
 *  - Features AURA emblem assembly, Liberty company signature, VS Code Work IDE
 *    for developers, Self-Healing never-repeat-bug intelligence, VOX live voice,
 *    AURA 2.0 Offline chat, and the Plus / Pro / Ultra flagship showcase.
 *  - Crisp bottom Cinema Dock with Timeline, Play/Pause, Optional Ambient Audio,
 *    Back, Next (steps through every slide & photo), and Skip controls.
 * ===================================================================================
 */
(function (global) {
    'use strict';

    const CHAPTER_DURATION_MS = 10000; // 6 chapters x 10s = 60.0s total (1:00)

    const CHAPTERS = [
        {
            id: 'liberty_reveal',
            badge: 'LIBERTY PRESENTS · CHAPTER 01 / 06',
            title: 'AURA — Engineered by Liberty',
            subtitle: 'A rare autonomous AI platform crafted by Liberty for visionaries, creators, and elite software engineers.',
            accent: '#e5c17b',
            accentRgb: '229, 193, 123',
            photo: 'https://images.unsplash.com/photo-1614162692292-7ac56d7f7f1e?auto=format&fit=crop&w=1920&q=85',
            visualMode: 'crest',
            bullets: [
                'Crafted by Liberty Company with architectural precision',
                'Zero-clutter sovereign experience across PC & mobile',
                'Cryptographic scrypt lifetime login & isolated vaults',
            ],
        },
        {
            id: 'developers_ide',
            badge: 'BUILT FOR DEVELOPERS · CHAPTER 02 / 06',
            title: 'Full VS Code Work Engine — Zero Cost',
            subtitle: 'Switch from Chat to Work on any PC to launch Monaco VS Code, 32+ real extensions, live terminal, and instant localhost previews.',
            accent: '#60a5fa',
            accentRgb: '96, 165, 250',
            photo: 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=1920&q=85',
            visualMode: 'code',
            bullets: [
                'Real VS Code Monaco Editor + 32+ free extensions',
                'Build luxury websites, full-stack apps & 60fps games',
                'Watch AURA write files live with split localhost preview',
            ],
        },
        {
            id: 'self_healing',
            badge: 'ZERO-REPEAT INTELLIGENCE · CHAPTER 03 / 06',
            title: 'Self-Healing Code That Learns Forever',
            subtitle: 'When a bug strikes once, AURA diagnoses the exact line, patches it automatically, and memorizes a permanent rule so it never repeats.',
            accent: '#34d399',
            accentRgb: '52, 211, 153',
            photo: 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1920&q=85',
            visualMode: 'heal',
            bullets: [
                'Automated AST, JS, JSON & HTML integrity verification',
                'Persistent Mistake-Prevention Memory on every build',
                'First-time fixes stay 100% fixed on every future run',
            ],
        },
        {
            id: 'vox_and_browser',
            badge: 'REAL-TIME VOICE & CONTROL · CHAPTER 04 / 06',
            title: 'VOX Live Call & Autonomous Control',
            subtitle: 'Speak naturally with photorealistic acoustic glass visuals, ultra-low latency replies, and guarded live browser automation.',
            accent: '#a78bfa',
            accentRgb: '167, 139, 250',
            photo: 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1920&q=85',
            visualMode: 'vox',
            bullets: [
                'VOX optical glass live voice with 64-band audio spectrum',
                'Multiple executive neural voice personas on Pro & Ultra',
                'Live browser & computer-use verification guardrails',
            ],
        },
        {
            id: 'offline_and_4k',
            badge: 'ALWAYS READY · CHAPTER 05 / 06',
            title: 'AURA 2.0 Offline + 4K Living Studio',
            subtitle: 'Chat anytime on AURA 2.0 with zero Wi-Fi or mobile data — surrounded by 170+ Day/Night 4K photography wallpapers.',
            accent: '#38bdf8',
            accentRgb: '56, 189, 248',
            photo: 'https://images.unsplash.com/photo-1544636331-e26879cd4d9b?auto=format&fit=crop&w=1920&q=85',
            visualMode: 'offline',
            bullets: [
                'AURA 2.0 works 100% offline for simple chat at ₹0 cost',
                '170+ real 4K wallpapers: Supercars, Nature, Aesthetic, Kids & Dev',
                'Smart Day/Night 10-minute auto-cycle with permanent lock',
            ],
        },
        {
            id: 'three_tiers',
            badge: 'LIBERTY FLAGSHIP · CHAPTER 06 / 06',
            title: 'AURA Plus · AURA Pro · AURA Ultra',
            subtitle: 'Unlock radical luxury themes, +40% to Flagship Ultra brain upgrades, extra VOX voices, and Antigravity + Codex engineering power.',
            accent: '#f8fafc',
            accentRgb: '248, 250, 252',
            photo: 'https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=1920&q=85',
            visualMode: 'tiers',
            bullets: [
                'AURA Plus ($40) — +40% Brain & Champagne-Obsidian Luxury',
                'AURA Pro ($79) — +60% Beyond Plus & 6 VOX Neural Voices',
                'AURA Ultra ($149) — Antigravity + Codex + Unlimited Flagship',
            ],
        },
    ];

    const state = {
        mounted: false,
        open: false,
        playing: true,
        elapsedMs: 0,
        lastFrameTs: 0,
        rafId: 0,
        chapterIdx: 0,
        soundOn: false,
        audioCtx: null,
        audioNodes: null,
        particles: [],
        onFinish: null,
    };

    function _totalDurationMs() {
        return CHAPTERS.length * CHAPTER_DURATION_MS;
    }

    function _formatClock(ms) {
        const s = Math.max(0, Math.min(60, Math.floor(ms / 1000)));
        const m = Math.floor(s / 60);
        const rem = s % 60;
        return `${m}:${String(rem).padStart(2, '0')}`;
    }

    function _injectStyles() {
        if (document.getElementById('auraCinemaIntroStyles')) return;
        const st = document.createElement('style');
        st.id = 'auraCinemaIntroStyles';
        st.textContent = `
            #auraCinemaOverlay {
                position: fixed; inset: 0; z-index: 100050;
                background: #050609; color: #f8fafc;
                display: none; flex-direction: column; overflow: hidden;
                font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Inter', sans-serif);
            }
            #auraCinemaOverlay.open { display: flex; animation: acFadeIn 0.4s ease; }
            @keyframes acFadeIn { from { opacity: 0; } to { opacity: 1; } }
            .ac-photo-bg {
                position: absolute; inset: 0; background-size: cover; background-position: center;
                opacity: 0.26; transform: scale(1.06);
                transition: background-image 0.7s ease, opacity 0.6s ease, transform 9s linear;
                filter: saturate(1.08) contrast(1.08);
            }
            .ac-vignette {
                position: absolute; inset: 0; pointer-events: none;
                background: radial-gradient(circle at 50% 42%, rgba(7,9,14,0.34) 0%, rgba(5,6,9,0.88) 72%, rgba(4,5,8,0.97) 100%);
            }
            #acCanvas { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
            .ac-top {
                position: relative; z-index: 3; display: flex; align-items: center; justify-content: space-between;
                padding: 20px 28px;
            }
            .ac-liberty-pill {
                display: inline-flex; align-items: center; gap: 9px; padding: 6px 13px; border-radius: 999px;
                background: rgba(14,17,25,0.72); border: 1px solid rgba(255,255,255,0.14);
                backdrop-filter: blur(14px); font-size: 11px; font-weight: 700; letter-spacing: 0.14em;
                text-transform: uppercase; color: #e5c17b;
            }
            .ac-stage {
                position: relative; z-index: 3; flex: 1; display: grid;
                grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
                align-items: center; gap: 36px; padding: 0 48px; max-width: 1320px; width: 100%; margin: 0 auto; box-sizing: border-box;
            }
            @media (max-width: 900px) {
                .ac-stage { grid-template-columns: 1fr; padding: 0 22px; gap: 18px; align-content: center; }
                .ac-slide-frame { max-height: 220px !important; }
                .ac-title { font-size: 28px !important; }
            }
            .ac-eyebrow {
                font-family: var(--font-code, monospace); font-size: 11px; font-weight: 700;
                letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 12px;
            }
            .ac-title {
                margin: 0 0 14px; font-size: clamp(30px, 4.2vw, 52px); font-weight: 800;
                letter-spacing: -0.03em; line-height: 1.08; color: #ffffff;
            }
            .ac-sub {
                margin: 0 0 22px; font-size: clamp(14px, 1.35vw, 17px); line-height: 1.62; color: #cbd5e1; max-width: 580px;
            }
            .ac-bullets { display: flex; flex-direction: column; gap: 9px; }
            .ac-bullet {
                display: flex; align-items: center; gap: 10px; font-size: 13.5px; color: #e2e8f0;
                padding: 8px 12px; border-radius: 10px; background: rgba(15,19,29,0.68);
                border: 1px solid rgba(255,255,255,0.09); backdrop-filter: blur(12px);
            }
            .ac-slide-frame {
                position: relative; border-radius: 20px; overflow: hidden;
                border: 1px solid rgba(255,255,255,0.16); box-shadow: 0 32px 90px rgba(0,0,0,0.65);
                background: #0d1018; aspect-ratio: 16 / 10; max-height: 390px; width: 100%;
            }
            .ac-slide-frame img {
                width: 100%; height: 100%; object-fit: cover; display: block;
                transition: transform 6s ease, opacity 0.45s ease;
            }
            .ac-slide-caption {
                position: absolute; left: 0; right: 0; bottom: 0; padding: 14px 16px;
                background: linear-gradient(180deg, transparent, rgba(5,7,11,0.92));
                display: flex; align-items: center; justify-content: space-between; font-size: 11.5px;
                font-family: var(--font-code, monospace); color: #e2e8f0;
            }
            .ac-dock {
                position: relative; z-index: 4; padding: 16px 28px 22px;
                background: linear-gradient(180deg, transparent, rgba(5,6,9,0.95) 35%);
                display: flex; flex-direction: column; gap: 12px; max-width: 1320px; width: 100%; margin: 0 auto; box-sizing: border-box;
            }
            .ac-progress-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
            .ac-seg {
                height: 4px; border-radius: 999px; background: rgba(255,255,255,0.16); overflow: hidden; cursor: pointer;
            }
            .ac-seg-fill { height: 100%; width: 0%; background: #e5c17b; transition: width 0.08s linear; }
            .ac-controls { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
            .ac-btn {
                height: 38px; padding: 0 16px; border-radius: 11px; border: 1px solid rgba(255,255,255,0.16);
                background: rgba(18,22,32,0.82); color: #f8fafc; font-size: 12.5px; font-weight: 700;
                cursor: pointer; display: inline-flex; align-items: center; gap: 7px; backdrop-filter: blur(12px);
                transition: all 0.16s ease;
            }
            .ac-btn:hover { background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.3); }
            .ac-btn.primary {
                background: linear-gradient(135deg, #f3d79b, #d4a853); color: #090b10; border-color: transparent;
                padding: 0 22px;
            }
            .ac-btn.primary:hover { filter: brightness(1.07); }
        `;
        document.head.appendChild(st);
    }

    function _mountDom() {
        if (state.mounted) return;
        _injectStyles();
        const ov = document.createElement('div');
        ov.id = 'auraCinemaOverlay';
        ov.setAttribute('role', 'dialog');
        ov.setAttribute('aria-modal', 'true');
        ov.setAttribute('aria-label', 'AURA by Liberty — 1-Minute Premiere Showcase');
        ov.innerHTML = `
            <div class="ac-photo-bg" id="acPhotoBg"></div>
            <div class="ac-vignette"></div>
            <canvas id="acCanvas"></canvas>

            <div class="ac-top">
                <div class="ac-liberty-pill">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#e5c17b" stroke-width="2.2"><polygon points="12 2 20 7 20 17 12 22 4 17 4 7 12 2"/><circle cx="12" cy="12" r="3"/></svg>
                    <span>LIBERTY COMPANY · AURA PREMIERE</span>
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span id="acWelcomeUser" style="font-size:12px;color:#cbd5e1;font-weight:600;"></span>
                    <button type="button" class="ac-btn" style="height:32px;padding:0 12px;font-size:11.5px;" onclick="AuraCinematicIntro.skip()">Skip Intro ✕</button>
                </div>
            </div>

            <div class="ac-stage">
                <div>
                    <div class="ac-eyebrow" id="acEyebrow" style="color:#e5c17b;">LIBERTY PRESENTS · CHAPTER 01 / 06</div>
                    <h1 class="ac-title" id="acTitle">AURA — Engineered by Liberty</h1>
                    <p class="ac-sub" id="acSub"></p>
                    <div class="ac-bullets" id="acBullets"></div>
                </div>
                <div class="ac-slide-frame">
                    <img id="acSlideImg" alt="AURA Showcase Visual" />
                    <div class="ac-slide-caption">
                        <span id="acSlideTag">AURA · LIBERTY EDITION</span>
                        <span id="acSlideIdx">01 / 06</span>
                    </div>
                </div>
            </div>

            <div class="ac-dock">
                <div class="ac-progress-row" id="acSegRow">
                    ${CHAPTERS.map((_, i) => `<div class="ac-seg" onclick="AuraCinematicIntro.goTo(${i})" title="Chapter ${i + 1}"><div class="ac-seg-fill" id="acSegFill_${i}"></div></div>`).join('')}
                </div>
                <div class="ac-controls">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <button type="button" class="ac-btn" id="acPlayPauseBtn" onclick="AuraCinematicIntro.togglePlay()">Pause</button>
                        <button type="button" class="ac-btn" id="acSoundBtn" onclick="AuraCinematicIntro.toggleSound()">Sound: Off</button>
                        <span id="acClock" style="font-family:var(--font-code,monospace);font-size:12px;color:#94a3b8;margin-left:4px;">0:00 / 1:00</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <button type="button" class="ac-btn" onclick="AuraCinematicIntro.prev()">← Back</button>
                        <button type="button" class="ac-btn primary" id="acNextBtn" onclick="AuraCinematicIntro.next()">Next Slide →</button>
                        <button type="button" class="ac-btn" onclick="AuraCinematicIntro.skip()">Skip</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(ov);

        // Seed 140 luminous motion particles
        state.particles = [];
        for (let i = 0; i < 140; i++) {
            state.particles.push({
                x: Math.random(),
                y: Math.random(),
                vx: (Math.random() - 0.5) * 0.00055,
                vy: (Math.random() - 0.5) * 0.00055,
                r: 0.9 + Math.random() * 2.1,
                angle: (i / 140) * Math.PI * 2,
            });
        }
        state.mounted = true;
    }

    function _applyChapterUi(idx) {
        const ch = CHAPTERS[idx] || CHAPTERS[0];
        const bg = document.getElementById('acPhotoBg');
        const ey = document.getElementById('acEyebrow');
        const ti = document.getElementById('acTitle');
        const su = document.getElementById('acSub');
        const bu = document.getElementById('acBullets');
        const img = document.getElementById('acSlideImg');
        const tag = document.getElementById('acSlideTag');
        const si = document.getElementById('acSlideIdx');
        const nb = document.getElementById('acNextBtn');

        if (bg) bg.style.backgroundImage = `url('${ch.photo}')`;
        if (ey) { ey.textContent = ch.badge; ey.style.color = ch.accent; }
        if (ti) ti.textContent = ch.title;
        if (su) su.textContent = ch.subtitle;
        if (bu) {
            bu.innerHTML = ch.bullets.map(b =>
                `<div class="ac-bullet"><span style="width:7px;height:7px;border-radius:999px;background:${ch.accent};flex-shrink:0;box-shadow:0 0 12px ${ch.accent};"></span><span>${b}</span></div>`
            ).join('');
        }
        if (img) {
            img.style.opacity = '0.35';
            img.src = ch.photo;
            img.onload = () => { img.style.opacity = '1'; };
        }
        if (tag) tag.textContent = ch.title.toUpperCase();
        if (si) si.textContent = `0${idx + 1} / 0${CHAPTERS.length}`;
        if (nb) nb.textContent = idx === CHAPTERS.length - 1 ? 'Enter AURA Workspace →' : 'Next Slide →';
    }

    function _drawCanvas(ts) {
        const canvas = document.getElementById('acCanvas');
        if (!canvas) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const w = window.innerWidth;
        const h = window.innerHeight;
        if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
            canvas.width = Math.floor(w * dpr);
            canvas.height = Math.floor(h * dpr);
        }
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);

        const ch = CHAPTERS[state.chapterIdx] || CHAPTERS[0];
        const t = ts * 0.001;
        const cx = w * 0.5;
        const cy = h * 0.48;

        // Subtle sweeping anamorphic light beam
        const grad = ctx.createRadialGradient(
            cx + Math.cos(t * 0.45) * 180,
            cy + Math.sin(t * 0.35) * 90,
            10,
            cx,
            cy,
            Math.max(w, h) * 0.65
        );
        grad.addColorStop(0, `rgba(${ch.accentRgb}, 0.14)`);
        grad.addColorStop(1, 'rgba(5, 6, 9, 0)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);

        // Chapter-specific precision architectural motion graphics (zero cartoons!)
        ctx.save();
        ctx.strokeStyle = `rgba(${ch.accentRgb}, 0.22)`;
        ctx.lineWidth = 1.2;

        if (ch.visualMode === 'crest' || ch.visualMode === 'tiers') {
            // Rotating precision hexagonal AURA crest geometry
            for (let ring = 0; ring < 3; ring++) {
                const rad = 110 + ring * 52 + Math.sin(t * 1.4 + ring) * 6;
                ctx.beginPath();
                for (let k = 0; k <= 6; k++) {
                    const a = (k * Math.PI) / 3 + t * (ring % 2 === 0 ? 0.16 : -0.11);
                    const px = cx + Math.cos(a) * rad;
                    const py = cy + Math.sin(a) * rad;
                    if (k === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
                }
                ctx.stroke();
            }
        } else if (ch.visualMode === 'vox') {
            // Concentric acoustic wave rings
            for (let r = 0; r < 5; r++) {
                const rad = 70 + ((t * 55 + r * 48) % 240);
                const alpha = Math.max(0, 0.32 * (1 - rad / 310));
                ctx.strokeStyle = `rgba(${ch.accentRgb}, ${alpha.toFixed(3)})`;
                ctx.beginPath();
                ctx.arc(cx, cy, rad, 0, Math.PI * 2);
                ctx.stroke();
            }
        } else if (ch.visualMode === 'heal' || ch.visualMode === 'code') {
            // Precision architectural grid scanlines
            const step = 64;
            const offset = (t * 24) % step;
            ctx.strokeStyle = `rgba(${ch.accentRgb}, 0.07)`;
            for (let gx = offset; gx < w; gx += step) {
                ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, h); ctx.stroke();
            }
            for (let gy = offset; gy < h; gy += step) {
                ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(w, gy); ctx.stroke();
            }
        }
        ctx.restore();

        // Luminous drifting particle constellation
        for (let i = 0; i < state.particles.length; i++) {
            const p = state.particles[i];
            p.x = (p.x + p.vx + 1) % 1;
            p.y = (p.y + p.vy + 1) % 1;
            const px = p.x * w;
            const py = p.y * h;
            ctx.fillStyle = `rgba(${ch.accentRgb}, ${0.28 + 0.32 * Math.sin(t * 2 + i)})`;
            ctx.beginPath();
            ctx.arc(px, py, p.r, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    function _tick(ts) {
        if (!state.open) return;
        if (!state.lastFrameTs) state.lastFrameTs = ts;
        const dt = Math.min(100, ts - state.lastFrameTs);
        state.lastFrameTs = ts;

        if (state.playing) {
            state.elapsedMs += dt;
            if (state.elapsedMs >= _totalDurationMs()) {
                skip();
                return;
            }
        }

        const idx = Math.min(CHAPTERS.length - 1, Math.floor(state.elapsedMs / CHAPTER_DURATION_MS));
        if (idx !== state.chapterIdx) {
            state.chapterIdx = idx;
            _applyChapterUi(idx);
        }

        // Update 6-segment timeline fills
        for (let i = 0; i < CHAPTERS.length; i++) {
            const fill = document.getElementById('acSegFill_' + i);
            if (!fill) continue;
            const segStart = i * CHAPTER_DURATION_MS;
            const pct = Math.max(0, Math.min(100, ((state.elapsedMs - segStart) / CHAPTER_DURATION_MS) * 100));
            fill.style.width = pct.toFixed(1) + '%';
            fill.style.background = CHAPTERS[state.chapterIdx].accent;
        }
        const clk = document.getElementById('acClock');
        if (clk) clk.textContent = `${_formatClock(state.elapsedMs)} / 1:00`;

        _drawCanvas(ts);
        state.rafId = requestAnimationFrame(_tick);
    }

    function _stopSound() {
        try {
            if (state.audioNodes) {
                state.audioNodes.forEach(n => { try { n.stop(); } catch (_) {} });
                state.audioNodes = null;
            }
            if (state.audioCtx) {
                state.audioCtx.close().catch(() => {});
                state.audioCtx = null;
            }
        } catch (_) {}
        state.soundOn = false;
        const btn = document.getElementById('acSoundBtn');
        if (btn) btn.textContent = 'Sound: Off';
    }

    function toggleSound() {
        if (state.soundOn) {
            _stopSound();
            return;
        }
        try {
            const Ctx = global.AudioContext || global.webkitAudioContext;
            if (!Ctx) return;
            const ctx = new Ctx();
            const master = ctx.createGain();
            master.gain.value = 0.045;
            master.connect(ctx.destination);
            const freqs = [110, 164.81, 220, 329.63]; // Warm A-major cinematic ambient pad
            const nodes = freqs.map(f => {
                const osc = ctx.createOscillator();
                osc.type = 'sine';
                osc.frequency.value = f;
                osc.connect(master);
                osc.start();
                return osc;
            });
            state.audioCtx = ctx;
            state.audioNodes = nodes;
            state.soundOn = true;
            const btn = document.getElementById('acSoundBtn');
            if (btn) btn.textContent = 'Sound: On';
        } catch (_) {}
    }

    function play(opts) {
        _mountDom();
        state.elapsedMs = 0;
        state.chapterIdx = 0;
        state.playing = true;
        state.lastFrameTs = 0;
        state.onFinish = (opts && typeof opts.onFinish === 'function') ? opts.onFinish : null;

        const welcomeEl = document.getElementById('acWelcomeUser');
        const uname = (opts && opts.username) ? String(opts.username) : '';
        if (welcomeEl) welcomeEl.textContent = uname ? `Welcome, ${uname}` : '';

        const ppBtn = document.getElementById('acPlayPauseBtn');
        if (ppBtn) ppBtn.textContent = 'Pause';

        _applyChapterUi(0);
        const ov = document.getElementById('auraCinemaOverlay');
        if (ov) ov.classList.add('open');
        state.open = true;
        cancelAnimationFrame(state.rafId);
        state.rafId = requestAnimationFrame(_tick);
    }

    function goTo(idx) {
        const clamped = Math.max(0, Math.min(CHAPTERS.length - 1, Number(idx || 0)));
        state.chapterIdx = clamped;
        state.elapsedMs = clamped * CHAPTER_DURATION_MS + 10;
        _applyChapterUi(clamped);
    }

    function next() {
        if (state.chapterIdx >= CHAPTERS.length - 1) {
            skip();
            return;
        }
        goTo(state.chapterIdx + 1);
    }

    function prev() {
        goTo(Math.max(0, state.chapterIdx - 1));
    }

    function togglePlay() {
        state.playing = !state.playing;
        const ppBtn = document.getElementById('acPlayPauseBtn');
        if (ppBtn) ppBtn.textContent = state.playing ? 'Pause' : 'Play';
    }

    function skip() {
        state.open = false;
        state.playing = false;
        cancelAnimationFrame(state.rafId);
        _stopSound();
        const ov = document.getElementById('auraCinemaOverlay');
        if (ov) ov.classList.remove('open');
        if (typeof state.onFinish === 'function') {
            const cb = state.onFinish;
            state.onFinish = null;
            try { cb(); } catch (_) {}
        }
    }

    global.AuraCinematicIntro = {
        play,
        next,
        prev,
        goTo,
        togglePlay,
        toggleSound,
        skip,
        CHAPTERS,
    };
})(window);
