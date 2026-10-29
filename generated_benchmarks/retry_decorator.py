import time
import random
import functools
import logging
from typing import Callable, Iterable, Type, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RetryDecorator")

def retry_with_backoff(
    exceptions: Iterable[Type[Exception]] = (Exception,),
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True
):
    """
    Decorator for retrying a function with exponential backoff and jitter.
    
    :param exceptions: Tuple of exception types to catch and retry on.
    :param max_retries: Maximum number of retry attempts.
    :param base_delay: Initial delay in seconds.
    :param max_delay: Maximum delay in seconds.
    :param jitter: Whether to add randomness to the delay (helps avoid thundering herd).
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            delay = base_delay
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except tuple(exceptions) as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Max retries ({max_retries}) reached. Raising last exception.")
                        raise e
                    
                    # Exponential backoff: delay = base * (2 ^ attempt)
                    # Add jitter: random(0, delay)
                    sleep_time = min(max_delay, delay)
                    if jitter:
                        sleep_time = random.uniform(0, sleep_time)
                    
                    logger.warning(
                        f"Attempt {retries} failed: {e}. Retrying in {sleep_time:.2f}s..."
                    )
                    
                    time.sleep(sleep_time)
                    delay *= 2  # Exponential growth
            return func(*args, **kwargs)
        return wrapper
    return decorator

# --- Example Usage ---

@retry_with_backoff(
    exceptions=(ConnectionError, TimeoutError), 
    max_retries=3, 
    base_delay=0.5
)
def unstable_network_call():
    print("Attempting connection...")
    if random.random() < 0.7:  # 70% chance to fail
        raise ConnectionError("Network connection lost!")
    return "Success!"

if __name__ == "__main__":
    try:
        result = unstable_network_call()
        print(f"Final Result: {result}")
    except Exception as e:
        print(f"Function failed after retries: {e}")
