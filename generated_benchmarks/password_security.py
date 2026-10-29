import os
import hashlib
import binascii

# We use Argon2id via the 'argon2-cffi' library (recommended)
# If you don't have it, install with: pip install argon2-cffi

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

class PasswordManager:
    def __init__(self):
        # Argon2id is the current industry standard (winner of Password Hashing Competition)
        self.ph = PasswordHasher(
            time_cost=3,        # Number of iterations
            memory_cost=65536,  # 64 MiB
            parallelism=4,      # Number of threads
            hash_len=32,
            salt_len=16
        )

    def hash_password(self, password: str) -> str:
        """Hash a password using Argon2id."""
        return self.ph.hash(password)

    def verify_password(self, hashed_password: str, password: str) -> bool:
        """Verify a password against a hash."""
        try:
            return self.ph.verify(hashed_password, password)
        except VerifyMismatchError:
            return False

# --- Example Usage ---
if __name__ == "__main__":
    pwd_mgr = PasswordManager()
    
    # User registration
    raw_password = "my_super_secure_password"
    hashed = pwd_mgr.hash_password(raw_password)
    print(f"Hashed Password: {hashed}")
    
    # Login verification
    is_valid = pwd_mgr.verify_password(hashed, "my_super_secure_password")
    print(f"Password valid: {is_valid}")
    
    # Failed login
    is_invalid = pwd_mgr.verify_password(hashed, "wrong_password")
    print(f"Wrong password valid: {is_invalid}")
