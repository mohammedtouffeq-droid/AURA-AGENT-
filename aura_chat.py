"""
===================================================================================
                     AURA AGENT - INTERACTIVE TERMINAL CONSOLE
===================================================================================
Interactive terminal client for Aura's Gemini-backed tool loop.
===================================================================================
"""

from aura_brain import AuraBrain


def main() -> None:
    brain = AuraBrain()
    configured = bool(brain.api_key.strip())

    print("=" * 65)
    print("        AURA AGENT - LOCAL TERMINAL CONSOLE")
    print("=" * 65)
    print(f"[*] Model          : {brain.model}")
    print(f"[*] API key        : {'configured' if configured else 'missing'}")
    print("[*] Connection     : not verified until the first request")
    print("[!] Tool approval  : not implemented; model-requested tools run immediately")
    print("[*] Type 'exit' or 'quit' to close the console.")
    print("-" * 65)

    while True:
        try:
            user_input = input("\nYou > ").strip()
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit", "q"}:
                print("\n[*] Shutting down AURA Console. Goodbye!")
                break

            print("\n[AURA Thinking & Working...]")
            reply = brain.think_and_act(user_input)
            print(f"\nAURA > {reply}")

        except KeyboardInterrupt:
            print("\n\n[*] Interrupted. Exiting AURA Console.")
            break
        except EOFError:
            print("\n[*] Input closed. Exiting AURA Console.")
            break


if __name__ == "__main__":
    main()
