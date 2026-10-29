import queue
import threading
import time
import logging
import signal

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(threadName)s: %(message)s')

class ProducerConsumerQueue:
    def __init__(self, max_size=100):
        self.queue = queue.Queue(maxsize=max_size)
        self.shutdown_event = threading.Event()
        self.producers = []
        self.consumers = []

    def producer(self, name):
        """Producer adds items to the queue."""
        count = 0
        while not self.shutdown_event.is_set():
            try:
                item = f"Data-{count}"
                # Put with timeout to allow checking shutdown_event frequently
                self.queue.put(item, timeout=0.5)
                logging.info(f"Produced {item}")
                count += 1
                time.sleep(0.1) # Simulate work
            except queue.Full:
                continue
        logging.info("Producer shutting down.")

    def consumer(self, name):
        """Consumer retrieves items from the queue."""
        while not self.shutdown_event.is_set() or not self.queue.empty():
            try:
                # Use a timeout so we can periodically check the shutdown_event
                item = self.queue.get(timeout=0.5)
                logging.info(f"Consumed {item}")
                self.queue.task_done()
                time.sleep(0.2) # Simulate processing
            except queue.Empty:
                continue
        logging.info("Consumer shutting down.")

    def start(self, num_producers=2, num_consumers=3):
        for i in range(num_producers):
            t = threading.Thread(target=self.producer, args=(f"P{i}",), name=f"Producer-{i}")
            self.producers.append(t)
            t.start()
        
        for i in range(num_consumers):
            t = threading.Thread(target=self.consumer, args=(f"C{i}",), name=f"Consumer-{i}")
            self.consumers.append(t)
            t.start()

    def stop(self):
        logging.info("Shutdown signal received...")
        self.shutdown_event.set()
        for t in self.producers + self.consumers:
            t.join()
        logging.info("All threads stopped.")

# --- Execution ---
if __name__ == "__main__":
    pq = ProducerConsumerQueue()
    
    # Handle Ctrl+C
    def signal_handler(sig, frame):
        pq.stop()
        exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    pq.start()
    
    # Run for a few seconds then shut down automatically
    time.sleep(3)
    pq.stop()
