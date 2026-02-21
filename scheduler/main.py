import asyncio
import os
from prometheus_client import start_http_server
from .leader_election import RedisLeaderElection, HEARTBEAT_INTERVAL
from .job_assigner import run_assignment_loop
from .recovery import run_recovery_loop

SCHEDULER_CONSUMER = os.getenv("HOSTNAME", "scheduler-1")


async def main():
    print(f"Scheduler {SCHEDULER_CONSUMER} starting...", flush=True)

    try:
        start_http_server(8000)
        print("Metrics server started on port 8000", flush=True)
    except Exception as e:
        print(f"Failed to start metrics server: {e}", flush=True)
        import sys
        sys.exit(1)

    election = RedisLeaderElection(instance_id=SCHEDULER_CONSUMER)

    while True:
        try:
            print("Attempting to become leader...")
            is_leader = await election.acquire()

            if is_leader:
                print(f"I am the LEADER ({SCHEDULER_CONSUMER}). Starting scheduler loop...")

                scheduler_task = asyncio.create_task(run_assignment_loop())
                reconcile_task = asyncio.create_task(run_recovery_loop())

                try:
                    while True:
                        refreshed = await election.refresh()
                        if not refreshed:
                            print("Lost leadership lock!")
                            break
                        await asyncio.sleep(HEARTBEAT_INTERVAL)
                except Exception as e:
                    print(f"Error maintaining leadership: {e}")
                finally:
                    print("Stopping scheduler loop...")
                    scheduler_task.cancel()
                    reconcile_task.cancel()
                    try:
                        await scheduler_task
                        await reconcile_task
                    except asyncio.CancelledError:
                        pass
            else:
                print(f"I am a FOLLOWER ({SCHEDULER_CONSUMER}). Leader is active.")
                await asyncio.sleep(5)

        except Exception as e:
            print(f"Leader Election Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Scheduler stopping...")
