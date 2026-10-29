import winreg
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RegistryReader")

def read_registry_key(root, subkey_path, value_name):
    """
    Safely reads a value from the Windows Registry.
    
    :param root: e.g., winreg.HKEY_LOCAL_MACHINE
    :param subkey_path: Path to the key, e.g., 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
    :param value_name: The name of the value to read
    """
    try:
        # Open the key with READ access (KEY_READ)
        with winreg.OpenKey(root, subkey_path, 0, winreg.KEY_READ) as key:
            # Query the value
            value, reg_type = winreg.QueryValueEx(key, value_name)
            return value, reg_type
    except FileNotFoundError:
        logger.error(f"Registry key not found: {subkey_path}")
        return None, None
    except PermissionError:
        logger.error(f"Access denied to registry key: {subkey_path}")
        return None, None
    except Exception as e:
        logger.error(f"Error reading registry: {e}")
        return None, None

def list_subkey_names(root, subkey_path):
    """Safely lists all subkeys of a registry key."""
    subkeys = []
    try:
        with winreg.OpenKey(root, subkey_path, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    subkeys.append(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break
        return subkeys
    except Exception as e:
        logger.error(f"Error listing subkeys: {e}")
        return []

# --- Example Usage ---
if __name__ == "__main__":
    # Example: Check the Windows version
    path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    name = "ProductName"
    
    val, _ = read_registry_key(winreg.HKEY_LOCAL_MACHINE, path, name)
    if val:
        print(f"Product Name: {val}")

    # Example: List subkeys
    subkeys = list_subkey_names(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE")
    print(f"First 5 subkeys in SOFTWARE: {subkeys[:5]}")
