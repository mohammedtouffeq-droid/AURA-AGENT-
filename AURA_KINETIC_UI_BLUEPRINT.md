# AURA AGENT - KINETIC UI/UX MASTER BLUEPRINT
**Architectural Specification & ChatGPT Frontend Build Prompt**  
*Creator: Mohammed Touffeq | Architecture: Kinetic Liquid Cyberpunk*

---

## 🎨 1. Design Vision: "The Living AI Artifact"

AURA is NOT a boring, flat, static chat box like ChatGPT or Claude. AURA is a living, breathing holographic workstation with continuous kinetic motion.

### Core Visual Pillars:
1. **Living AI Core (Central Pulsating Hologram Orb):**
   * An animated 3D/Canvas orb in the center with shimmering particle rings.
   * **Reactive States:**
     * 🟢 *Neon Emerald & Cyan (#00FFCC)*: Idle / Listening / Ready.
     * 🟣 *Plasma Violet (#9D00FF)*: Brain Thinking & Reasoning.
     * 🟡 *Solar Gold (#FFD700)*: Tool Execution (Running PowerShell, Scraping Web, Writing Files).
     * 🔴 *Crimson Red (#FF0055)*: Security Guardrail / Intervention Alert.

2. **Liquid Ambient Motion Background:**
   * Gentle, undulating fluid mesh gradients that shift and flow smoothly across the dark viewport (no harsh flashing, organic fluid movement).

3. **Ultra-Refined Glassmorphism:**
   * Translucent frosted glass containers (`backdrop-filter: blur(20px)`), subtle 1px neon borders, and micro-glow box shadows.

4. **Sliding Kinetic Settings Drawer:**
   * A side drawer that slides in with spring-damped physics.
   * Full control over Models (Gemini 3.1, GPT-4o, Claude, Ollama), Security (Auto-Pilot vs Ask-First), Memory inspection, and Theme color adjustments.

---

## 📋 2. Comprehensive Settings System Architecture (Mapped from Top 15 Models)

AURA's settings engine (`aura_settings.py` & `aura_config.json`) controls 5 distinct categories:

| Category | Controls | Inspired By |
|---|---|---|
| **1. Brain & Reasoning** | Active Model Switcher, Temperature Slider (0.0 to 1.0), Thinking Budget (Low, Medium, Deep, Maximum), Custom System Persona. | ChatGPT & Claude 3.5 |
| **2. Security & Auto-Pilot** | Mode Toggle (`Auto-Pilot` vs `Ask-First`), Browser Visibility (`Visible Chrome` vs `Headless`), Destructive Action Guardrails. | Cursor AI & Open-Interpreter |
| **3. Memory & Identity** | View Stored SQLite Facts, Recall Switch, Export Memories, Wipe Memory Button. | ChatGPT Memory & LlamaIndex |
| **4. Hardware & Speed** | Max Autonomous Turns (1-15), Connection Keep-Alive, Offline Local Endpoint (Ollama). | LM Studio & Ollama |
| **5. Kinetic Aesthetics** | Particle Flow Speed (Calm, Smooth, Hyper), Ambient Wave Toggle, Accent Color Picker (Cyan, Violet, Gold, Emerald). | AURA Custom Identity |

---

## 🚀 3. PROMPT TO GIVE CHATGPT (Copy-Paste Ready)

> **Copy everything below this line and give it directly to ChatGPT:**

```markdown
Bhai ChatGPT, suno: Hum Mohammed Touffeq ke flagship project "AURA AGENT" ke liye duniya ka sabse khoobsurat, modern aur kinetic animated UI/UX frontend create kar rahe hain. 

Mujhe koi boring flat black/blue standard design nahi chahiye. AURA ek "Living AI Artifact" jaisa dikhna chahiye jisme colors aur particles continuously move kar rahe hon.

Yahan complete technical requirements hain:

### 1. Visual Aesthetics & Animations (Liquid Cyberpunk):
- Background: Deep void space (#0A0A0F) with floating, undulating liquid gradient meshes (ambient glow moving between Neon Cyan #00FFCC and Plasma Violet #9D00FF).
- Central AI Core Orb: An animated glowing, pulsating circular orb that breathes and ripples. When AURA is thinking, it swirls in violet; when executing tools, it sends out gold particle waves.
- Glassmorphism Panels: Frosted glass containers (backdrop-filter: blur(20px), border: 1px solid rgba(0, 255, 204, 0.15), border-radius: 16px).

### 2. Main Layout Sections:
1. Top Navigation Bar:
   - AURA glowing logo with version tag "v4.0 Universe".
   - Status Indicator: "Gemini 3.1 Next-Gen Brain [CONNECTED]".
   - Action buttons: "Settings (Gear Icon)", "Memory Inspector (Brain Icon)", "Terminal Logs (Terminal Icon)".

2. Central Command & Chat Hub:
   - Floating chat message stream with distinct styling for User (Glass Cyan) and AURA (Glass Violet).
   - Tool Execution Badges: Visual glowing pills appearing when AURA executes tools (e.g., "[⚡ PowerShell: hostname]", "[🌐 Browser: Google Opened]", "[💾 Memory Saved]").
   - Bottom Floating Command Bar: Modern input pill with Mic button, Send button, and auto-expanding textarea.

3. Interactive Kinetic Settings Drawer (Modal / Sidebar):
   - Opens smoothly with spring physics from the right.
   - Connected to AURA's settings schema:
     * Model Selector Dropdown: Gemini 3.1 Flash-Lite, Gemini 2.5 Pro, GPT-4o, Claude 3.5, Ollama Llama-3.
     * Temperature Slider: 0.0 (Strict Code) to 1.0 (Creative).
     * Execution Mode Toggle: "Auto-Pilot (Full Autonomous)" vs "Ask-First (Confirm Actions)".
     * Browser Visibility Switch: "Visible Browser" vs "Headless Silent".
     * Memory Database Viewer: Table showing stored facts with delete buttons.
     * Accent Color Theme Picker: Neon Cyan, Plasma Violet, Solar Gold, Cyber Emerald.

### 3. Deliverable:
Create a complete, responsive, self-contained, single-file frontend (`index.html` with embedded CSS and modern JavaScript) or React/Tailwind component that I can run immediately in my browser or package into Electron/Desktop app. Use pure CSS animations, canvas particles, and smooth transitions. Make it breathtaking!
```
