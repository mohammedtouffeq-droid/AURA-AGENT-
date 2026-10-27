# AURA AGENT (Autonomous Universal Robotics & Automation)

> **Next-Generation Autonomous Super-Agent Framework**  
> Unified orchestration combining 5 world-class open-source AI engines into a single master control system.

---

## 🌟 Architecture & The 5 Core Engines

AURA bridges and orchestrates the top 5 open-source AI projects:

| Engine | Upstream Repository | Role in AURA |
|---|---|---|
| **OS & Desktop Engine** | [`open-interpreter/open-interpreter`](https://github.com/openinterpreter/open-interpreter) | Native PowerShell execution, screen inspection, mouse & keyboard automation |
| **Web Browser Engine** | [`browser-use/browser-use`](https://github.com/browser-use/browser-use) | Headless and headful Chrome/Edge automation, DOM navigation, web workflows |
| **Autonomous Coding** | [`Aider-AI/aider`](https://github.com/Aider-AI/aider) | Real-time code editing, AST syntax validation, targeted patch diffing |
| **Agent Swarm Planner** | [`crewAIInc/crewAI`](https://github.com/crewAIInc/crewAI) | Multi-agent task decomposition, ReAct reasoning loop, memory state machine |
| **Universal Model Router** | [`BerriAI/litellm`](https://github.com/BerriAI/litellm) | Universal abstraction connecting local models (Ollama/Llama 3) and cloud LLMs |

---

## 🚀 Quick Start

### 1. Initialize & Verify All 5 Engines
```bash
python aura_agent.py
```

### 2. File Structure
```text
AURA-Agent/
├── aura_agent.py            # Master Controller & Engine Bridges
├── REPOSITORIES_PROOF.md    # Metrics, GitHub stars, and upstream references
├── setup_engines.py        # Automated engine sync & verification tool
└── engines/                # Cloned and mounted upstream source codebases
    ├── open-interpreter/
    ├── browser-use/
    ├── aider/
    ├── crewAI/
    └── litellm/
```

---

## 🛡️ License & Attribution
All integrated upstream engines are open-source and governed by their respective licenses (MIT / Apache 2.0).
Developed by **Mohammed Touffeq** with Antigravity.
