"""
===================================================================================
                     AURA AGENT - INTERACTIVE TERMINAL CONSOLE
===================================================================================
Interactive live console to chat and give autonomous commands to AURA.
Author: Mohammed Touffeq & Antigravity
===================================================================================
"""

import sys
from aura_brain import AuraBrain

def main():
    print("=" * 65)
    print("        AURA AGENT - NEXT-GEN AUTONOMOUS INTERFACE")
    print("                 Created by Mohammed Touffeq")
    print("=" * 65)
    print("[*] Engine Status : ACTIVE (Gemini 3.1 Next-Gen Brain Online)")
    print("[*] Hardware Tools: PowerShell, Browser, Code Editor, File I/O")
    print("[*] Type 'exit' or 'quit' to close console.")
    print("-" * 65)

    brain = AuraBrain()

    while True:
        try:
            user_input = input("\nYou > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("\n[*] Shutting down AURA Console. Goodbye!")
                break

            print("\n[AURA Thinking & Working...]")
            reply = brain.think_and_act(user_input)
            print(f"\nAURA > {reply}")

        except KeyboardInterrupt:
            print("\n\n[*] Interrupted. Exiting AURA Console.")
            break
        except Exception as e:
            print(f"\n[Error]: {e}")

if __name__ == "__main__":
    main()
