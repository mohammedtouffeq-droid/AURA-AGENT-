import psutil
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def kill_orphaned_children(parent_pid):
    """
    Finds and kills all child processes of a given parent PID.
    Orphaned processes are defined here as any process whose 
    parent is the specified PID.
    """
    try:
        parent = psutil.Process(parent_pid)
        children = parent.children(recursive=True)
        
        if not children:
            logging.info(f"No child processes found for PID {parent_pid}")
            return

        for child in children:
            logging.warning(f"Terminating orphaned process: {child.name()} (PID: {child.pid})")
            child.terminate()

        # Wait for processes to exit
        gone, alive = psutil.wait_procs(children, timeout=3)
        
        for p in alive:
            logging.error(f"Process {p.pid} refused to die. Force killing.")
            p.kill()
            
    except psutil.NoSuchProcess:
        logging.error(f"Parent PID {parent_pid} does not exist.")
    except Exception as e:
        logging.error(f"Error during reaping: {e}")

if __name__ == "__main__":
    # Example: Kill children of the current process (if any)
    # or replace with a specific target PID
    current_pid = os.getpid()
    logging.info(f"Reaping children of current PID: {current_pid}")
    kill_orphaned_children(current_pid)
