import asyncio

# The event loop prevents deadlocks by utilizing a single-threaded cooperative model.
# Unlike multi-threading where pre-emption can lead to race conditions/deadlocks,
# asyncio tasks only switch context at defined 'await' points.

async def task_a():
    print("Task A: Starting...")
    # The event loop pauses Task A here and moves to the next available task
    await asyncio.sleep(1) 
    print("Task A: Resumed and finished.")

async def task_b():
    print("Task B: Starting...")
    # The event loop pauses Task B here
    await asyncio.sleep(0.5)
    print("Task B: Resumed and finished.")

async def main():
    print("Event loop managing tasks...")
    # asyncio.gather schedules the tasks on the event loop.
    # The loop ensures one task progress while others wait on I/O.
    await asyncio.gather(task_a(), task_b())
    print("All tasks complete.")

if __name__ == "__main__":
    asyncio.run(main())
