/**
 * ===================================================================================
 *   AURA 100 SCROLL-DRIVEN REALISTIC CINEMATIC WALLPAPER ENGINE
 *   50 Realistic Cyber / Hacker Command Worlds + 50 Realistic BMW / Automotive Worlds
 *   Zero cartoons · High-craft procedural optics · 8GB-RAM adaptive 30-60fps engine
 * ===================================================================================
 */
(function (global) {
    'use strict';

    // 10 Cyber/Hacker Realistic Optical Engines x 5 Graded Palettes = 50 Hacker Wallpapers
    const HACKER_ENGINES = [
        { engine: 'kernel_rain', base: 'Kernel Memory Rain', motion: 'Z-Depth Hex Stream' },
        { engine: 'threat_globe', base: 'Orbital Threat Globe', motion: 'Longitude & Packet Arcs' },
        { engine: 'fiber_grid', base: 'Optical Fiber Trunk', motion: 'Forward Tunnel Warp' },
        { engine: 'rf_spectrum', base: 'SDR Spectrum Analyzer', motion: 'RF Frequency Sweep' },
        { engine: 'sar_radar', base: 'SAR Topographic Radar', motion: 'Altitude & Sweep Scan' },
        { engine: 'pcb_wafer', base: 'Silicon Wafer Bus', motion: '45° Trace Propagation' },
        { engine: 'crypto_lattice', base: 'SHA-256 Neural Lattice', motion: '3D Camera Orbit' },
        { engine: 'orbital_hud', base: 'Azimuth Vernier HUD', motion: 'Counter-Spinning Rings' },
        { engine: 'lidar_city', base: 'LiDAR Recon Skyline', motion: 'Drone Parallax Pan' },
        { engine: 'datacenter_aisle', base: 'Cold-Aisle Server Rack', motion: 'Corridor Glide' },
    ];
    const HACKER_PALETTES = [
        { tag: 'Phosphor', p: '#10b981', s: '#34d399', bg: '#040907', g: 'rgba(16,185,129,0.22)' },
        { tag: 'Cobalt Ice', p: '#38bdf8', s: '#7aa2ff', bg: '#05080f', g: 'rgba(56,189,248,0.22)' },
        { tag: 'Red-Team', p: '#ef4444', s: '#f87171', bg: '#0b0507', g: 'rgba(239,68,68,0.20)' },
        { tag: 'Amber Core', p: '#f59e0b', s: '#fbbf24', bg: '#0b0804', g: 'rgba(245,158,11,0.20)' },
        { tag: 'Ghost Mono', p: '#cbd5e1', s: '#94a3b8', bg: '#07080a', g: 'rgba(203,213,225,0.18)' },
    ];

    // 10 Automotive / BMW Studio & Night-Drive Engines x 5 Real Paint/Lighting Finishes = 50 Auto Wallpapers
    const AUTO_ENGINES = [
        { engine: 'bmw_laser_drl', base: 'BMW M-Laser Studio', motion: 'Softbox & DRL Beam Sweep' },
        { engine: 'autobahn_tunnel', base: 'Autobahn Night Tunnel', motion: 'High-Speed Tunnel Warp' },
        { engine: 'aero_windtunnel', base: 'BMW Aero Wind-Tunnel', motion: 'Laminar CFD Streamlines' },
        { engine: 'forged_carbon', base: 'Forged Carbon Weave', motion: 'Anisotropic Specular Bar' },
        { engine: 'm_cockpit_hud', base: 'M-Track Cockpit HUD', motion: 'RPM Arc & Horizon Tilt' },
        { engine: 'wet_asphalt_oled', base: 'Midnight OLED Asphalt', motion: 'Rain Tarmac Reflections' },
        { engine: 'forged_wheel_brake', base: 'Forged Rim & Ceramic', motion: 'Rotational Wheel Spin' },
        { engine: 'circuit_elevation', base: 'Nordschleife Telemetry', motion: 'Apex Racing-Line Trace' },
        { engine: 'studio_lightbar', base: 'Showroom Light-Rig', motion: 'Overhead Studio Glide' },
        { engine: 'pitlane_laser', base: 'Motorsport Pit Laser', motion: 'Laser Alignment & Mist' },
    ];
    const AUTO_PALETTES = [
        { tag: 'Frozen Black', p: '#e2e8f0', s: '#7aa2ff', bg: '#06070a', g: 'rgba(122,162,255,0.22)' },
        { tag: 'M4 CSL Yellow', p: '#facc15', s: '#fde047', bg: '#090804', g: 'rgba(250,204,21,0.22)' },
        { tag: 'i8 Laser Blue', p: '#38bdf8', s: '#60a5fa', bg: '#040811', g: 'rgba(56,189,248,0.24)' },
        { tag: 'M-Crimson', p: '#f43f5e', s: '#fb7185', bg: '#0b0507', g: 'rgba(244,63,94,0.22)' },
        { tag: 'Dravit Titanium', p: '#cbd5e1', s: '#94a3b8', bg: '#08090c', g: 'rgba(226,232,240,0.20)' },
    ];

    const CATALOG = [
        {
            id: 'obsidian',
            name: 'Pure Obsidian (Static)',
            category: 'minimal',
            engine: 'none',
            motion: 'Minimal Matte',
            p: '#7aa2ff',
            s: '#93c5fd',
            bg: '#0b0c0e',
            g: 'rgba(122,162,255,0.12)',
            seed: 0,
        },
    ];

    let hIdx = 1;
    HACKER_ENGINES.forEach((eng, ei) => {
        HACKER_PALETTES.forEach((pal, pi) => {
            const num = String(hIdx).padStart(2, '0');
            CATALOG.push({
                id: `hacker_${num}`,
                name: `${eng.base} · ${pal.tag}`,
                shortName: `${pal.tag} ${eng.base.split(' ')[0]}`,
                category: 'hacker',
                engine: eng.engine,
                motion: eng.motion,
                p: pal.p,
                s: pal.s,
                bg: pal.bg,
                g: pal.g,
                seed: ei * 17 + pi * 31 + 11,
            });
            hIdx++;
        });
    });

    let aIdx = 1;
    AUTO_ENGINES.forEach((eng, ei) => {
        AUTO_PALETTES.forEach((pal, pi) => {
            const num = String(aIdx).padStart(2, '0');
            CATALOG.push({
                id: `auto_${num}`,
                name: `${eng.base} · ${pal.tag}`,
                shortName: `${pal.tag} ${eng.base.split(' ')[0]}`,
                category: 'auto',
                engine: eng.engine,
                motion: eng.motion,
                p: pal.p,
                s: pal.s,
                bg: pal.bg,
                g: pal.g,
                seed: ei * 23 + pi * 41 + 97,
            });
            aIdx++;
        });
    });

    // =========================================================================
    // NEW COLLECTION A: 25 MODIFIED HYPERCAR REEL WALLPAPERS (PURE MODIFIED!)
    // BMW · Ferrari · Pagani · Bugatti · Lamborghini · Porsche · Koenigsegg · McLaren · GT-R
    // EVERY car blinks its headlights dynamically on scroll & cycles RGB laser colors
    // AND animates its signature moving part (Headlights / Tyres / Rain Wipers / Exhaust / Aero Wing)
    // =========================================================================
    const MODCAR_SPECS = [
        // 5 Modified BMW Builds
        { name: 'BMW M4 CSL Widebody · RGB Strobe', brand: 'bmw', part: 'headlight_strobe', motion: 'RGB Blinking Laser DRL + Splitter', p: '#facc15', s: '#38bdf8', bg: '#050609' },
        { name: 'BMW M3 Touring Mansory · Rain Wipers', brand: 'bmw', part: 'wiper_rain', motion: 'Sweeping Wipers + RGB Rain Glare', p: '#38bdf8', s: '#f43f5e', bg: '#04070d' },
        { name: 'BMW M8 G-Power · Deep-Dish Forged Tyres', brand: 'bmw', part: 'forged_tyres', motion: 'Spinning Forged Rims + Blinking DRL', p: '#f43f5e', s: '#facc15', bg: '#080507' },
        { name: 'BMW E46 M3 GTR Liberty Walk · Flame Exhaust', brand: 'bmw', part: 'exhaust_flame', motion: 'Titanium Exhaust Pops + RGB Strobe', p: '#60a5fa', s: '#fb923c', bg: '#05060b' },
        { name: 'BMW M5 CS Matte Carbon · Active GT Wing', brand: 'bmw', part: 'aero_wing', motion: 'DRS Carbon Wing + RGB Laser Flash', p: '#10b981', s: '#facc15', bg: '#040807' },
        // 5 Modified Ferrari Builds
        { name: 'Ferrari SF90 XX Novitec · Fang Strobe', brand: 'ferrari', part: 'headlight_strobe', motion: 'RGB Blinking Fangs + Carbon Aero', p: '#f43f5e', s: '#facc15', bg: '#0a0406' },
        { name: 'Ferrari 812 Comp Carbon · Monsoon Wipers', brand: 'ferrari', part: 'wiper_rain', motion: 'Sweeping Glass Wipers + RGB Beams', p: '#fb7185', s: '#38bdf8', bg: '#080509' },
        { name: 'Ferrari LaFerrari Mansory · Ceramic Tyres', brand: 'ferrari', part: 'forged_tyres', motion: 'Glowing Brake Rotor + Wheel Spin', p: '#ef4444', s: '#fbbf24', bg: '#0a0505' },
        { name: 'Ferrari F40 LM Twin-Turbo · Titanium Flames', brand: 'ferrari', part: 'exhaust_flame', motion: 'Blue Flame Backfire + RGB Flash', p: '#fb923c', s: '#38bdf8', bg: '#090504' },
        { name: 'Ferrari 488 Pista Widebody · DRS Spoiler', brand: 'ferrari', part: 'aero_wing', motion: 'Active Carbon Wing + Color Shift', p: '#f43f5e', s: '#a855f7', bg: '#08040a' },
        // 5 Modified Pagani Builds
        { name: 'Pagani Zonda R Exposed Carbon · Quad RGB', brand: 'pagani', part: 'headlight_strobe', motion: 'Quad-Pod RGB Blink + Carbon Hood', p: '#38bdf8', s: '#facc15', bg: '#05070c' },
        { name: 'Pagani Huayra BC Tempesta · Rain Wipers', brand: 'pagani', part: 'wiper_rain', motion: 'Monsoon Wiper Sweep + Quad Beams', p: '#a855f7', s: '#38bdf8', bg: '#07050c' },
        { name: 'Pagani Utopia Track Spec · Forged Alloys', brand: 'pagani', part: 'forged_tyres', motion: 'Turbine Forged Wheel + RGB Pulse', p: '#facc15', s: '#fb7185', bg: '#090704' },
        { name: 'Pagani Zonda Cinque · Quad Titanium Flame', brand: 'pagani', part: 'exhaust_flame', motion: 'Quad Pipe Afterburner + RGB Blink', p: '#38bdf8', s: '#fb923c', bg: '#05070b' },
        { name: 'Pagani Huayra R Evo · Active Aero Flaps', brand: 'pagani', part: 'aero_wing', motion: 'Hydraulic Aero Flaps + RGB Flash', p: '#10b981', s: '#38bdf8', bg: '#040908' },
        // 5 Modified Bugatti Builds
        { name: 'Bugatti Chiron Pur Sport Carbon · 4-Dot RGB', brand: 'bugatti', part: 'headlight_strobe', motion: '4-Pixel RGB Flash + Carbon Grille', p: '#38bdf8', s: '#f8fafc', bg: '#04070e' },
        { name: 'Bugatti Bolide Track · Storm Wiper Glass', brand: 'bugatti', part: 'wiper_rain', motion: 'Aero Wiper Sweep + X-Laser Glow', p: '#60a5fa', s: '#f43f5e', bg: '#05060d' },
        { name: 'Bugatti Divo Stealth · Spinning Aero Tyres', brand: 'bugatti', part: 'forged_tyres', motion: 'Spinning Carbon Rim + RGB Halo', p: '#06b6d4', s: '#facc15', bg: '#04080c' },
        { name: 'Bugatti Tourbillon Mansory · Quad Flames', brand: 'bugatti', part: 'exhaust_flame', motion: 'Titanium Quad Flame + RGB Strobe', p: '#a855f7', s: '#fb923c', bg: '#07050c' },
        { name: 'Bugatti Veyron Super Sport WRE · Airbrake', brand: 'bugatti', part: 'aero_wing', motion: 'Hydraulic Airbrake Wing + RGB LED', p: '#fb923c', s: '#38bdf8', bg: '#090604' },
        // 5 Iconic Modified Hypercars
        { name: 'Lamborghini Revuelto Mansory · Y-Fang RGB', brand: 'hyper', part: 'headlight_strobe', motion: 'Y-Fang RGB Strobe + Stealth Nose', p: '#a855f7', s: '#facc15', bg: '#08050c' },
        { name: 'Porsche 911 GT3 RS Manthey · Rain Wipers', brand: 'hyper', part: 'wiper_rain', motion: 'Track Rain Wipers + Matrix RGB', p: '#10b981', s: '#38bdf8', bg: '#040807' },
        { name: 'Koenigsegg Jesko Absolut · Carbon Tyres', brand: 'hyper', part: 'forged_tyres', motion: 'Aircore Carbon Rim + RGB Flash', p: '#f8fafc', s: '#38bdf8', bg: '#06070a' },
        { name: 'Nissan R35 GT-R Nismo Widebody · Anti-Lag', brand: 'hyper', part: 'exhaust_flame', motion: 'Anti-Lag Titanium Flame + RGB DRL', p: '#f43f5e', s: '#38bdf8', bg: '#0a0507' },
        { name: 'McLaren P1 GTR Carbon · Swan-Neck DRS', brand: 'hyper', part: 'aero_wing', motion: 'Active Carbon DRS Wing + RGB Beam', p: '#facc15', s: '#fb923c', bg: '#090704' },
    ];

    MODCAR_SPECS.forEach((mc, idx) => {
        const num = String(idx + 1).padStart(2, '0');
        CATALOG.push({
            id: `modcar_${num}`,
            name: mc.name,
            shortName: mc.name.split('·')[0].trim(),
            category: 'modcars',
            engine: 'modcar_reel',
            brand: mc.brand,
            part: mc.part,
            motion: mc.motion,
            p: mc.p,
            s: mc.s,
            bg: mc.bg,
            g: _rgba(mc.p, 0.24),
            seed: idx * 37 + 303,
        });
    });

    // =========================================================================
    // NEW COLLECTION B: 25 REALISTIC CINEMATIC ENVIRONMENT WALLPAPERS
    // 5 Atmospheric Engines x 5 Graded Worlds = 25 Zero-Cartoon Environments
    // =========================================================================
    const ENV_SPECS = [
        // 5 Rainstorm & Wet City Reflection Worlds
        { engine: 'env_rain_storm', name: 'Tokyo Midnight Monsoon', motion: 'Slanted Rain + Puddle Ripples', p: '#38bdf8', s: '#f43f5e', bg: '#04070d' },
        { engine: 'env_rain_storm', name: 'Mumbai Marine Drive Storm', motion: 'Coastal Rain + Golden Bokeh', p: '#f59e0b', s: '#38bdf8', bg: '#07060a' },
        { engine: 'env_rain_storm', name: 'London Obsidian Fog Rain', motion: 'Heavy Downpour + Silver Mist', p: '#cbd5e1', s: '#60a5fa', bg: '#06070a' },
        { engine: 'env_rain_storm', name: 'Seoul Neon Rain Boulevard', motion: 'Neon Reflections + Storm Ripples', p: '#a855f7', s: '#ec4899', bg: '#07040c' },
        { engine: 'env_rain_storm', name: 'Emerald Rainforest Downpour', motion: 'Canopy Rain + Bioluminescent Mist', p: '#10b981', s: '#34d399', bg: '#030907' },
        // 5 Aurora Borealis & Polar Peak Worlds
        { engine: 'env_aurora_peaks', name: 'Iceland Black-Sand Aurora', motion: 'Shifting Emerald Borealis Curtains', p: '#10b981', s: '#38bdf8', bg: '#03080b' },
        { engine: 'env_aurora_peaks', name: 'Norway Fjord Mirror Sky', motion: 'Glacial Aurora + Water Reflection', p: '#2dd4bf', s: '#818cf8', bg: '#04070e' },
        { engine: 'env_aurora_peaks', name: 'Yukon Violet Borealis', motion: 'Violet Solar Ribbons + Peaks', p: '#a855f7', s: '#38bdf8', bg: '#06040d' },
        { engine: 'env_aurora_peaks', name: 'Arctic Glacial Blue Crown', motion: 'Polar Light Wave + Ice Horizon', p: '#38bdf8', s: '#e2e8f0', bg: '#040811' },
        { engine: 'env_aurora_peaks', name: 'Patagonia Crimson Aurora', motion: 'Solar Storm Sky + Ridge Shadow', p: '#f43f5e', s: '#a855f7', bg: '#0a0409' },
        // 5 Deep Ocean Abyss & Caustics Worlds
        { engine: 'env_abyss_ocean', name: 'Mariana Bioluminescent Trench', motion: 'Ocean Sun-Shafts + Glowing Spores', p: '#06b6d4', s: '#3b82f6', bg: '#02070e' },
        { engine: 'env_abyss_ocean', name: 'Pacific Midnight Caustics', motion: 'Underwater Light Caustics Drift', p: '#38bdf8', s: '#0ea5e9', bg: '#020812' },
        { engine: 'env_abyss_ocean', name: 'Arctic Sub-Ice Current', motion: 'Glacial Shafts + Deep Current', p: '#bae6fd', s: '#38bdf8', bg: '#030910' },
        { engine: 'env_abyss_ocean', name: 'Abyssal Emerald Lagoon', motion: 'Teal Water Rays + Rising Motes', p: '#14b8a6', s: '#34d399', bg: '#020a09' },
        { engine: 'env_abyss_ocean', name: 'Atlantic Moonlit Swell', motion: 'Silver Lunar Rays + Deep Tide', p: '#94a3b8', s: '#60a5fa', bg: '#04070c' },
        // 5 Volcanic Obsidian & Rising Ember Worlds
        { engine: 'env_volcanic_embers', name: 'Obsidian Basalt Caldera', motion: 'Rising Volcanic Embers + Glow', p: '#f97316', s: '#ef4444', bg: '#0a0504' },
        { engine: 'env_volcanic_embers', name: 'Mount Etna Night Magma', motion: 'Lava Fissure Pulse + Ash Drift', p: '#ef4444', s: '#fbbf24', bg: '#0c0404' },
        { engine: 'env_volcanic_embers', name: 'Fuji Obsidian Ash Horizon', motion: 'Crimson Sunset Ridge + Sparks', p: '#fb7185', s: '#f97316', bg: '#090507' },
        { engine: 'env_volcanic_embers', name: 'Golden Forge Valley', motion: 'Molten Gold Embers + Smoke', p: '#facc15', s: '#f97316', bg: '#090703' },
        { engine: 'env_volcanic_embers', name: 'Solar Eclipse Obsidian Ridge', motion: 'Corona Rim + Rising Embers', p: '#e2e8f0', s: '#f97316', bg: '#060506' },
        // 5 Alpine Mist, Desert Starfield & Cosmic Horizon Worlds
        { engine: 'env_mist_cosmos', name: 'Himalayan Milky Way Pass', motion: 'Parallax Peaks + Shooting Meteors', p: '#93c5fd', s: '#e2e8f0', bg: '#04060c' },
        { engine: 'env_mist_cosmos', name: 'Sahara Midnight Starfield', motion: 'Desert Dunes + Starlight Drift', p: '#fbbf24', s: '#93c5fd', bg: '#080604' },
        { engine: 'env_mist_cosmos', name: 'Misty Redwood Valley', motion: 'Gliding Silver Mist + Pines', p: '#6ee7b7', s: '#94a3b8', bg: '#040807' },
        { engine: 'env_mist_cosmos', name: 'Swiss Alpine Moonrise', motion: 'Lunar Halo + Rolling Valley Fog', p: '#cbd5e1', s: '#60a5fa', bg: '#05070b' },
        { engine: 'env_mist_cosmos', name: 'Atacama Nebula Horizon', motion: 'Deep-Space Band + Meteor Streaks', p: '#c084fc', s: '#38bdf8', bg: '#06040d' },
    ];

    ENV_SPECS.forEach((ev, idx) => {
        const num = String(idx + 1).padStart(2, '0');
        CATALOG.push({
            id: `env_${num}`,
            name: ev.name,
            shortName: ev.name.split(' ').slice(0, 2).join(' '),
            category: 'environment',
            engine: ev.engine,
            motion: ev.motion,
            p: ev.p,
            s: ev.s,
            bg: ev.bg,
            g: _rgba(ev.p, 0.22),
            seed: idx * 43 + 701,
        });
    });

    const RGB_LASER_SPECTRUM = ['#facc15', '#38bdf8', '#f43f5e', '#f8fafc', '#10b981', '#a855f7', '#fb923c'];

    function _lerpHex(hexA, hexB, f) {
        const a = _hexToRgb(hexA);
        const b = _hexToRgb(hexB);
        const t = Math.max(0, Math.min(1, f));
        const r = Math.round(a.r + (b.r - a.r) * t);
        const g = Math.round(a.g + (b.g - a.g) * t);
        const bl = Math.round(a.b + (b.b - a.b) * t);
        return `#${((1 << 24) + (r << 16) + (g << 8) + bl).toString(16).slice(1)}`;
    }

    function _scrollRgbColor(sc, seed) {
        const phase = Math.abs(sc * 1.45) + (seed % RGB_LASER_SPECTRUM.length);
        const i0 = Math.floor(phase) % RGB_LASER_SPECTRUM.length;
        const i1 = (i0 + 1) % RGB_LASER_SPECTRUM.length;
        return _lerpHex(RGB_LASER_SPECTRUM[i0], RGB_LASER_SPECTRUM[i1], phase - Math.floor(phase));
    }

    // Deterministic seeded PRNG so each of the 100 wallpapers has crisp, consistent structure
    function _rng(seed) {
        let s = (seed * 1664525 + 1013904223) >>> 0;
        return function () {
            s = (s * 1664525 + 1013904223) >>> 0;
            return s / 4294967296;
        };
    }

    function _hexToRgb(hex) {
        const clean = String(hex || '#7aa2ff').replace('#', '');
        const num = parseInt(clean.length === 3 ? clean.split('').map(c => c + c).join('') : clean, 16) || 0x7aa2ff;
        return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
    }

    function _rgba(hex, a) {
        const c = _hexToRgb(hex);
        return `rgba(${c.r},${c.g},${c.b},${Math.max(0, Math.min(1, a)).toFixed(3)})`;
    }

    // =========================================================================
    // 20 HIGH-CRAFT PROCEDURAL RENDERERS (10 HACKER + 10 AUTOMOTIVE/BMW)
    // Every single frame responds smoothly to `scroll` (scroll phase) + `vel`!
    // =========================================================================
    function renderWallpaperFrame(ctx, w, h, spec, t, scroll, vel, isPreview) {
        ctx.fillStyle = spec.bg || '#08090c';
        ctx.fillRect(0, 0, w, h);

        if (!spec || spec.engine === 'none') return;

        // Subtle optical ambient vignette
        const amb = ctx.createRadialGradient(w * 0.5, h * 0.35, w * 0.04, w * 0.5, h * 0.5, Math.max(w, h) * 0.78);
        amb.addColorStop(0, _rgba(spec.p, 0.14));
        amb.addColorStop(0.55, _rgba(spec.s, 0.04));
        amb.addColorStop(1, 'rgba(0,0,0,0.65)');
        ctx.fillStyle = amb;
        ctx.fillRect(0, 0, w, h);

        const eng = spec.engine;
        const sc = scroll;
        const speedBoost = 1 + Math.min(4, Math.abs(vel) * 1.8);
        const rnd = _rng(spec.seed || 7);

        // ---------------- CYBER / HACKER ENGINES (50 VARIANTS) ----------------
        if (eng === 'kernel_rain') {
            const cols = isPreview ? 14 : Math.min(46, Math.max(22, Math.floor(w / 32)));
            const tokens = ['0x7F', 'RAX', 'SYS', 'MOV', 'XOR', 'SHA', 'PTR', '0x4A', 'JMP', 'AES', '0xFF', 'TLS'];
            ctx.font = `${isPreview ? 8 : 11}px monospace`;
            for (let i = 0; i < cols; i++) {
                const depth = 0.35 + rnd() * 0.85;
                const x = ((i + 0.3) / cols) * w;
                const speed = (0.35 + rnd() * 0.7) * depth;
                const headY = (((t * 0.16 * speed + sc * 0.42 * depth + rnd() * 5) % 1.35) - 0.15) * h;
                const trail = isPreview ? 5 : 11;
                for (let k = 0; k < trail; k++) {
                    const y = headY - k * (isPreview ? 9 : 16) * depth;
                    if (y < -20 || y > h + 20) continue;
                    const alpha = Math.max(0, (1 - k / trail) * 0.72 * depth);
                    ctx.fillStyle = k === 0 ? _rgba('#ffffff', alpha * 0.95) : _rgba(spec.p, alpha);
                    const tok = tokens[(i * 7 + k * 3 + Math.floor(t * 2 + sc * 4)) % tokens.length];
                    ctx.fillText(tok, x, y);
                }
            }
            return;
        }

        if (eng === 'threat_globe') {
            const cx = w * 0.56;
            const cy = h * 0.52;
            const rad = Math.min(w, h) * (isPreview ? 0.38 : 0.34);
            const rot = t * 0.12 + sc * 0.95;
            const tilt = 0.28 + Math.sin(sc * 0.6) * 0.16;

            // Latitude rings
            ctx.lineWidth = isPreview ? 0.7 : 1;
            for (let lat = -60; lat <= 60; lat += 20) {
                const lr = (lat * Math.PI) / 180;
                const rLat = Math.cos(lr) * rad;
                const yLat = cy + Math.sin(lr) * rad * Math.cos(tilt);
                ctx.strokeStyle = _rgba(spec.p, 0.18);
                ctx.beginPath();
                ctx.ellipse(cx, yLat, rLat, Math.max(1, rLat * Math.sin(tilt)), 0, 0, Math.PI * 2);
                ctx.stroke();
            }
            // Longitude meridians
            for (let m = 0; m < 12; m++) {
                const ang = rot + (m / 12) * Math.PI;
                ctx.strokeStyle = _rgba(spec.p, 0.22);
                ctx.beginPath();
                ctx.ellipse(cx, cy, Math.abs(Math.cos(ang)) * rad, rad, 0, 0, Math.PI * 2);
                ctx.stroke();
            }
            // Outer atmospheric rim
            ctx.strokeStyle = _rgba(spec.s, 0.52);
            ctx.lineWidth = isPreview ? 1 : 1.4;
            ctx.beginPath();
            ctx.arc(cx, cy, rad, 0, Math.PI * 2);
            ctx.stroke();

            // Encrypted packet trajectories
            const arcs = isPreview ? 4 : 8;
            for (let a = 0; a < arcs; a++) {
                const a1 = rot + rnd() * Math.PI * 2;
                const a2 = rot + rnd() * Math.PI * 2;
                const p1x = cx + Math.cos(a1) * rad * 0.72;
                const p1y = cy + Math.sin(a1) * rad * 0.45;
                const p2x = cx + Math.cos(a2) * rad * 0.78;
                const p2y = cy + Math.sin(a2) * rad * 0.5;
                const mx = (p1x + p2x) * 0.5;
                const my = (p1y + p2y) * 0.5 - rad * 0.36;
                ctx.strokeStyle = _rgba(spec.s, 0.48);
                ctx.lineWidth = isPreview ? 0.9 : 1.25;
                ctx.beginPath();
                ctx.moveTo(p1x, p1y);
                ctx.quadraticCurveTo(mx, my, p2x, p2y);
                ctx.stroke();
                const prog = (t * 0.45 + sc * 0.8 + a * 0.19) % 1;
                const inv = 1 - prog;
                const bx = inv * inv * p1x + 2 * inv * prog * mx + prog * prog * p2x;
                const by = inv * inv * p1y + 2 * inv * prog * my + prog * prog * p2y;
                ctx.fillStyle = '#ffffff';
                ctx.beginPath();
                ctx.arc(bx, by, isPreview ? 1.5 : 2.5, 0, Math.PI * 2);
                ctx.fill();
            }
            return;
        }

        if (eng === 'fiber_grid') {
            const hz = h * (0.44 + Math.sin(sc * 0.45) * 0.04);
            const vpX = w * (0.5 + Math.sin(sc * 0.35) * 0.06);
            // Horizon optical glow
            const hg = ctx.createLinearGradient(0, hz - h * 0.14, 0, hz + h * 0.2);
            hg.addColorStop(0, 'rgba(0,0,0,0)');
            hg.addColorStop(0.45, _rgba(spec.p, 0.25));
            hg.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.fillStyle = hg;
            ctx.fillRect(0, hz - h * 0.14, w, h * 0.34);

            // Perspective longitudinal fiber lanes
            const lanes = isPreview ? 10 : 18;
            ctx.lineWidth = 1;
            for (let i = -lanes; i <= lanes; i++) {
                const bx = vpX + (i / lanes) * w * 1.45;
                ctx.strokeStyle = _rgba(spec.p, 0.22);
                ctx.beginPath();
                ctx.moveTo(vpX, hz);
                ctx.lineTo(bx, h);
                ctx.stroke();
            }
            // Scroll-driven depth cross-bars
            const rows = isPreview ? 10 : 18;
            const zOff = (t * 0.35 + sc * 1.15) % 1;
            for (let r = 0; r < rows; r++) {
                const f = Math.pow((r + zOff) / rows, 2.25);
                const y = hz + f * (h - hz);
                ctx.strokeStyle = _rgba(spec.s, 0.08 + f * 0.44);
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            }
            // Laser data packets zipping down center trunks
            for (let p = 0; p < (isPreview ? 4 : 9); p++) {
                const lane = (p - 4) * 0.16;
                const d = (t * 0.55 + sc * 1.3 + p * 0.23) % 1;
                const d2 = Math.min(1, d + 0.08);
                const f1 = d * d, f2 = d2 * d2;
                ctx.strokeStyle = _rgba('#ffffff', 0.72 * f2);
                ctx.lineWidth = isPreview ? 1 : 2;
                ctx.beginPath();
                ctx.moveTo(vpX + lane * w * f1, hz + (h - hz) * f1);
                ctx.lineTo(vpX + lane * w * f2, hz + (h - hz) * f2);
                ctx.stroke();
            }
            return;
        }

        if (eng === 'rf_spectrum') {
            // Calibrated dB grid
            ctx.strokeStyle = _rgba(spec.p, 0.10);
            ctx.lineWidth = 1;
            const gx = isPreview ? 6 : 12;
            const gy = isPreview ? 4 : 8;
            for (let i = 1; i < gx; i++) { ctx.beginPath(); ctx.moveTo((w / gx) * i, 0); ctx.lineTo((w / gx) * i, h); ctx.stroke(); }
            for (let j = 1; j < gy; j++) { ctx.beginPath(); ctx.moveTo(0, (h / gy) * j); ctx.lineTo(w, (h / gy) * j); ctx.stroke(); }
            // Multi-channel harmonic SDR waves reacting to scroll frequency sweep
            const waves = isPreview ? 3 : 5;
            for (let wv = 0; wv < waves; wv++) {
                const baseY = h * (0.28 + wv * 0.12);
                const amp = h * (0.045 + wv * 0.012);
                const freq = 0.012 + wv * 0.005;
                ctx.beginPath();
                const step = isPreview ? 4 : 6;
                for (let x = 0; x <= w; x += step) {
                    const phase = x * freq + t * (0.7 + wv * 0.2) + sc * (2.6 + wv * 0.9);
                    const carrier = Math.sin(phase) * Math.cos(phase * 0.37 - sc * 1.4);
                    const spike = Math.exp(-Math.pow(((x / w) - ((0.25 + wv * 0.16 + sc * 0.15) % 1 + 1) % 1) * 9, 2)) * amp * 1.8;
                    const y = baseY + carrier * amp - spike;
                    if (x === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.strokeStyle = _rgba(wv % 2 === 0 ? spec.p : spec.s, 0.35 + wv * 0.1);
                ctx.lineWidth = wv === waves - 1 ? 1.8 : 1.1;
                ctx.stroke();
            }
            return;
        }

        if (eng === 'sar_radar') {
            const cx = w * 0.55;
            const cy = h * 0.52;
            const maxR = Math.min(w, h) * 0.44;
            const sweep = t * 0.65 + sc * 2.1;
            // Topographic contour rings
            for (let k = 1; k <= 6; k++) {
                const r = (maxR * k) / 6;
                ctx.strokeStyle = _rgba(spec.p, 0.14 + (k === 6 ? 0.2 : 0));
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(cx, cy, r, 0, Math.PI * 2);
                ctx.stroke();
            }
            // Crosshair axes
            ctx.strokeStyle = _rgba(spec.p, 0.16);
            ctx.beginPath(); ctx.moveTo(cx - maxR, cy); ctx.lineTo(cx + maxR, cy); ctx.moveTo(cx, cy - maxR); ctx.lineTo(cx, cy + maxR); ctx.stroke();
            // Rotating radar phosphor cone
            for (let s = 0; s < 14; s++) {
                const a0 = sweep - s * 0.045;
                ctx.strokeStyle = _rgba(spec.p, (1 - s / 14) * 0.36);
                ctx.lineWidth = isPreview ? 1.5 : 2.5;
                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.lineTo(cx + Math.cos(a0) * maxR, cy + Math.sin(a0) * maxR);
                ctx.stroke();
            }
            // Target lock pings
            for (let b = 0; b < (isPreview ? 5 : 10); b++) {
                const ba = rnd() * Math.PI * 2;
                const br = (0.2 + rnd() * 0.72) * maxR;
                const diff = ((sweep - ba) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
                const glow = Math.max(0.12, 1 - diff / 2.6);
                const bx = cx + Math.cos(ba) * br;
                const by = cy + Math.sin(ba) * br;
                ctx.fillStyle = _rgba(spec.s, glow);
                ctx.beginPath();
                ctx.arc(bx, by, isPreview ? 1.5 : 2.6, 0, Math.PI * 2);
                ctx.fill();
            }
            return;
        }

        if (eng === 'pcb_wafer') {
            const count = isPreview ? 10 : 22;
            const pulsePos = (t * 0.35 + sc * 0.9) % 1;
            for (let i = 0; i < count; i++) {
                const y0 = ((i + 0.5) / count) * h;
                const bendX = w * (0.22 + rnd() * 0.45);
                const dy = (rnd() - 0.5) * (isPreview ? 26 : 80);
                ctx.strokeStyle = _rgba(spec.p, 0.20);
                ctx.lineWidth = isPreview ? 0.9 : 1.2;
                ctx.beginPath();
                ctx.moveTo(0, y0);
                ctx.lineTo(bendX, y0);
                ctx.lineTo(bendX + Math.abs(dy), y0 + dy);
                ctx.lineTo(w, y0 + dy);
                ctx.stroke();

                // Via pad
                ctx.fillStyle = _rgba(spec.s, 0.45);
                ctx.beginPath();
                ctx.arc(bendX, y0, isPreview ? 1.4 : 2.4, 0, Math.PI * 2);
                ctx.fill();

                // Traveling signal packet along bus
                const px = ((pulsePos + i * 0.13) % 1) * w;
                const py = px < bendX ? y0 : (px < bendX + Math.abs(dy) ? y0 + dy * ((px - bendX) / Math.max(1, Math.abs(dy))) : y0 + dy);
                ctx.fillStyle = '#ffffff';
                ctx.beginPath();
                ctx.arc(px, py, isPreview ? 1.2 : 2.2, 0, Math.PI * 2);
                ctx.fill();
            }
            return;
        }

        if (eng === 'crypto_lattice') {
            const pts = [];
            const n = isPreview ? 18 : 42;
            const angle = t * 0.1 + sc * 0.75;
            for (let i = 0; i < n; i++) {
                const rx = (rnd() - 0.5) * 2;
                const ry = (rnd() - 0.5) * 1.4;
                const rz = (rnd() - 0.5) * 2;
                const x3 = rx * Math.cos(angle) - rz * Math.sin(angle);
                const z3 = rx * Math.sin(angle) + rz * Math.cos(angle) + 2.8;
                const scale = 1.6 / Math.max(0.6, z3);
                pts.push({ x: w * 0.5 + x3 * w * 0.32 * scale, y: h * 0.5 + ry * h * 0.4 * scale, s: scale });
            }
            const maxDist = isPreview ? 46 : 145;
            ctx.lineWidth = 0.9;
            for (let i = 0; i < pts.length; i++) {
                for (let j = i + 1; j < pts.length; j++) {
                    const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y);
                    if (d < maxDist) {
                        ctx.strokeStyle = _rgba(spec.p, (1 - d / maxDist) * 0.34);
                        ctx.beginPath();
                        ctx.moveTo(pts[i].x, pts[i].y);
                        ctx.lineTo(pts[j].x, pts[j].y);
                        ctx.stroke();
                    }
                }
                ctx.fillStyle = _rgba(spec.s, Math.min(0.9, 0.35 + pts[i].s * 0.45));
                ctx.beginPath();
                ctx.arc(pts[i].x, pts[i].y, Math.max(1, pts[i].s * (isPreview ? 1.8 : 2.8)), 0, Math.PI * 2);
                ctx.fill();
            }
            return;
        }

        if (eng === 'orbital_hud') {
            const cx = w * 0.54, cy = h * 0.5;
            const baseR = Math.min(w, h) * 0.38;
            for (let r = 0; r < 5; r++) {
                const rad = baseR * (0.35 + r * 0.18);
                const dir = r % 2 === 0 ? 1 : -1;
                const rot = (t * 0.18 + sc * 1.15) * dir * (1 + r * 0.15);
                ctx.strokeStyle = _rgba(r % 2 === 0 ? spec.p : spec.s, 0.24 + r * 0.06);
                ctx.lineWidth = r === 3 ? 2 : 1;
                ctx.beginPath();
                ctx.arc(cx, cy, rad, rot, rot + Math.PI * (1.1 + r * 0.12));
                ctx.stroke();
                // Vernier tick marks
                const ticks = isPreview ? 16 : 36;
                for (let k = 0; k < ticks; k++) {
                    const a = rot + (k / ticks) * Math.PI * 2;
                    const len = k % 6 === 0 ? (isPreview ? 5 : 10) : (isPreview ? 2 : 4);
                    ctx.strokeStyle = _rgba(spec.p, 0.28);
                    ctx.beginPath();
                    ctx.moveTo(cx + Math.cos(a) * rad, cy + Math.sin(a) * rad);
                    ctx.lineTo(cx + Math.cos(a) * (rad + len), cy + Math.sin(a) * (rad + len));
                    ctx.stroke();
                }
            }
            return;
        }

        if (eng === 'lidar_city') {
            const pan = (t * 0.08 + sc * 0.45) * w;
            const bldgs = isPreview ? 12 : 24;
            const scanY = h * (0.2 + ((t * 0.22 + sc * 0.6) % 0.72));
            for (let i = 0; i < bldgs; i++) {
                const bw = (isPreview ? 14 : 46) + rnd() * (isPreview ? 16 : 58);
                const bh = h * (0.18 + rnd() * 0.52);
                const bx = (((i * (w / (bldgs * 0.65)) - pan * (0.4 + (i % 3) * 0.25)) % (w + bw * 2)) + (w + bw * 2)) % (w + bw * 2) - bw;
                const by = h - bh;
                ctx.strokeStyle = _rgba(spec.p, 0.22);
                ctx.lineWidth = 1;
                ctx.strokeRect(bx, by, bw, bh);
                // LiDAR point dots along floors
                const stepY = isPreview ? 7 : 12;
                const stepX = isPreview ? 6 : 11;
                for (let y = by + 4; y < h; y += stepY) {
                    const nearScan = Math.max(0, 1 - Math.abs(y - scanY) / (h * 0.14));
                    ctx.fillStyle = _rgba(nearScan > 0.3 ? '#ffffff' : spec.s, 0.14 + nearScan * 0.72);
                    for (let x = bx + 4; x < bx + bw - 3; x += stepX) {
                        ctx.fillRect(x, y, isPreview ? 1.3 : 2, isPreview ? 1.3 : 2);
                    }
                }
            }
            // Horizontal LiDAR laser sweep beam
            ctx.strokeStyle = _rgba(spec.p, 0.55);
            ctx.lineWidth = 1.4;
            ctx.beginPath(); ctx.moveTo(0, scanY); ctx.lineTo(w, scanY); ctx.stroke();
            return;
        }

        if (eng === 'datacenter_aisle') {
            const vpX = w * 0.5, vpY = h * 0.47;
            const racks = isPreview ? 7 : 12;
            const zOff = (t * 0.28 + sc * 0.95) % 1;
            for (let i = 0; i < racks; i++) {
                const f = Math.pow((i + zOff) / racks, 1.85);
                const halfW = w * 0.08 + f * w * 0.46;
                const halfH = h * 0.08 + f * h * 0.46;
                ctx.strokeStyle = _rgba(spec.p, 0.08 + f * 0.36);
                ctx.lineWidth = 1 + f;
                ctx.strokeRect(vpX - halfW, vpY - halfH, halfW * 2, halfH * 2);
                // Left & right server blade status LEDs
                const leds = isPreview ? 4 : 9;
                for (let l = 0; l < leds; l++) {
                    const ly = vpY - halfH + (l + 0.5) * ((halfH * 2) / leds);
                    const blink = ((Math.floor(t * 4 + i * 3 + l * 7 + sc * 5) % 5) === 0) ? 0.92 : 0.28;
                    ctx.fillStyle = _rgba(l % 3 === 0 ? spec.s : spec.p, blink * f);
                    const sz = Math.max(1.2, f * (isPreview ? 2.2 : 4.2));
                    ctx.fillRect(vpX - halfW + sz, ly, sz * 1.8, sz * 0.65);
                    ctx.fillRect(vpX + halfW - sz * 2.8, ly, sz * 1.8, sz * 0.65);
                }
            }
            return;
        }

        // ---------------- AUTOMOTIVE / BMW M-SERIES ENGINES (50 VARIANTS) ----------------
        if (eng === 'bmw_laser_drl') {
            const cx = w * 0.5;
            const cy = h * 0.54;
            const s = Math.min(w * 0.44, h * 0.62);
            const sweepNorm = Math.sin(t * 0.28 + sc * 1.15);
            const sweepX = cx + sweepNorm * w * 0.34;

            // Pitch-black studio cyclorama + moving overhead softbox light bar
            const soft = ctx.createRadialGradient(sweepX, h * 0.10, s * 0.04, sweepX, h * 0.28, s * 1.85);
            soft.addColorStop(0, _rgba('#ffffff', 0.14));
            soft.addColorStop(0.32, _rgba(spec.s, 0.08));
            soft.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.fillStyle = soft;
            ctx.fillRect(0, 0, w, h);

            // Sculpted gloss-black carbon hood silhouette & twin power-dome specular highlights
            const hoodG = ctx.createLinearGradient(cx - s * 1.15, cy - s * 0.32, cx + s * 1.15, cy - s * 0.14);
            hoodG.addColorStop(0, 'rgba(255,255,255,0)');
            hoodG.addColorStop(0.35 + sweepNorm * 0.12, _rgba('#ffffff', 0.18));
            hoodG.addColorStop(0.50 + sweepNorm * 0.12, _rgba(spec.s, 0.26));
            hoodG.addColorStop(0.68 + sweepNorm * 0.12, _rgba('#ffffff', 0.14));
            hoodG.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.strokeStyle = hoodG;
            ctx.lineWidth = isPreview ? 1.1 : 1.8;
            ctx.beginPath();
            ctx.moveTo(cx - s * 1.18, cy - s * 0.18);
            ctx.bezierCurveTo(cx - s * 0.52, cy - s * 0.40, cx + s * 0.52, cy - s * 0.40, cx + s * 1.18, cy - s * 0.18);
            ctx.stroke();

            // Twin sculpted hood power-dome specular creases
            ctx.strokeStyle = _rgba('#ffffff', 0.085);
            ctx.lineWidth = isPreview ? 0.8 : 1.2;
            [-1, 1].forEach((side) => {
                ctx.beginPath();
                ctx.moveTo(cx + side * s * 0.24, cy - s * 0.36);
                ctx.quadraticCurveTo(cx + side * s * 0.36, cy - s * 0.23, cx + side * s * 0.46, cy - s * 0.12);
                ctx.stroke();
            });

            // Subtle BMW Iconic Glow recessed double kidney grille (soft rim light veiled in dark studio shadow)
            const gw = s * 0.22, gh = s * 0.21, gGap = s * 0.026;
            const grilleAlpha = 0.24 + Math.abs(Math.sin(sc * 1.1 + t * 0.25)) * 0.16;
            [-1, 1].forEach((side) => {
                const gx0 = cx + side * gGap;
                const gx1 = cx + side * (gGap + gw);
                const gyT = cy - gh * 0.34;
                const gyB = cy + gh * 0.52;
                ctx.save();
                ctx.beginPath();
                ctx.moveTo(gx0, gyT + gh * 0.06);
                ctx.bezierCurveTo(gx0 + side * gw * 0.32, gyT - gh * 0.10, gx1 - side * gw * 0.15, gyT - gh * 0.02, gx1, gyT + gh * 0.18);
                ctx.bezierCurveTo(gx1 + side * gw * 0.04, cy + gh * 0.16, gx1 - side * gw * 0.08, gyB - gh * 0.06, gx1 - side * gw * 0.24, gyB);
                ctx.bezierCurveTo(gx0 + side * gw * 0.34, gyB + gh * 0.05, gx0 + side * gw * 0.04, gyB + gh * 0.02, gx0, gyB - gh * 0.06);
                ctx.closePath();

                // Dark recessed obsidian interior
                ctx.fillStyle = 'rgba(3,4,7,0.88)';
                ctx.fill();
                // Subtle brushed horizontal/vertical M-slat shadows
                ctx.clip();
                ctx.strokeStyle = _rgba('#ffffff', 0.055);
                ctx.lineWidth = isPreview ? 0.7 : 1.1;
                for (let sl = 1; sl <= 5; sl++) {
                    const sy = gyT + (gh * 0.88 * sl) / 6;
                    ctx.beginPath(); ctx.moveTo(gx0, sy); ctx.lineTo(gx1, sy); ctx.stroke();
                }
                ctx.restore();

                // Feathered Iconic Glow outer contour
                const gGrad = ctx.createLinearGradient(gx0, gyT, gx1, gyB);
                gGrad.addColorStop(0, _rgba(spec.p, grilleAlpha));
                gGrad.addColorStop(0.55, _rgba(spec.s, grilleAlpha * 0.45));
                gGrad.addColorStop(1, _rgba(spec.p, grilleAlpha * 0.15));
                ctx.strokeStyle = gGrad;
                ctx.lineWidth = isPreview ? 1 : 1.5;
                ctx.beginPath();
                ctx.moveTo(gx0, gyT + gh * 0.06);
                ctx.bezierCurveTo(gx0 + side * gw * 0.32, gyT - gh * 0.10, gx1 - side * gw * 0.15, gyT - gh * 0.02, gx1, gyT + gh * 0.18);
                ctx.bezierCurveTo(gx1 + side * gw * 0.04, cy + gh * 0.16, gx1 - side * gw * 0.08, gyB - gh * 0.06, gx1 - side * gw * 0.24, gyB);
                ctx.bezierCurveTo(gx0 + side * gw * 0.34, gyB + gh * 0.05, gx0 + side * gw * 0.04, gyB + gh * 0.02, gx0, gyB - gh * 0.06);
                ctx.closePath();
                ctx.stroke();
            });

            // Photorealistic BMW M-Series Twin Laser DRL Optics (Left & Right) + Anamorphic Lens Flare
            const beamIntensity = 0.78 + Math.abs(Math.sin(sc * 1.25 + t * 0.3)) * 0.22;
            const drawHeadlight = (side) => {
                const ex = cx + side * s * 0.68;
                const ey = cy - s * 0.01;

                // 1. Wide atmospheric volumetric laser halo
                const halo = ctx.createRadialGradient(ex, ey, 1, ex, ey, s * 0.52);
                halo.addColorStop(0, _rgba(spec.p, 0.42 * beamIntensity));
                halo.addColorStop(0.32, _rgba(spec.s, 0.16 * beamIntensity));
                halo.addColorStop(0.7, _rgba(spec.p, 0.04 * beamIntensity));
                halo.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = halo;
                ctx.beginPath(); ctx.arc(ex, ey, s * 0.52, 0, Math.PI * 2); ctx.fill();

                // 2. Cinema anamorphic horizontal optical streak
                if (!isPreview) {
                    const streak = ctx.createLinearGradient(ex - s * 0.55, ey, ex + s * 0.55, ey);
                    streak.addColorStop(0, 'rgba(0,0,0,0)');
                    streak.addColorStop(0.38, _rgba(spec.p, 0.14 * beamIntensity));
                    streak.addColorStop(0.5, _rgba('#ffffff', 0.32 * beamIntensity));
                    streak.addColorStop(0.62, _rgba(spec.p, 0.14 * beamIntensity));
                    streak.addColorStop(1, 'rgba(0,0,0,0)');
                    ctx.fillStyle = streak;
                    ctx.fillRect(ex - s * 0.55, ey - 1.5, s * 1.1, 3);
                }

                // 3. Predatory BMW M4 CSL / M8 Laserlight sculpted hexagonal L-blades (razor-sleek low-profile geometry)
                const traceBlade = (ox, oy, scaleX, scaleY) => {
                    ctx.beginPath();
                    ctx.moveTo(ox - side * s * 0.105 * scaleX, oy - s * 0.044 * scaleY);
                    ctx.lineTo(ox - side * s * 0.072 * scaleX, oy + s * 0.028 * scaleY);
                    ctx.quadraticCurveTo(
                        ox - side * s * 0.058 * scaleX, oy + s * 0.036 * scaleY,
                        ox - side * s * 0.036 * scaleX, oy + s * 0.036 * scaleY
                    );
                    ctx.lineTo(ox + side * s * 0.068 * scaleX, oy + s * 0.026 * scaleY);
                    ctx.quadraticCurveTo(
                        ox + side * s * 0.088 * scaleX, oy + s * 0.022 * scaleY,
                        ox + side * s * 0.098 * scaleX, oy + s * 0.004 * scaleY
                    );
                    ctx.lineTo(ox + side * s * 0.122 * scaleX, oy - s * 0.038 * scaleY);
                };

                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
                for (let k = 0; k < 2; k++) {
                    const ox = ex + side * (k === 0 ? -s * 0.135 : s * 0.115);
                    const oy = ey + (k === 0 ? s * 0.010 : -s * 0.014);
                    const sx = k === 0 ? 0.90 : 1.08;
                    const sy = k === 0 ? 0.88 : 1.02;

                    // Soft colored fiber-optic outer glow pass
                    ctx.strokeStyle = _rgba(spec.p, 0.58 * beamIntensity);
                    ctx.lineWidth = isPreview ? 3.2 : 6.8;
                    traceBlade(ox, oy, sx, sy);
                    ctx.stroke();

                    // Mid-core tinted luminance
                    ctx.strokeStyle = _rgba(spec.s, 0.85 * beamIntensity);
                    ctx.lineWidth = isPreview ? 1.9 : 3.4;
                    traceBlade(ox, oy, sx, sy);
                    ctx.stroke();

                    // Razor-sharp pure-white laser core filament
                    ctx.strokeStyle = _rgba('#ffffff', 0.96);
                    ctx.lineWidth = isPreview ? 1.0 : 1.8;
                    traceBlade(ox, oy, sx, sy);
                    ctx.stroke();
                }

                // 4. Wet black-epoxy studio floor elliptical reflection directly beneath headlight (ZERO hard edges!)
                ctx.save();
                const refY = cy + s * 0.36;
                ctx.translate(ex, refY);
                ctx.scale(1.0, 0.24);
                const fRef = ctx.createRadialGradient(0, 0, 2, 0, 0, s * 0.54);
                fRef.addColorStop(0, _rgba(spec.p, 0.30 * beamIntensity));
                fRef.addColorStop(0.45, _rgba(spec.s, 0.11 * beamIntensity));
                fRef.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = fRef;
                ctx.beginPath();
                ctx.arc(0, 0, s * 0.54, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            };
            drawHeadlight(-1);
            drawHeadlight(1);

            // Subtle wet-floor horizon whisper line
            const horG = ctx.createLinearGradient(cx - s * 1.4, cy + s * 0.33, cx + s * 1.4, cy + s * 0.33);
            horG.addColorStop(0, 'rgba(0,0,0,0)');
            horG.addColorStop(0.5, _rgba(spec.p, 0.16));
            horG.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.strokeStyle = horG;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(cx - s * 1.4, cy + s * 0.33);
            ctx.lineTo(cx + s * 1.4, cy + s * 0.33);
            ctx.stroke();
            return;
        }

        if (eng === 'autobahn_tunnel') {
            const vpX = w * (0.5 + Math.sin(sc * 0.4) * 0.05);
            const vpY = h * 0.49;
            const arches = isPreview ? 8 : 14;
            const zOff = (t * 0.55 + sc * 1.85) % 1;
            for (let i = 0; i < arches; i++) {
                const f = Math.pow((i + zOff) / arches, 2.2);
                const rx = w * 0.06 + f * w * 0.62;
                const ry = h * 0.06 + f * h * 0.56;
                ctx.strokeStyle = _rgba(spec.p, 0.06 + f * 0.52);
                ctx.lineWidth = Math.max(1, f * (isPreview ? 2.2 : 4.2));
                ctx.beginPath();
                ctx.ellipse(vpX, vpY, rx, ry, 0, Math.PI * 1.05, Math.PI * 1.95);
                ctx.stroke();
                // Wet floor reflection streak of tunnel arch
                ctx.strokeStyle = _rgba(spec.s, f * 0.22);
                ctx.lineWidth = Math.max(1, f * 2);
                ctx.beginPath();
                ctx.moveTo(vpX - rx * 0.55, vpY + ry * 0.72);
                ctx.lineTo(vpX + rx * 0.55, vpY + ry * 0.72);
                ctx.stroke();
            }
            // High-speed radial motion light streaks
            const streaks = isPreview ? 10 : 22;
            for (let k = 0; k < streaks; k++) {
                const ang = (k / streaks) * Math.PI * 2;
                const d1 = ((t * 0.7 + sc * 2.1 + rnd()) % 1);
                const d2 = Math.min(1, d1 + 0.12 * speedBoost);
                const r1 = d1 * d1 * Math.max(w, h) * 0.7;
                const r2 = d2 * d2 * Math.max(w, h) * 0.7;
                ctx.strokeStyle = _rgba(k % 3 === 0 ? '#ffffff' : spec.s, d2 * 0.55);
                ctx.lineWidth = isPreview ? 1 : 1.7;
                ctx.beginPath();
                ctx.moveTo(vpX + Math.cos(ang) * r1, vpY + Math.sin(ang) * r1);
                ctx.lineTo(vpX + Math.cos(ang) * r2, vpY + Math.sin(ang) * r2);
                ctx.stroke();
            }
            return;
        }

        if (eng === 'aero_windtunnel') {
            // Pure C-infinity smooth fastback BMW M coupe aerodynamic envelope (zero vertical step cliffs!)
            const baseLine = h * 0.72;
            const flow = t * 1.45 + sc * 4.4;
            const profileY = (nx) => {
                const hood = Math.exp(-Math.pow((nx - 0.30) / 0.145, 2)) * 0.095;
                const cabin = Math.exp(-Math.pow((nx - 0.53) / 0.165, 2)) * 0.225;
                const deck = Math.exp(-Math.pow((nx - 0.74) / 0.105, 2)) * 0.075;
                return baseLine - h * (hood + cabin + deck);
            };

            // Subtle dark wind-tunnel chamber floor reflection sheen
            const flG = ctx.createLinearGradient(0, baseLine, 0, h);
            flG.addColorStop(0, _rgba(spec.p, 0.14));
            flG.addColorStop(0.55, _rgba(spec.s, 0.04));
            flG.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.fillStyle = flG;
            ctx.fillRect(0, baseLine, w, h - baseLine);

            // Pitch-black sculpted fastback volume underneath the roofline so streamlines wrap around real mass
            ctx.beginPath();
            ctx.moveTo(0, baseLine);
            const bodyStep = isPreview ? 5 : 6;
            for (let x = 0; x <= w; x += bodyStep) {
                ctx.lineTo(x, profileY(x / w));
            }
            ctx.lineTo(w, baseLine);
            ctx.closePath();
            const bodyFill = ctx.createLinearGradient(0, baseLine - h * 0.34, 0, baseLine);
            bodyFill.addColorStop(0, _rgba(spec.s, 0.12));
            bodyFill.addColorStop(0.35, 'rgba(5,7,11,0.92)');
            bodyFill.addColorStop(1, 'rgba(2,3,5,0.98)');
            ctx.fillStyle = bodyFill;
            ctx.fill();

            // Silky laminar multi-pass wind-tunnel smoke streamlines gliding cleanly across entire viewport
            const ribbons = isPreview ? 10 : 18;
            for (let r = 0; r < ribbons; r++) {
                const ratio = r / (ribbons - 1);
                const lift = (r + 1) * (h * 0.026);
                const step = isPreview ? 6 : 8;
                const traceRibbon = () => {
                    ctx.beginPath();
                    for (let x = 0; x <= w; x += step) {
                        const nx = x / w;
                        const env = baseLine - profileY(nx); // smooth displacement >= 0
                        const bodyInfl = Math.exp(-ratio * 2.15);
                        const wakeEnv = Math.exp(-Math.pow((nx - 0.88) / 0.16, 2));
                        const wakeWave = Math.sin(x * 0.032 - flow + r * 0.45) * wakeEnv * h * 0.016 * (1 - ratio * 0.5);
                        const drift = Math.sin(x * 0.010 - flow * 0.65 + r * 0.35) * 1.8;
                        const y = baseLine - lift - env * (0.28 + 0.72 * bodyInfl) + wakeWave + drift;
                        if (x === 0) ctx.moveTo(x, y);
                        else ctx.lineTo(x, y);
                    }
                };
                // Soft volumetric smoke ribbon glow
                if (!isPreview && r < 8) {
                    ctx.strokeStyle = _rgba(r < 3 ? spec.p : spec.s, 0.12 * (1 - ratio * 0.6));
                    ctx.lineWidth = 4.6 - r * 0.35;
                    traceRibbon();
                    ctx.stroke();
                }
                // Crisp laminar smoke core
                const coreAlpha = r < 4 ? (0.72 - r * 0.09) : (0.34 - ratio * 0.18);
                ctx.strokeStyle = _rgba(r < 2 ? '#ffffff' : (r % 2 === 0 ? spec.p : spec.s), Math.max(0.08, coreAlpha));
                ctx.lineWidth = r < 3 ? (isPreview ? 1.15 : 1.55) : (isPreview ? 0.7 : 0.95);
                traceRibbon();
                ctx.stroke();
            }

            // Razor-crisp metallic rim-light along the sculpted coupe roofline (feathered at edges)
            const rimG = ctx.createLinearGradient(w * 0.12, 0, w * 0.88, 0);
            rimG.addColorStop(0, 'rgba(0,0,0,0)');
            rimG.addColorStop(0.24, _rgba(spec.p, 0.65));
            rimG.addColorStop(0.52, _rgba('#ffffff', 0.88));
            rimG.addColorStop(0.78, _rgba(spec.s, 0.58));
            rimG.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.beginPath();
            for (let x = w * 0.10; x <= w * 0.90; x += 5) {
                const y = profileY(x / w);
                if (x === w * 0.10) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.strokeStyle = rimG;
            ctx.lineWidth = isPreview ? 1.2 : 2.1;
            ctx.stroke();
            return;
        }

        if (eng === 'forged_carbon') {
            const tile = isPreview ? 8 : 14;
            const lightPos = ((Math.sin(t * 0.32 + sc * 1.1) * 0.5 + 0.5) * (w + h));
            for (let y = 0; y < h; y += tile) {
                for (let x = 0; x < w; x += tile) {
                    const diag = x + y;
                    const sheen = Math.exp(-Math.pow((diag - lightPos) / (Math.max(w, h) * 0.24), 2));
                    const alt = ((Math.floor(x / tile) + Math.floor(y / tile)) & 1) === 0;
                    const baseA = alt ? 0.06 : 0.025;
                    ctx.fillStyle = _rgba(alt ? spec.p : spec.s, baseA + sheen * (alt ? 0.24 : 0.11));
                    ctx.fillRect(x, y, tile - 1, tile - 1);
                }
            }
            return;
        }

        if (eng === 'm_cockpit_hud') {
            const cx = w * 0.5, cy = h * 0.56;
            const rad = Math.min(w, h) * 0.38;
            const rpm = 0.28 + ((Math.sin(t * 0.5 + sc * 1.65) * 0.5 + 0.5) * 0.62);
            const startA = Math.PI * 0.82;
            const endA = Math.PI * 2.18;
            const curA = startA + (endA - startA) * rpm;

            // Outer dark track arc
            ctx.strokeStyle = _rgba('#ffffff', 0.12);
            ctx.lineWidth = isPreview ? 4 : 8;
            ctx.beginPath(); ctx.arc(cx, cy, rad, startA, endA); ctx.stroke();

            // Active luminous RPM power arc
            ctx.strokeStyle = _rgba(spec.p, 0.82);
            ctx.lineWidth = isPreview ? 4 : 8;
            ctx.beginPath(); ctx.arc(cx, cy, rad, startA, curA); ctx.stroke();

            // Calibrated RPM ticks
            const ticks = isPreview ? 16 : 32;
            for (let i = 0; i <= ticks; i++) {
                const a = startA + ((endA - startA) * i) / ticks;
                const active = a <= curA;
                const inner = rad - (i % 4 === 0 ? (isPreview ? 9 : 18) : (isPreview ? 5 : 10));
                ctx.strokeStyle = active ? _rgba(i > ticks * 0.82 ? '#f43f5e' : '#ffffff', 0.85) : _rgba('#ffffff', 0.18);
                ctx.lineWidth = i % 4 === 0 ? 1.8 : 1;
                ctx.beginPath();
                ctx.moveTo(cx + Math.cos(a) * inner, cy + Math.sin(a) * inner);
                ctx.lineTo(cx + Math.cos(a) * (rad - 3), cy + Math.sin(a) * (rad - 3));
                ctx.stroke();
            }
            // Horizon pitch bar
            const tilt = Math.sin(sc * 0.8) * 0.12;
            ctx.strokeStyle = _rgba(spec.s, 0.35);
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(cx - rad * 0.72, cy + Math.sin(tilt) * rad * 0.3);
            ctx.lineTo(cx + rad * 0.72, cy - Math.sin(tilt) * rad * 0.3);
            ctx.stroke();
            return;
        }

        if (eng === 'wet_asphalt_oled') {
            const hz = h * 0.46;
            // Atmospheric wet road shimmer
            const roadG = ctx.createLinearGradient(0, hz, 0, h);
            roadG.addColorStop(0, _rgba(spec.p, 0.16));
            roadG.addColorStop(0.5, _rgba(spec.s, 0.06));
            roadG.addColorStop(1, 'rgba(0,0,0,0.9)');
            ctx.fillStyle = roadG;
            ctx.fillRect(0, hz, w, h - hz);

            // Iconic BMW L-blade OLED tail-light trails gliding into perspective
            const pairs = isPreview ? 3 : 6;
            for (let i = 0; i < pairs; i++) {
                const depth = ((t * 0.22 + sc * 0.9 + i / pairs) % 1);
                const f = depth * depth;
                const spread = w * (0.04 + f * 0.32);
                const y = hz + f * (h - hz) * 0.78;
                const bladeW = (isPreview ? 8 : 26) * (0.3 + f);
                const bladeH = (isPreview ? 3 : 9) * (0.3 + f);
                [-1, 1].forEach((side) => {
                    const lx = w * 0.5 + side * spread;
                    ctx.strokeStyle = _rgba(spec.p, 0.25 + f * 0.72);
                    ctx.lineWidth = Math.max(1.2, f * (isPreview ? 2 : 3.6));
                    ctx.beginPath();
                    ctx.moveTo(lx - side * bladeW, y);
                    ctx.lineTo(lx, y);
                    ctx.lineTo(lx + side * bladeW * 0.25, y - bladeH);
                    ctx.stroke();
                    // Vertical wet-asphalt reflection column
                    const rg = ctx.createLinearGradient(lx, y, lx, y + (h - y) * 0.7);
                    rg.addColorStop(0, _rgba(spec.p, 0.28 * f));
                    rg.addColorStop(1, 'rgba(0,0,0,0)');
                    ctx.fillStyle = rg;
                    ctx.fillRect(lx - bladeW * 0.5, y + 2, bladeW, (h - y) * 0.7);
                });
            }
            return;
        }

        if (eng === 'forged_wheel_brake') {
            const cx = w * 0.55, cy = h * 0.52;
            const rad = Math.min(w, h) * 0.38;
            const spin = t * 0.55 + sc * 2.6;
            // Ceramic brake caliper thermal glow behind spokes
            const cal = ctx.createRadialGradient(cx + rad * 0.42, cy, 2, cx + rad * 0.42, cy, rad * 0.42);
            cal.addColorStop(0, _rgba(spec.p, 0.52));
            cal.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.fillStyle = cal;
            ctx.beginPath(); ctx.arc(cx + rad * 0.42, cy, rad * 0.42, 0, Math.PI * 2); ctx.fill();

            // Outer forged alloy barrel & rotor ring
            ctx.strokeStyle = _rgba('#ffffff', 0.42);
            ctx.lineWidth = isPreview ? 2.2 : 4.2;
            ctx.beginPath(); ctx.arc(cx, cy, rad, 0, Math.PI * 2); ctx.stroke();
            ctx.strokeStyle = _rgba(spec.s, 0.28);
            ctx.lineWidth = isPreview ? 1.2 : 2;
            ctx.beginPath(); ctx.arc(cx, cy, rad * 0.72, 0, Math.PI * 2); ctx.stroke();

            // 10 Y-Spoke Forged BMW M-Competition Spokes spinning smoothly with scroll
            const spokes = 10;
            ctx.strokeStyle = _rgba('#e2e8f0', 0.52);
            ctx.lineWidth = isPreview ? 1.4 : 2.6;
            for (let i = 0; i < spokes; i++) {
                const a = spin + (i / spokes) * Math.PI * 2;
                const aFork = a + (i % 2 === 0 ? 0.085 : -0.085);
                ctx.beginPath();
                ctx.moveTo(cx + Math.cos(a) * rad * 0.18, cy + Math.sin(a) * rad * 0.18);
                ctx.lineTo(cx + Math.cos(a) * rad * 0.55, cy + Math.sin(a) * rad * 0.55);
                ctx.lineTo(cx + Math.cos(aFork) * rad * 0.96, cy + Math.sin(aFork) * rad * 0.96);
                ctx.stroke();
            }
            // Center lock hub
            ctx.strokeStyle = _rgba(spec.p, 0.85);
            ctx.lineWidth = isPreview ? 1.5 : 2.5;
            ctx.beginPath(); ctx.arc(cx, cy, rad * 0.16, 0, Math.PI * 2); ctx.stroke();
            return;
        }

        if (eng === 'circuit_elevation') {
            // Mountain elevation contour ribbons + luminous GPS racing line
            const layers = isPreview ? 5 : 9;
            for (let l = 0; l < layers; l++) {
                const baseY = h * (0.30 + l * 0.075);
                ctx.beginPath();
                for (let x = 0; x <= w; x += (isPreview ? 6 : 10)) {
                    const nx = x / w;
                    const y = baseY - Math.sin(nx * 5.2 + l * 0.8 + sc * (0.5 + l * 0.12)) * h * 0.06 - Math.cos(nx * 11 - sc * 0.7) * h * 0.02;
                    if (x === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.strokeStyle = _rgba(l === 4 ? spec.p : spec.s, l === 4 ? 0.82 : 0.18);
                ctx.lineWidth = l === 4 ? (isPreview ? 1.8 : 2.8) : 1;
                ctx.stroke();
            }
            // Live telemetry apex cursor riding the racing line
            const cxPos = (((t * 0.18 + sc * 0.45) % 1) + 1) % 1;
            const tx = cxPos * w;
            const ty = h * 0.60 - Math.sin(cxPos * 5.2 + 3.2 + sc * 0.98) * h * 0.06 - Math.cos(cxPos * 11 - sc * 0.7) * h * 0.02;
            ctx.fillStyle = '#ffffff';
            ctx.beginPath(); ctx.arc(tx, ty, isPreview ? 2.2 : 4, 0, Math.PI * 2); ctx.fill();
            return;
        }

        if (eng === 'studio_lightbar') {
            const bars = isPreview ? 5 : 8;
            const shift = (t * 0.25 + sc * 1.1) % 1;
            for (let i = 0; i < bars; i++) {
                const f = (i + shift) / bars;
                const y = h * (0.08 + f * 0.84);
                const curve = Math.sin(f * Math.PI) * h * 0.14;
                const alpha = Math.sin(f * Math.PI) * 0.42;
                ctx.strokeStyle = _rgba(i % 2 === 0 ? '#ffffff' : spec.p, alpha);
                ctx.lineWidth = (isPreview ? 2 : 4.5) * (0.5 + Math.sin(f * Math.PI));
                ctx.beginPath();
                ctx.moveTo(w * 0.06, y + curve * 0.4);
                ctx.quadraticCurveTo(w * 0.5, y - curve, w * 0.94, y + curve * 0.4);
                ctx.stroke();
            }
            return;
        }

        // ---------------- 25 MODIFIED HYPERCAR REEL ENGINES (RGB BLINKING HEADLIGHTS + MOVING PARTS) ----------------
        if (eng === 'modcar_reel') {
            const cx = w * 0.5;
            const cy = h * 0.54;
            const s = Math.min(w * 0.44, h * 0.62);
            const brand = spec.brand || 'bmw';
            const part = spec.part || 'headlight_strobe';

            // Dynamic RGB headlight color shifts on EVERY scroll step + strobe blink pulse!
            const rgbPrimary = _scrollRgbColor(sc, spec.seed || 1);
            const rgbAlt = _scrollRgbColor(sc + 1.8, (spec.seed || 1) + 2);
            const scrollActivity = Math.min(1, Math.abs(vel) * 1.4);
            const strobeWave = 0.5 + 0.5 * Math.sin(sc * 11.5 + t * 4.2);
            const blink = isPreview ? 0.92 : (0.48 + 0.52 * strobeWave + scrollActivity * 0.35);
            const beam = Math.min(1.25, blink);

            // Pitch-black wet studio floor + RGB ambient wash shifting with scroll
            const wash = ctx.createRadialGradient(cx, cy - s * 0.1, s * 0.08, cx, cy, Math.max(w, h) * 0.72);
            wash.addColorStop(0, _rgba(rgbPrimary, 0.22 * beam));
            wash.addColorStop(0.48, _rgba(rgbAlt, 0.08 * beam));
            wash.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.fillStyle = wash;
            ctx.fillRect(0, 0, w, h);

            // Sweeping studio light bar across widebody carbon hood
            const sweepX = cx + Math.sin(t * 0.35 + sc * 1.4) * w * 0.36;
            const hoodG = ctx.createLinearGradient(cx - s * 1.25, cy - s * 0.28, cx + s * 1.25, cy - s * 0.28);
            hoodG.addColorStop(0, 'rgba(255,255,255,0)');
            hoodG.addColorStop(0.5, _rgba('#ffffff', 0.20));
            hoodG.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.strokeStyle = hoodG;
            ctx.lineWidth = isPreview ? 1.1 : 1.9;
            ctx.beginPath();
            ctx.moveTo(cx - s * 1.25, cy - s * 0.14);
            ctx.bezierCurveTo(cx - s * 0.55, cy - s * 0.42, cx + s * 0.55, cy - s * 0.42, cx + s * 1.25, cy - s * 0.14);
            ctx.stroke();

            // Helper: draw brand-specific iconic modified headlights with RGB color-shift & scroll strobe blink!
            const drawBrandHeadlights = (hy) => {
                [-1, 1].forEach((side) => {
                    const ex = cx + side * s * 0.66;
                    // Wide volumetric RGB headlight halo
                    const halo = ctx.createRadialGradient(ex, hy, 1, ex, hy, s * 0.52);
                    halo.addColorStop(0, _rgba(rgbPrimary, 0.54 * beam));
                    halo.addColorStop(0.35, _rgba(rgbAlt, 0.18 * beam));
                    halo.addColorStop(1, 'rgba(0,0,0,0)');
                    ctx.fillStyle = halo;
                    ctx.beginPath(); ctx.arc(ex, hy, s * 0.52, 0, Math.PI * 2); ctx.fill();

                    // Anamorphic horizontal strobe flash streak on scroll
                    if (!isPreview) {
                        const fl = ctx.createLinearGradient(ex - s * 0.62, hy, ex + s * 0.62, hy);
                        fl.addColorStop(0, 'rgba(0,0,0,0)');
                        fl.addColorStop(0.4, _rgba(rgbPrimary, 0.24 * beam));
                        fl.addColorStop(0.5, _rgba('#ffffff', 0.52 * beam));
                        fl.addColorStop(0.6, _rgba(rgbPrimary, 0.24 * beam));
                        fl.addColorStop(1, 'rgba(0,0,0,0)');
                        ctx.fillStyle = fl;
                        ctx.fillRect(ex - s * 0.62, hy - 1.6, s * 1.24, 3.2);
                    }

                    const strokeOptic = (traceFn) => {
                        ctx.lineCap = 'round';
                        ctx.lineJoin = 'round';
                        ctx.strokeStyle = _rgba(rgbPrimary, 0.65 * beam);
                        ctx.lineWidth = isPreview ? 3.2 : 7.0;
                        traceFn(); ctx.stroke();
                        ctx.strokeStyle = _rgba(rgbAlt, 0.85 * beam);
                        ctx.lineWidth = isPreview ? 1.8 : 3.2;
                        traceFn(); ctx.stroke();
                        ctx.strokeStyle = _rgba('#ffffff', Math.min(1, 0.72 + 0.28 * beam));
                        ctx.lineWidth = isPreview ? 0.95 : 1.8;
                        traceFn(); ctx.stroke();
                    };

                    if (brand === 'bmw') {
                        // Predatory M4 CSL twin hexagonal L-blades
                        for (let k = 0; k < 2; k++) {
                            const ox = ex + side * (k === 0 ? -s * 0.13 : s * 0.11);
                            const oy = hy + (k === 0 ? s * 0.01 : -s * 0.014);
                            strokeOptic(() => {
                                ctx.beginPath();
                                ctx.moveTo(ox - side * s * 0.095, oy - s * 0.042);
                                ctx.lineTo(ox - side * s * 0.062, oy + s * 0.032);
                                ctx.lineTo(ox + side * s * 0.068, oy + s * 0.026);
                                ctx.lineTo(ox + side * s * 0.11, oy - s * 0.036);
                            });
                        }
                    } else if (brand === 'ferrari') {
                        // Razor Italian SF90 / 812 sweeping L-fang LEDs
                        strokeOptic(() => {
                            ctx.beginPath();
                            ctx.moveTo(ex - side * s * 0.22, hy + s * 0.03);
                            ctx.lineTo(ex + side * s * 0.14, hy + s * 0.01);
                            ctx.lineTo(ex + side * s * 0.26, hy - s * 0.095);
                        });
                        strokeOptic(() => {
                            ctx.beginPath();
                            ctx.moveTo(ex - side * s * 0.14, hy - s * 0.025);
                            ctx.lineTo(ex + side * s * 0.08, hy - s * 0.038);
                        });
                    } else if (brand === 'pagani') {
                        // Iconic Pagani quad-pod carbon projector pods (2 stacked twin eyes per side)
                        for (let p = 0; p < 2; p++) {
                            const px = ex + side * (p === 0 ? -s * 0.09 : s * 0.10);
                            const py = hy + (p === 0 ? s * 0.016 : -s * 0.022);
                            const r = s * (p === 0 ? 0.046 : 0.054);
                            strokeOptic(() => {
                                ctx.beginPath();
                                ctx.arc(px, py, r, 0, Math.PI * 2);
                            });
                        }
                    } else if (brand === 'bugatti') {
                        // Signature Bugatti Chiron 4-dot quad-pixel LED bar
                        for (let d = 0; d < 4; d++) {
                            const dx = ex + side * (-s * 0.17 + d * s * 0.115);
                            const dy = hy - d * s * 0.008;
                            strokeOptic(() => {
                                ctx.beginPath();
                                ctx.moveTo(dx - side * s * 0.03, dy + s * 0.014);
                                ctx.lineTo(dx + side * s * 0.03, dy + s * 0.014);
                                ctx.lineTo(dx + side * s * 0.03, dy - s * 0.018);
                                ctx.lineTo(dx - side * s * 0.03, dy - s * 0.018);
                                ctx.closePath();
                            });
                        }
                    } else {
                        // Lamborghini / Koenigsegg / GT3RS predatory Y-fang blade
                        strokeOptic(() => {
                            ctx.beginPath();
                            ctx.moveTo(ex - side * s * 0.19, hy + s * 0.02);
                            ctx.lineTo(ex + side * s * 0.04, hy + s * 0.012);
                            ctx.lineTo(ex + side * s * 0.22, hy - s * 0.078);
                            ctx.moveTo(ex + side * s * 0.04, hy + s * 0.012);
                            ctx.lineTo(ex + side * s * 0.21, hy + s * 0.072);
                        });
                    }

                    // Wet studio floor RGB elliptical reflection under each headlight
                    ctx.save();
                    ctx.translate(ex, cy + s * 0.38);
                    ctx.scale(1.0, 0.22);
                    const fr = ctx.createRadialGradient(0, 0, 2, 0, 0, s * 0.56);
                    fr.addColorStop(0, _rgba(rgbPrimary, 0.34 * beam));
                    fr.addColorStop(0.5, _rgba(rgbAlt, 0.12 * beam));
                    fr.addColorStop(1, 'rgba(0,0,0,0)');
                    ctx.fillStyle = fr;
                    ctx.beginPath(); ctx.arc(0, 0, s * 0.56, 0, Math.PI * 2); ctx.fill();
                    ctx.restore();
                });

                // Subtle center grille accent matching brand
                if (brand === 'bugatti') {
                    // Iconic illuminated carbon horseshoe grille
                    ctx.strokeStyle = _rgba(rgbPrimary, 0.42 * beam);
                    ctx.lineWidth = isPreview ? 1.2 : 2.1;
                    ctx.beginPath();
                    ctx.arc(cx, hy + s * 0.10, s * 0.18, Math.PI, Math.PI * 2);
                    ctx.lineTo(cx + s * 0.16, hy + s * 0.26);
                    ctx.lineTo(cx - s * 0.16, hy + s * 0.26);
                    ctx.closePath();
                    ctx.stroke();
                } else if (brand === 'bmw') {
                    // Dark recessed carbon double kidney grilles
                    [-1, 1].forEach((side) => {
                        const gx = cx + side * s * 0.028;
                        ctx.fillStyle = 'rgba(3,4,7,0.88)';
                        ctx.strokeStyle = _rgba(rgbPrimary, 0.32 * beam);
                        ctx.lineWidth = isPreview ? 1 : 1.6;
                        ctx.beginPath();
                        ctx.roundRect(side < 0 ? gx - s * 0.19 : gx, hy - s * 0.05, s * 0.19, s * 0.22, 10);
                        ctx.fill();
                        ctx.stroke();
                    });
                } else {
                    // Widebody low carbon front splitter glow line
                    const spG = ctx.createLinearGradient(cx - s * 0.9, 0, cx + s * 0.9, 0);
                    spG.addColorStop(0, 'rgba(0,0,0,0)');
                    spG.addColorStop(0.5, _rgba(rgbPrimary, 0.48 * beam));
                    spG.addColorStop(1, 'rgba(0,0,0,0)');
                    ctx.strokeStyle = spG;
                    ctx.lineWidth = isPreview ? 1.4 : 2.4;
                    ctx.beginPath();
                    ctx.moveTo(cx - s * 0.92, hy + s * 0.24);
                    ctx.quadraticCurveTo(cx, hy + s * 0.29, cx + s * 0.92, hy + s * 0.24);
                    ctx.stroke();
                }
            };

            // ---- SIGNATURE MOVING PART PER MODIFIED CAR ----
            if (part === 'wiper_rain') {
                // Dark glass windshield perspective + live raindrops + twin aero windshield wipers ("water cleaner") moving on scroll!
                drawBrandHeadlights(cy + s * 0.06);

                // Slanted monsoon rain streaks falling across tinted windshield
                const drops = isPreview ? 28 : 85;
                ctx.lineWidth = isPreview ? 0.8 : 1.15;
                for (let i = 0; i < drops; i++) {
                    const rx = rnd() * w;
                    const ry = ((rnd() * h + (t * 220 + sc * 320) * (0.6 + rnd() * 0.8)) % (h + 40)) - 20;
                    const len = (isPreview ? 7 : 18) + rnd() * 14;
                    ctx.strokeStyle = _rgba(i % 4 === 0 ? rgbPrimary : '#cbd5e1', 0.16 + rnd() * 0.24);
                    ctx.beginPath();
                    ctx.moveTo(rx, ry);
                    ctx.lineTo(rx - len * 0.22, ry + len);
                    ctx.stroke();
                }

                // Twin sweeping aero windshield wiper blades pivoting cleanly with scroll!
                const wipeSweep = Math.sin(sc * 2.4 + t * 1.15); // -1 .. +1
                const wiperLen = s * 0.82;
                const pivots = [
                    { x: cx - s * 0.36, y: h * 0.86 },
                    { x: cx + s * 0.18, y: h * 0.86 },
                ];
                pivots.forEach((pv, pi) => {
                    const ang = -Math.PI * 0.5 + wipeSweep * 0.72 + (pi === 0 ? -0.08 : 0.08);
                    const tipX = pv.x + Math.cos(ang) * wiperLen;
                    const tipY = pv.y + Math.sin(ang) * wiperLen;
                    // Clean water-cleared misty arc trail behind the moving wiper blade
                    ctx.strokeStyle = _rgba(rgbPrimary, 0.12 * beam);
                    ctx.lineWidth = isPreview ? 6 : 16;
                    ctx.beginPath();
                    ctx.arc(pv.x, pv.y, wiperLen * 0.72, ang - 0.18, ang + 0.18);
                    ctx.stroke();
                    // Sleek matte-carbon wiper arm & rubber aero blade
                    ctx.strokeStyle = 'rgba(226,232,240,0.72)';
                    ctx.lineWidth = isPreview ? 1.8 : 3.4;
                    ctx.lineCap = 'round';
                    ctx.beginPath();
                    ctx.moveTo(pv.x, pv.y);
                    ctx.lineTo(tipX, tipY);
                    ctx.stroke();
                    // Water bead spray glinting off blade edge
                    ctx.strokeStyle = _rgba(rgbPrimary, 0.65 * beam);
                    ctx.lineWidth = isPreview ? 0.9 : 1.5;
                    ctx.beginPath();
                    ctx.moveTo(pv.x + Math.cos(ang) * wiperLen * 0.35, pv.y + Math.sin(ang) * wiperLen * 0.35);
                    ctx.lineTo(tipX, tipY);
                    ctx.stroke();
                });
                return;
            }

            if (part === 'forged_tyres') {
                // Blinking RGB headlights at upper horizon + twin giant spinning deep-dish forged tyres with glowing ceramic brakes!
                drawBrandHeadlights(cy - s * 0.24);
                const spin = t * 0.9 + sc * 4.2;
                const wRad = s * 0.35;
                [-1, 1].forEach((side) => {
                    const wx = cx + side * s * 0.68;
                    const wy = cy + s * 0.26;
                    // Glowing hot carbon-ceramic brake caliper
                    const cal = ctx.createRadialGradient(wx - side * wRad * 0.35, wy, 2, wx - side * wRad * 0.35, wy, wRad * 0.55);
                    cal.addColorStop(0, _rgba('#fb923c', 0.62));
                    cal.addColorStop(0.5, _rgba(rgbPrimary, 0.24 * beam));
                    cal.addColorStop(1, 'rgba(0,0,0,0)');
                    ctx.fillStyle = cal;
                    ctx.beginPath(); ctx.arc(wx - side * wRad * 0.35, wy, wRad * 0.55, 0, Math.PI * 2); ctx.fill();

                    // Outer dark tyre wall & forged rim lip
                    ctx.strokeStyle = 'rgba(18,20,26,0.95)';
                    ctx.lineWidth = isPreview ? 5 : 12;
                    ctx.beginPath(); ctx.arc(wx, wy, wRad, 0, Math.PI * 2); ctx.stroke();

                    ctx.strokeStyle = _rgba(rgbPrimary, 0.58 * beam);
                    ctx.lineWidth = isPreview ? 1.5 : 2.8;
                    ctx.beginPath(); ctx.arc(wx, wy, wRad * 0.86, 0, Math.PI * 2); ctx.stroke();

                    // 10-Spoke concave forged alloy spinning rapidly with scroll!
                    ctx.strokeStyle = 'rgba(226,232,240,0.68)';
                    ctx.lineWidth = isPreview ? 1.2 : 2.4;
                    for (let k = 0; k < 10; k++) {
                        const a = spin * side + (k / 10) * Math.PI * 2;
                        const af = a + (k % 2 === 0 ? 0.1 : -0.1);
                        ctx.beginPath();
                        ctx.moveTo(wx + Math.cos(a) * wRad * 0.18, wy + Math.sin(a) * wRad * 0.18);
                        ctx.lineTo(wx + Math.cos(a) * wRad * 0.52, wy + Math.sin(a) * wRad * 0.52);
                        ctx.lineTo(wx + Math.cos(af) * wRad * 0.85, wy + Math.sin(af) * wRad * 0.85);
                        ctx.stroke();
                    }
                    // Center lock ring
                    ctx.strokeStyle = _rgba(rgbAlt, 0.9);
                    ctx.lineWidth = isPreview ? 1.4 : 2.4;
                    ctx.beginPath(); ctx.arc(wx, wy, wRad * 0.17, 0, Math.PI * 2); ctx.stroke();
                });
                return;
            }

            if (part === 'exhaust_flame') {
                // Blinking RGB optics + Quad Titanium Exhaust Pipes spitting blue/amber backfire flames on scroll!
                drawBrandHeadlights(cy - s * 0.18);
                const diffY = cy + s * 0.25;
                // Carbon rear diffuser fins
                ctx.strokeStyle = 'rgba(255,255,255,0.16)';
                ctx.lineWidth = isPreview ? 1.2 : 2.2;
                for (let f = -3; f <= 3; f++) {
                    const fx = cx + f * s * 0.14;
                    ctx.beginPath();
                    ctx.moveTo(fx, diffY - s * 0.08);
                    ctx.lineTo(fx + f * s * 0.02, diffY + s * 0.14);
                    ctx.stroke();
                }
                // Quad titanium exhaust tips with realistic feathered jet-torch backfire flames + sparks on scroll!
                const flamePower = isPreview ? 0.85 : Math.min(1.35, 0.42 + Math.abs(Math.sin(sc * 4.5 + t * 2.5)) * 0.58 + scrollActivity * 0.75);
                const pipeOffsets = [-0.52, -0.34, 0.34, 0.52];
                pipeOffsets.forEach((po, idx) => {
                    const px = cx + po * s;
                    const py = diffY + s * 0.04;
                    const pr = s * 0.052;
                    const fLen = s * (0.22 + 0.18 * flamePower);

                    // Soft circular atmospheric afterburner glow (ZERO hard ellipse edge!)
                    const ambGlow = ctx.createRadialGradient(px, py + fLen * 0.25, 1, px, py + fLen * 0.25, fLen * 1.15);
                    ambGlow.addColorStop(0, _rgba('#38bdf8', 0.42 * flamePower));
                    ambGlow.addColorStop(0.35, _rgba('#fb923c', 0.26 * flamePower));
                    ambGlow.addColorStop(0.7, _rgba(rgbPrimary, 0.10 * flamePower));
                    ambGlow.addColorStop(1, 'rgba(0,0,0,0)');
                    ctx.fillStyle = ambGlow;
                    ctx.beginPath();
                    ctx.arc(px, py + fLen * 0.25, fLen * 1.15, 0, Math.PI * 2);
                    ctx.fill();

                    // Sculpted tapered jet-torch outer amber tongue + inner electric-blue Mach diamond core
                    const drawTongue = (wScale, lScale, gradStops) => {
                        const fl = fLen * lScale;
                        const fw = pr * wScale;
                        const sway = Math.sin(t * 14 + sc * 6 + idx * 1.9) * pr * 0.25;
                        const tg = ctx.createLinearGradient(px, py, px + sway, py + fl);
                        gradStops.forEach(([stop, col]) => tg.addColorStop(stop, col));
                        ctx.fillStyle = tg;
                        ctx.beginPath();
                        ctx.moveTo(px - fw, py);
                        ctx.quadraticCurveTo(px - fw * 0.85, py + fl * 0.55, px + sway, py + fl);
                        ctx.quadraticCurveTo(px + fw * 0.85, py + fl * 0.55, px + fw, py);
                        ctx.closePath();
                        ctx.fill();
                    };
                    drawTongue(1.15, 1.05, [[0, _rgba('#fb923c', 0.82 * flamePower)], [0.55, _rgba('#f97316', 0.45 * flamePower)], [1, 'rgba(0,0,0,0)']]);
                    drawTongue(0.68, 0.72, [[0, '#ffffff'], [0.42, _rgba('#38bdf8', 0.92)], [1, 'rgba(56,189,248,0)']]);

                    // Titanium burnt-blue exhaust bezel ring
                    ctx.fillStyle = 'rgba(4,5,9,0.85)';
                    ctx.beginPath(); ctx.arc(px, py, pr, 0, Math.PI * 2); ctx.fill();
                    ctx.strokeStyle = idx % 2 === 0 ? '#93c5fd' : '#e2e8f0';
                    ctx.lineWidth = isPreview ? 1.4 : 2.5;
                    ctx.beginPath(); ctx.arc(px, py, pr, 0, Math.PI * 2); ctx.stroke();

                    // Hot flying titanium backfire sparks driven by scroll!
                    for (let sp = 0; sp < (isPreview ? 2 : 5); sp++) {
                        const spT = ((t * 1.6 + sc * 2.2 + sp * 0.27 + idx * 0.19) % 1);
                        const sx = px + Math.sin(sp * 7.3 + idx) * pr * (0.8 + spT * 2.6);
                        const sy = py + spT * fLen * 1.35;
                        ctx.fillStyle = _rgba('#fde68a', (1 - spT) * 0.85);
                        ctx.beginPath(); ctx.arc(sx, sy, isPreview ? 1 : 1.7, 0, Math.PI * 2); ctx.fill();
                    }
                });
                return;
            }

            if (part === 'aero_wing') {
                // Active Swan-Neck Carbon GT / DRS Wing pitching dynamically on scroll + RGB blinking headlights + vortex trails!
                const drsPitch = Math.sin(sc * 1.9 + t * 0.6) * s * 0.095;
                const wingY = cy - s * 0.32 + drsPitch * 0.35;
                // Swan-neck carbon wing uprights
                ctx.strokeStyle = 'rgba(203,213,225,0.42)';
                ctx.lineWidth = isPreview ? 2 : 4;
                [-0.36, 0.36].forEach((ux) => {
                    ctx.beginPath();
                    ctx.moveTo(cx + ux * s, cy - s * 0.05);
                    ctx.quadraticCurveTo(cx + ux * s * 0.92, wingY - s * 0.05, cx + ux * s * 1.04, wingY + drsPitch * 0.4);
                    ctx.stroke();
                });
                // Main carbon airfoil blade + dynamic DRS upper flap
                const wingG = ctx.createLinearGradient(cx - s * 1.08, wingY, cx + s * 1.08, wingY);
                wingG.addColorStop(0, _rgba(rgbPrimary, 0.75 * beam));
                wingG.addColorStop(0.5, '#f8fafc');
                wingG.addColorStop(1, _rgba(rgbAlt, 0.75 * beam));
                ctx.strokeStyle = wingG;
                ctx.lineWidth = isPreview ? 2.6 : 5.2;
                ctx.beginPath();
                ctx.moveTo(cx - s * 1.08, wingY + s * 0.04);
                ctx.quadraticCurveTo(cx, wingY - s * 0.06 + drsPitch, cx + s * 1.08, wingY + s * 0.04);
                ctx.stroke();

                // Aerodynamic wingtip vortex ribbons streaming off both carbon endplates
                [-1, 1].forEach((side) => {
                    const ex = cx + side * s * 1.08;
                    ctx.strokeStyle = _rgba(rgbPrimary, 0.34 * beam);
                    ctx.lineWidth = isPreview ? 1 : 1.8;
                    ctx.beginPath();
                    for (let k = 0; k <= 16; k++) {
                        const f = k / 16;
                        const vx = ex + side * f * s * 0.45;
                        const vy = wingY + s * 0.04 + Math.sin(f * 10 - sc * 4 - t * 2) * s * 0.04 * (1 + f);
                        if (k === 0) ctx.moveTo(vx, vy);
                        else ctx.lineTo(vx, vy);
                    }
                    ctx.stroke();
                });

                drawBrandHeadlights(cy + s * 0.06);
                return;
            }

            // Default: 'headlight_strobe' — pure widebody dark studio RGB blinking hypercar reel!
            drawBrandHeadlights(cy);
            return;
        }

        // ---------------- 25 REALISTIC CINEMATIC ENVIRONMENT ENGINES ----------------
        if (eng === 'env_rain_storm') {
            const hz = h * 0.64;
            // Distant nocturnal city/horizon neon bokeh lights shifting gently on scroll
            const bokehN = isPreview ? 8 : 18;
            for (let b = 0; b < bokehN; b++) {
                const bx = (((rnd() * w + sc * (18 + b * 4)) % (w + 80)) + (w + 80)) % (w + 80) - 40;
                const by = hz * (0.35 + rnd() * 0.58);
                const br = (isPreview ? 8 : 22) + rnd() * (isPreview ? 10 : 28);
                const bg = ctx.createRadialGradient(bx, by, 1, bx, by, br);
                bg.addColorStop(0, _rgba(b % 2 === 0 ? spec.p : spec.s, 0.22));
                bg.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = bg;
                ctx.beginPath(); ctx.arc(bx, by, br, 0, Math.PI * 2); ctx.fill();
            }
            // Wet reflective ground plane
            const gnd = ctx.createLinearGradient(0, hz, 0, h);
            gnd.addColorStop(0, _rgba(spec.p, 0.16));
            gnd.addColorStop(0.5, _rgba(spec.s, 0.06));
            gnd.addColorStop(1, 'rgba(2,3,6,0.96)');
            ctx.fillStyle = gnd;
            ctx.fillRect(0, hz, w, h - hz);

            // Expanding rain puddle ripples on wet asphalt
            const ripN = isPreview ? 5 : 11;
            for (let r = 0; r < ripN; r++) {
                const rx = rnd() * w;
                const ry = hz + rnd() * (h - hz) * 0.88;
                const phase = ((t * 0.75 + sc * 0.9 + rnd()) % 1);
                const rad = phase * (isPreview ? 14 : 42);
                ctx.strokeStyle = _rgba(r % 2 === 0 ? spec.p : '#e2e8f0', (1 - phase) * 0.36);
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.ellipse(rx, ry, rad, rad * 0.28, 0, 0, Math.PI * 2);
                ctx.stroke();
            }
            // Multi-depth slanted volumetric rain streaks
            const rainN = isPreview ? 32 : 110;
            for (let i = 0; i < rainN; i++) {
                const depth = 0.4 + rnd() * 0.8;
                const x = rnd() * (w + 80);
                const y = ((rnd() * h + (t * 280 + sc * 340) * depth) % (h + 40)) - 20;
                const len = (isPreview ? 8 : 22) * depth;
                ctx.strokeStyle = _rgba(i % 5 === 0 ? spec.p : '#cbd5e1', 0.12 + depth * 0.22);
                ctx.lineWidth = depth > 0.95 ? 1.3 : 0.85;
                ctx.beginPath();
                ctx.moveTo(x, y);
                ctx.lineTo(x - len * 0.20, y + len);
                ctx.stroke();
            }
            return;
        }

        if (eng === 'env_aurora_peaks') {
            const hz = h * 0.68;
            // Shimmering volumetric Aurora Borealis curtains undulating smoothly on scroll
            const curtains = isPreview ? 3 : 5;
            for (let c = 0; c < curtains; c++) {
                const step = isPreview ? 8 : 10;
                const baseY = h * (0.20 + c * 0.085);
                for (let x = 0; x <= w; x += step) {
                    const nx = x / w;
                    const wave = Math.sin(nx * 5.2 + c * 1.4 + t * 0.45 + sc * 1.35) * h * 0.085
                        + Math.cos(nx * 10.5 - t * 0.3 + sc * 0.9) * h * 0.03;
                    const yTop = baseY + wave - h * 0.14;
                    const yBot = baseY + wave + h * 0.13;
                    const aGrad = ctx.createLinearGradient(x, yTop, x, yBot);
                    aGrad.addColorStop(0, 'rgba(0,0,0,0)');
                    aGrad.addColorStop(0.45, _rgba(c % 2 === 0 ? spec.p : spec.s, 0.15));
                    aGrad.addColorStop(0.78, _rgba(spec.p, 0.06));
                    aGrad.addColorStop(1, 'rgba(0,0,0,0)');
                    ctx.fillStyle = aGrad;
                    ctx.fillRect(x, yTop, step + 1, yBot - yTop);
                }
            }
            // Layered dark obsidian alpine peaks with parallax scroll depth
            for (let layer = 0; layer < 3; layer++) {
                const shift = sc * (18 + layer * 24);
                const ridgeBase = hz - (2 - layer) * h * 0.06;
                ctx.beginPath();
                ctx.moveTo(0, h);
                for (let x = 0; x <= w; x += (isPreview ? 8 : 10)) {
                    const nx = (x + shift) / w;
                    const peak = Math.abs(Math.sin(nx * (3.2 + layer * 1.5) + spec.seed + layer)) * h * (0.14 - layer * 0.025)
                        + Math.sin(nx * 11 + layer * 2) * h * 0.02;
                    ctx.lineTo(x, ridgeBase - peak);
                }
                ctx.lineTo(w, h);
                ctx.closePath();
                ctx.fillStyle = layer === 2 ? '#040508' : (layer === 1 ? 'rgba(8,11,17,0.86)' : 'rgba(13,18,28,0.68)');
                ctx.fill();
            }
            // Mirror glacial lake reflection whisper
            const lk = ctx.createLinearGradient(0, hz, 0, h);
            lk.addColorStop(0, _rgba(spec.p, 0.16));
            lk.addColorStop(1, 'rgba(2,4,8,0.92)');
            ctx.fillStyle = lk;
            ctx.fillRect(0, hz + h * 0.04, w, h - hz);
            return;
        }

        if (eng === 'env_abyss_ocean') {
            // Volumetric underwater light-shafts slicing downward through midnight abyss
            const shafts = isPreview ? 4 : 8;
            for (let i = 0; i < shafts; i++) {
                const sx = w * (0.08 + (i / shafts) * 0.88) + Math.sin(t * 0.35 + sc * 0.9 + i) * w * 0.06;
                const sw = w * (0.04 + rnd() * 0.06);
                const sg = ctx.createLinearGradient(sx, 0, sx + w * 0.14, h * 0.92);
                sg.addColorStop(0, _rgba(i % 2 === 0 ? spec.p : spec.s, 0.20));
                sg.addColorStop(0.65, _rgba(spec.p, 0.05));
                sg.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = sg;
                ctx.beginPath();
                ctx.moveTo(sx - sw * 0.4, 0);
                ctx.lineTo(sx + sw * 0.4, 0);
                ctx.lineTo(sx + w * 0.16 + sw * 1.4, h);
                ctx.lineTo(sx + w * 0.16 - sw * 1.2, h);
                ctx.closePath();
                ctx.fill();
            }
            // Gently undulating caustic ribbons
            for (let r = 0; r < (isPreview ? 4 : 7); r++) {
                const y0 = h * (0.22 + r * 0.11);
                ctx.beginPath();
                for (let x = 0; x <= w; x += (isPreview ? 8 : 10)) {
                    const y = y0 + Math.sin(x * 0.012 + t * 0.8 + sc * 1.6 + r) * h * 0.025;
                    if (x === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.strokeStyle = _rgba(r % 2 === 0 ? spec.p : spec.s, 0.16);
                ctx.lineWidth = 1.2;
                ctx.stroke();
            }
            // Rising bioluminescent marine light motes driven by scroll
            const motes = isPreview ? 18 : 52;
            for (let m = 0; m < motes; m++) {
                const mx = rnd() * w + Math.sin(t + m) * 14;
                const my = (((rnd() * h - (t * 28 + sc * 120) * (0.4 + rnd() * 0.7)) % h) + h) % h;
                const mr = (isPreview ? 1.1 : 2.1) + rnd() * 1.4;
                ctx.fillStyle = _rgba(m % 3 === 0 ? '#ffffff' : spec.p, 0.28 + rnd() * 0.55);
                ctx.beginPath(); ctx.arc(mx, my, mr, 0, Math.PI * 2); ctx.fill();
            }
            return;
        }

        if (eng === 'env_volcanic_embers') {
            const hz = h * 0.74;
            // Deep caldera molten horizon glow
            const glow = ctx.createRadialGradient(w * 0.5, hz, 10, w * 0.5, hz, w * 0.72);
            glow.addColorStop(0, _rgba(spec.p, 0.34));
            glow.addColorStop(0.45, _rgba(spec.s, 0.12));
            glow.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.fillStyle = glow;
            ctx.fillRect(0, 0, w, h);

            // Dark basalt volcanic ridge silhouette
            ctx.beginPath();
            ctx.moveTo(0, h);
            const pan = sc * 28;
            for (let x = 0; x <= w; x += (isPreview ? 8 : 10)) {
                const nx = (x + pan) / w;
                const y = hz - Math.abs(Math.sin(nx * 4.1 + spec.seed)) * h * 0.16 - Math.cos(nx * 9.5) * h * 0.025;
                ctx.lineTo(x, y);
            }
            ctx.lineTo(w, h);
            ctx.closePath();
            ctx.fillStyle = '#070405';
            ctx.fill();

            // Glowing lava rim along caldera silhouette
            ctx.beginPath();
            for (let x = 0; x <= w; x += (isPreview ? 8 : 10)) {
                const nx = (x + pan) / w;
                const y = hz - Math.abs(Math.sin(nx * 4.1 + spec.seed)) * h * 0.16 - Math.cos(nx * 9.5) * h * 0.025;
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.strokeStyle = _rgba(spec.p, 0.45 + Math.sin(t * 1.4 + sc) * 0.18);
            ctx.lineWidth = isPreview ? 1.1 : 2;
            ctx.stroke();

            // Swirling incandescent ash embers rising with scroll velocity
            const embers = isPreview ? 22 : 68;
            for (let e = 0; e < embers; e++) {
                const sp = 0.5 + rnd() * 0.9;
                const ex = (((rnd() * w + Math.sin(t * 0.9 + e) * 28 + sc * 42 * sp) % w) + w) % w;
                const ey = (((rnd() * h - (t * 48 + sc * 180) * sp) % h) + h) % h;
                const er = (isPreview ? 1.0 : 1.9) + rnd() * 1.5;
                ctx.fillStyle = _rgba(e % 3 === 0 ? '#fde68a' : spec.p, 0.35 + rnd() * 0.6);
                ctx.beginPath(); ctx.arc(ex, ey, er, 0, Math.PI * 2); ctx.fill();
            }
            return;
        }

        if (eng === 'env_mist_cosmos') {
            // Deep-field starlight + shooting meteors gliding across night sky on scroll
            const stars = isPreview ? 30 : 95;
            for (let i = 0; i < stars; i++) {
                const sx = (((rnd() * w - sc * (4 + (i % 4) * 3)) % w) + w) % w;
                const sy = rnd() * h * 0.72;
                const tw = 0.25 + 0.65 * (0.5 + 0.5 * Math.sin(t * 2 + i * 3.1));
                ctx.fillStyle = _rgba(i % 4 === 0 ? spec.p : '#ffffff', tw);
                ctx.fillRect(sx, sy, i % 6 === 0 ? 2 : 1.2, i % 6 === 0 ? 2 : 1.2);
            }
            // Shooting meteor streak driven by scroll
            const mPhase = ((t * 0.22 + sc * 0.65) % 1 + 1) % 1;
            const mx = w * (0.15 + mPhase * 0.72);
            const my = h * (0.12 + mPhase * 0.26);
            const mg = ctx.createLinearGradient(mx, my, mx - w * 0.10, my - h * 0.045);
            mg.addColorStop(0, _rgba('#ffffff', 0.85));
            mg.addColorStop(0.4, _rgba(spec.p, 0.38));
            mg.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.strokeStyle = mg;
            ctx.lineWidth = isPreview ? 1.2 : 2;
            ctx.beginPath(); ctx.moveTo(mx, my); ctx.lineTo(mx - w * 0.10, my - h * 0.045); ctx.stroke();

            // Layered nocturnal mountain/dune silhouettes with rolling silver valley mist
            for (let l = 0; l < 3; l++) {
                const base = h * (0.64 + l * 0.09);
                const sh = sc * (14 + l * 22);
                ctx.beginPath();
                ctx.moveTo(0, h);
                for (let x = 0; x <= w; x += (isPreview ? 8 : 10)) {
                    const nx = (x + sh) / w;
                    const y = base - Math.sin(nx * (3.6 + l * 1.4) + spec.seed + l * 1.7) * h * (0.08 - l * 0.015) - Math.cos(nx * 8.2) * h * 0.02;
                    ctx.lineTo(x, y);
                }
                ctx.lineTo(w, h);
                ctx.closePath();
                ctx.fillStyle = l === 2 ? '#05060a' : (l === 1 ? 'rgba(9,12,18,0.82)' : 'rgba(15,20,30,0.62)');
                ctx.fill();

                // Soft silver mist ribbon hovering between ridges
                const mistG = ctx.createLinearGradient(0, base - h * 0.04, 0, base + h * 0.07);
                mistG.addColorStop(0, 'rgba(0,0,0,0)');
                mistG.addColorStop(0.5, _rgba(spec.s, 0.09));
                mistG.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = mistG;
                ctx.fillRect(0, base - h * 0.04, w, h * 0.11);
            }
            return;
        }

        // pitlane_laser
        const hz = h * 0.52;
        const sweep = Math.sin(t * 0.4 + sc * 1.4) * w * 0.22;
        // Dual volumetric laser alignment cones from front bumper
        [-1, 1].forEach((side) => {
            const bx = w * 0.5 + side * w * 0.16 + sweep * 0.25;
            const lg = ctx.createLinearGradient(bx, hz * 0.65, bx + side * w * 0.12, h);
            lg.addColorStop(0, _rgba(spec.p, 0.34));
            lg.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.fillStyle = lg;
            ctx.beginPath();
            ctx.moveTo(bx - 6, hz * 0.65);
            ctx.lineTo(bx + 6, hz * 0.65);
            ctx.lineTo(bx + side * w * 0.18 + w * 0.08, h);
            ctx.lineTo(bx + side * w * 0.18 - w * 0.08, h);
            ctx.closePath();
            ctx.fill();
        });
        // Floor laser alignment grid
        const lines = isPreview ? 6 : 12;
        const off = (t * 0.3 + sc * 1.2) % 1;
        for (let r = 0; r < lines; r++) {
            const f = Math.pow((r + off) / lines, 2);
            const y = hz + f * (h - hz);
            ctx.strokeStyle = _rgba(spec.s, 0.1 + f * 0.34);
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
        }
    }

    // =========================================================================
    // LIVE SCROLL-DRIVEN RUNTIME CONTROLLER (Home Screen + Chat + Workspace)
    // =========================================================================
    const Engine = {
        catalog: CATALOG,
        activeSpec: CATALOG[0],
        canvas: null,
        ctx: null,
        rafId: 0,
        lastTs: 0,
        timeAcc: 0,
        targetScroll: 0,
        smoothScroll: 0,
        velocity: 0,
        intensity: 1.0,
        previewCache: new Map(),

        init() {
            if (this.canvas) return;
            const layer = document.getElementById('auraWallpaperLayer');
            if (!layer) return;
            let c = document.getElementById('auraLiveWallpaperCanvas');
            if (!c) {
                c = document.createElement('canvas');
                c.id = 'auraLiveWallpaperCanvas';
                c.style.cssText = 'position:absolute; inset:0; width:100%; height:100%; display:block; pointer-events:none;';
                layer.appendChild(c);
            }
            this.canvas = c;
            this.ctx = c.getContext('2d', { alpha: false });
            try {
                const savedInt = parseFloat(localStorage.getItem('aura_wallpaper_scroll_intensity') || '1.0');
                if (Number.isFinite(savedInt)) this.intensity = Math.max(0.2, Math.min(2.2, savedInt));
            } catch (_) {}

            const resize = () => this._resize();
            window.addEventListener('resize', resize, { passive: true });
            resize();

            // Universal scroll listeners: mouse wheel (even on Home screen!), chat scroll, workspace scroll, touch!
            window.addEventListener('wheel', (e) => {
                this.targetScroll += (e.deltaY || 0) * 0.0018 * this.intensity;
            }, { passive: true });

            let lastTouchY = null;
            window.addEventListener('touchstart', (e) => {
                if (e.touches && e.touches[0]) lastTouchY = e.touches[0].clientY;
            }, { passive: true });
            window.addEventListener('touchmove', (e) => {
                if (e.touches && e.touches[0] && lastTouchY !== null) {
                    const dy = lastTouchY - e.touches[0].clientY;
                    lastTouchY = e.touches[0].clientY;
                    this.targetScroll += dy * 0.004 * this.intensity;
                }
            }, { passive: true });

            const chatEl = document.getElementById('chatContainer');
            if (chatEl) {
                let prevTop = chatEl.scrollTop;
                chatEl.addEventListener('scroll', () => {
                    const d = chatEl.scrollTop - prevTop;
                    prevTop = chatEl.scrollTop;
                    this.targetScroll += d * 0.0028 * this.intensity;
                }, { passive: true });
            }

            document.addEventListener('visibilitychange', () => {
                if (!document.hidden && this.activeSpec && this.activeSpec.engine !== 'none') {
                    this.lastTs = performance.now();
                    this._ensureLoop();
                }
            });
        },

        _resize() {
            if (!this.canvas) return;
            // Cap DPR at 1.25 for crisp visuals while keeping 8GB RAM laptops cool & silky smooth
            const dpr = Math.min(1.25, window.devicePixelRatio || 1);
            const rect = this.canvas.parentElement ? this.canvas.parentElement.getBoundingClientRect() : { width: window.innerWidth, height: window.innerHeight };
            const cw = Math.max(320, Math.round((rect.width || window.innerWidth) * dpr));
            const ch = Math.max(240, Math.round((rect.height || window.innerHeight) * dpr));
            if (this.canvas.width !== cw || this.canvas.height !== ch) {
                this.canvas.width = cw;
                this.canvas.height = ch;
            }
        },

        setIntensity(val) {
            const num = Math.max(0.2, Math.min(2.2, parseFloat(val || '1.0')));
            this.intensity = Number.isFinite(num) ? num : 1.0;
            try { localStorage.setItem('aura_wallpaper_scroll_intensity', String(this.intensity)); } catch (_) {}
            return this.intensity;
        },

        setActive(wallId) {
            this.init();
            const found = CATALOG.find(w => w.id === wallId) || CATALOG[0];
            this.activeSpec = found;
            const layer = document.getElementById('auraWallpaperLayer');
            if (!found || found.engine === 'none') {
                if (this.canvas) this.canvas.style.display = 'none';
                if (this.rafId) { cancelAnimationFrame(this.rafId); this.rafId = 0; }
                return found;
            }
            if (layer) {
                layer.style.backgroundImage = 'none';
                layer.style.opacity = '1';
            }
            if (this.canvas) {
                this.canvas.style.display = 'block';
                this._resize();
                // Render one crisp frame immediately so switching feels 0ms instant
                renderWallpaperFrame(this.ctx, this.canvas.width, this.canvas.height, found, this.timeAcc, this.smoothScroll, 0, false);
            }
            this._ensureLoop();
            return found;
        },

        hideForCustomImage() {
            if (this.canvas) this.canvas.style.display = 'none';
            if (this.rafId) { cancelAnimationFrame(this.rafId); this.rafId = 0; }
        },

        _ensureLoop() {
            if (this.rafId || !this.activeSpec || this.activeSpec.engine === 'none') return;
            this.lastTs = performance.now();
            const step = (now) => {
                this.rafId = 0;
                if (document.hidden || !this.activeSpec || this.activeSpec.engine === 'none') return;
                const dt = Math.min(0.05, Math.max(0.004, (now - this.lastTs) / 1000));
                this.lastTs = now;
                this.timeAcc += dt * 0.72;
                const prev = this.smoothScroll;
                this.smoothScroll += (this.targetScroll - this.smoothScroll) * Math.min(1, dt * 8.5);
                this.velocity = (this.smoothScroll - prev) / Math.max(0.008, dt);
                if (this.ctx && this.canvas) {
                    renderWallpaperFrame(this.ctx, this.canvas.width, this.canvas.height, this.activeSpec, this.timeAcc, this.smoothScroll, this.velocity, false);
                }
                this.rafId = requestAnimationFrame(step);
            };
            this.rafId = requestAnimationFrame(step);
        },

        getPreviewDataUrl(wallId) {
            if (this.previewCache.has(wallId)) return this.previewCache.get(wallId);
            const spec = CATALOG.find(w => w.id === wallId) || CATALOG[0];
            const c = document.createElement('canvas');
            c.width = 160;
            c.height = 96;
            const cx = c.getContext('2d', { alpha: false });
            renderWallpaperFrame(cx, 160, 96, spec, 1.4, 0.85, 0.25, true);
            const url = c.toDataURL('image/jpeg', 0.76);
            this.previewCache.set(wallId, url);
            return url;
        },
    };

    global.AURA_WALLPAPERS_100 = CATALOG;
    global.AURA_WALLPAPERS_150 = CATALOG;
    global.AuraWallpaperEngine = Engine;
})(window);
