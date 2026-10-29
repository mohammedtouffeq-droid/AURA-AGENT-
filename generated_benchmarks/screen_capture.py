import ctypes
from ctypes import wintypes
import time

# Using GDI (Graphics Device Interface) to capture screen
# Note: DXGI is faster but significantly more complex (requires COM/D3D).
# GDI is the standard way for quick, agent-based screenshots.

def capture_screen_gdi(filename="screenshot.bmp"):
    # Load user32 and gdi32
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    # Get primary monitor desktop dimensions
    # For multi-monitor, GetSystemMetrics(SM_CXVIRTUALSCREEN) works for full desktop
    width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    height = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
    left = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    top = user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN

    # Create handles
    h_dc = user32.GetDC(None)
    h_mem_dc = gdi32.CreateCompatibleDC(h_dc)
    h_bitmap = gdi32.CreateCompatibleBitmap(h_dc, width, height)
    gdi32.SelectObject(h_mem_dc, h_bitmap)

    # BitBlt from screen to memory
    gdi32.BitBlt(h_mem_dc, 0, 0, width, height, h_dc, left, top, 0x00CC0020)

    # Save to file (simplified BMP header writing for demonstration)
    # In a real agent, we'd use PIL or OpenCV to write the image
    print(f"Captured virtual screen area: {width}x{height} starting at ({left}, {top})")

    # Cleanup
    gdi32.DeleteObject(h_bitmap)
    gdi32.DeleteDC(h_mem_dc)
    user32.ReleaseDC(None, h_dc)

if __name__ == "__main__":
    start = time.perf_counter()
    capture_screen_gdi()
    print(f"GDI capture took {time.perf_counter() - start:.4f}s")
