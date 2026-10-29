import ctypes
import time

# Define the MEMORYSTATUSEX structure
class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]

    def __init__(self):
        super().__init__()
        self.dwLength = ctypes.sizeof(self)

def get_memory_usage():
    stat = MEMORYSTATUSEX()
    # Call the Win32 API
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    
    # Convert bytes to Gigabytes
    total_gb = stat.ullTotalPhys / (1024**3)
    avail_gb = stat.ullAvailPhys / (1024**3)
    return total_gb, avail_gb

if __name__ == "__main__":
    # Measure latency of the call
    start_time = time.perf_counter_ns()
    
    total, avail = get_memory_usage()
    
    end_time = time.perf_counter_ns()
    
    latency_us = (end_time - start_time) / 1000
    
    print(f"Total Physical RAM: {total:.2f} GB")
    print(f"Available Physical RAM: {avail:.2f} GB")
    print(f"Call latency: {latency_us:.2f} microseconds")
