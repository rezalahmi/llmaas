import subprocess
import sys
import time
import signal

processes = []

commands = [
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    [sys.executable, "-m", "celery", "-A", "app.tasks", "worker", "--loglevel=info"],
    [sys.executable, "-m", "app.stream_worker"],
]

try:
    for cmd in commands:
        p = subprocess.Popen(cmd)
        processes.append(p)
        time.sleep(1)

    print("✅ All services started")

    for p in processes:
        p.wait()

except KeyboardInterrupt:
    print("\n🛑 Stopping services...")
    for p in processes:
        p.send_signal(signal.SIGTERM)
