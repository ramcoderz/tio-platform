import sys
import subprocess
import time
import os
import socket

def kill_process_on_port(port):
    try:
        # Find all PIDs matching the specified port (Windows netstat)
        output = subprocess.check_output(f"netstat -aon | findstr :{port}", shell=True).decode()
        pids = set()
        for line in output.strip().split('\n'):
            parts = line.strip().split()
            if len(parts) >= 5:
                pid = parts[-1]
                if pid.isdigit() and pid != "0":
                    pids.add(pid)
        for pid in pids:
            try:
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    except Exception:
        pass

def main():
    print("========================================================")
    print("[SYSTEM] Initializing TiO Platform Launcher...")
    print("========================================================")

    # 1. Clean up any existing stale processes on ports 8000 and 5173
    kill_process_on_port(8000)
    kill_process_on_port(5173)

    # Determine command paths
    python_exe = sys.executable
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"

    # 2. Launch FastAPI Backend
    print("[SYSTEM] Starting backend...")
    backend_env = os.environ.copy()
    backend_env["PYTHONUNBUFFERED"] = "1"
    backend_proc = subprocess.Popen(
        [python_exe, "-u", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"],
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=backend_env
    )

    # Give backend 2 seconds to bind port
    time.sleep(2.0)

    # 3. Launch React Frontend
    print("[SYSTEM] Starting frontend...")
    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd="frontend",
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=os.environ.copy()
    )

    # Give services a brief moment to boot and output logs before rendering menu
    time.sleep(2.0)

    print("\n========================================================")
    print("[SYSTEM] TiO running successfully")
    print("========================================================")
    print("  ->  Frontend:  http://localhost:5173/")
    print("  ->  Backend:   http://127.0.0.1:8000/")
    print("  ->  Swagger:   http://127.0.0.1:8000/docs")
    print("========================================================")
    print("Press Ctrl+C to shutdown")
    print("========================================================")

    try:
        while True:
            # Monitor backend and frontend processes to ensure they stay active
            if backend_proc.poll() is not None:
                print("\n[FATAL] Backend process exited unexpectedly!", flush=True)
                break
            if frontend_proc.poll() is not None:
                print("\n[FATAL] Frontend process exited unexpectedly!", flush=True)
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

    # 4. Graceful & Resilient Shutdown Sequence
    print("\n[SYSTEM]")
    print("Shutdown requested")

    print("\n[SYSTEM]")
    print("Stopping backend...")
    if backend_proc.poll() is None:
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            backend_proc.kill()

    print("\n[SYSTEM]")
    print("Stopping frontend...")
    if frontend_proc.poll() is None:
        frontend_proc.terminate()
        try:
            frontend_proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            frontend_proc.kill()

    print("\n[SYSTEM]")
    print("Cleaning ports...")
    # Force clean ports to prevent any lingering kernel/zombie locks
    kill_process_on_port(8000)
    kill_process_on_port(5173)

    print("\n[SYSTEM]")
    print("TiO stopped successfully")
    print("========================================================")

if __name__ == "__main__":
    main()
