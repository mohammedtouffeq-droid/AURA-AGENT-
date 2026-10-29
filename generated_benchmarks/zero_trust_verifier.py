import os
import subprocess
import shlex
import logging

# Configure logging for security auditing
logging.basicConfig(level=logging.INFO, format='%(asctime)s - SECURITY - %(message)s')

class ZeroTrustCommandVerifier:
    """
    A simple zero-trust gatekeeper for terminal commands.
    Follows 'Principle of Least Privilege' (PoLP).
    """
    def __init__(self, allowed_commands=None):
        # Whitelist approach: only allow explicitly trusted binaries
        self.allowed_commands = allowed_commands or {
            'ls': '/bin/ls',
            'cat': '/bin/cat',
            'git': '/usr/bin/git'
        }

    def verify_and_execute(self, command_str):
        # 1. Sanitization: Parse command safely
        parts = shlex.split(command_str)
        if not parts:
            return "Empty command"
        
        command = parts[0]

        # 2. Authorization: Check against whitelist
        if command not in self.allowed_commands:
            logging.error(f"Unauthorized command attempted: {command}")
            return f"PERMISSION DENIED: {command} is not whitelisted."

        # 3. Contextual Inspection: Ensure no dangerous flags or path traversals
        # Example: Reject 'cat' if it tries to read sensitive files
        if command == 'cat':
            for arg in parts[1:]:
                if '/etc/shadow' in arg or '..' in arg:
                    logging.warning(f"Malicious file access attempt: {arg}")
                    return "PERMISSION DENIED: Prohibited file access."

        # 4. Secure Execution
        try:
            logging.info(f"Executing verified command: {command_str}")
            result = subprocess.run(parts, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Command failed: {e.stderr}"

# --- Example Usage ---
if __name__ == "__main__":
    verifier = ZeroTrustCommandVerifier()
    
    # Allowed
    print(verifier.verify_and_execute("ls -la"))
    
    # Denied (Not whitelisted)
    print(verifier.verify_and_execute("rm -rf /"))
    
    # Denied (Path traversal/Sensitive file)
    print(verifier.verify_and_execute("cat /etc/shadow"))
