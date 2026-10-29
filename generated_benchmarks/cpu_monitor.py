import asyncio
import psutil

async def monitor_cpu_usage(interval=1.0):
    """
    Monitors CPU usage per core without blocking the asyncio event loop.
    We use psutil.cpu_percent(interval=None, percpu=True) which is non-blocking.
    """
    print(f"{'Core':<10} | {'Usage %'}")
    print("-" * 20)
    
    # Initialize the first call to get the baseline
    psutil.cpu_percent(interval=None, percpu=True)
    
    while True:
        # Non-blocking call: interval=None makes it return instantly 
        # based on the time since the last call.
        await asyncio.sleep(interval)
        percentages = psutil.cpu_percent(interval=None, percpu=True)
        
        for i, usage in enumerate(percentages):
            print(f"Core {i:<5} | {usage:>6.1f}%")
        print("-" * 20)

async def main():
    # Run the monitoring task concurrently with other work
    print("Starting non-blocking CPU monitor...")
    await monitor_cpu_usage()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Monitoring stopped.")
