# Aura repository inventory and verification scope

This document records what the Aura parent repository declares. It is not evidence that any upstream project has been integrated, executed, tested, or endorsed by Aura.

## Current inventory

The current .gitmodules declares 32 submodule paths. The parent repository pins a commit for each entry. Names and URLs identify their respective upstream projects:

| # | Aura path | Upstream repository |
|---:|---|---|
| 1 | engines/open-interpreter | https://github.com/OpenInterpreter/open-interpreter |
| 2 | engines/browser-use | https://github.com/browser-use/browser-use |
| 3 | engines/aider | https://github.com/Aider-AI/aider |
| 4 | engines/crewAI | https://github.com/crewAIInc/crewAI |
| 5 | engines/litellm | https://github.com/BerriAI/litellm |
| 6 | engines/langgraph | https://github.com/langchain-ai/langgraph |
| 7 | engines/agent-framework | https://github.com/microsoft/agent-framework |
| 8 | engines/openai-agents-python | https://github.com/openai/openai-agents-python |
| 9 | engines/pydantic-ai | https://github.com/pydantic/pydantic-ai |
| 10 | engines/semantic-kernel | https://github.com/microsoft/semantic-kernel |
| 11 | engines/haystack | https://github.com/deepset-ai/haystack |
| 12 | engines/llama_index | https://github.com/run-llama/llama_index |
| 13 | engines/dspy | https://github.com/stanfordnlp/dspy |
| 14 | engines/dify | https://github.com/langgenius/dify |
| 15 | engines/n8n | https://github.com/n8n-io/n8n |
| 16 | engines/activepieces | https://github.com/activepieces/activepieces |
| 17 | engines/temporal | https://github.com/temporalio/temporal |
| 18 | engines/prefect | https://github.com/PrefectHQ/prefect |
| 19 | engines/playwright-python | https://github.com/microsoft/playwright-python |
| 20 | engines/skyvern | https://github.com/Skyvern-AI/skyvern |
| 21 | engines/stagehand | https://github.com/browserbase/stagehand |
| 22 | engines/OpenHands | https://github.com/All-Hands-AI/OpenHands |
| 23 | engines/composio | https://github.com/ComposioHQ/composio |
| 24 | engines/python-sdk | https://github.com/modelcontextprotocol/python-sdk |
| 25 | engines/llama.cpp | https://github.com/ggml-org/llama.cpp |
| 26 | engines/ollama | https://github.com/ollama/ollama |
| 27 | engines/transformers | https://github.com/huggingface/transformers |
| 28 | engines/vllm | https://github.com/vllm-project/vllm |
| 29 | engines/qdrant | https://github.com/qdrant/qdrant |
| 30 | engines/pgvector | https://github.com/pgvector/pgvector |
| 31 | engines/langfuse | https://github.com/langfuse/langfuse |
| 32 | engines/phoenix | https://github.com/Arize-ai/phoenix |

Inspect the Git tree or run git submodule status in an initialized Aura checkout to see exact pinned commits.

## Verification scope

- The registry audit validates relative paths beneath engines/ and credential-free HTTPS GitHub URLs.
- At the Aura checkout root, aura_agent.py asks local Git for submodule status. It does not make a network request.
- setup_engines.py defaults to listing metadata. Explicit initialization downloads parent-pinned source; it does not run that source.
- Offline tests cover parsing, URL/path validation, and Git status markers.

This does not test upstream code, dependencies, quality, security, or compatibility between projects. A folder existing on disk is not proof of a healthy integration.

## Licensing and attribution

Each upstream project retains its own author identity, license, trademark, and notices. Terms may differ by project and by dependency. Review pinned source, licenses, notices, and redistribution obligations before distributing an Aura product. Aura-authored documentation does not transfer ownership of upstream work.

