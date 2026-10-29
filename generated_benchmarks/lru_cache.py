class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # Map key -> Node
        # Dummy head and tail nodes to simplify list operations
        self.head = Node(0, 0)
        self.tail = Node(0, 0)
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: Node):
        """Remove an existing node from the linked list."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_front(self, node: Node):
        """Add node right after head (most recently used)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: int) -> int:
        if key in self.cache:
            node = self.cache[key]
            self._remove(node)
            self._add_to_front(node)
            return node.value
        return -1

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self._remove(self.cache[key])
        
        new_node = Node(key, value)
        self._add_to_front(new_node)
        self.cache[key] = new_node
        
        if len(self.cache) > self.capacity:
            # Remove the least recently used node (before tail)
            lru_node = self.tail.prev
            self._remove(lru_node)
            del self.cache[lru_node.key]

# --- Testing the implementation ---
if __name__ == "__main__":
    lru = LRUCache(2)
    lru.put(1, 1)
    lru.put(2, 2)
    print(f"Get 1: {lru.get(1)}") # Returns 1
    lru.put(3, 3)                # Evicts key 2
    print(f"Get 2: {lru.get(2)}") # Returns -1 (not found)
    lru.put(4, 4)                # Evicts key 1
    print(f"Get 1: {lru.get(1)}") # Returns -1
    print(f"Get 3: {lru.get(3)}") # Returns 3
    print(f"Get 4: {lru.get(4)}") # Returns 4
