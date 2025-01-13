import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import sys
import signal
import os


class Watcher:
    def __init__(self):
        self.observer = Observer()
        self.process = None

    def kill_existing_process(self):
        """
        Kill any process currently running on port 5000.
        """
        try:
            result = subprocess.run(
                ["lsof", "-t", "-i:5000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.stdout:
                for pid in result.stdout.strip().split('\n'):
                    print(f"Terminating process {pid} on port 5000...")
                    os.kill(int(pid), signal.SIGTERM)
                    time.sleep(1)  # Allow time for graceful shutdown
        except Exception as e:
            print(f"Error killing process on port 5000: {e}")

    def run_server(self):
        """
        Start or restart the FastAPI server pointing to `src/main.py`.
        """
        # Properly terminate the existing process
        if self.process:
            print("Terminating existing server process...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Force killing the server process...")
                os.kill(self.process.pid, signal.SIGKILL)

        # Ensure the port is free before starting a new process
        self.kill_existing_process()

        # Update the server path to point to main.py
        server_path = "src/main.py"
        if not os.path.exists(server_path):
            print(f"Error: {server_path} does not exist. Please check the path.")
            return

        print(f"Starting server process with {server_path}...")
        self.process = subprocess.Popen(
            [sys.executable, server_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    class Handler(FileSystemEventHandler):
        def __init__(self, watcher):
            self.watcher = watcher

        def on_modified(self, event):
            """
            Restart the server if a Python file is modified.
            """
            if event.src_path.endswith('.py'):
                print(f'File {event.src_path} has been modified')
                self.watcher.run_server()

    def start(self):
        """
        Start the file watcher and initial server process.
        """
        event_handler = self.Handler(self)
        self.observer.schedule(event_handler, 'src/', recursive=True)
        self.observer.start()
        self.run_server()  # Initial server startup
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping observer...")
            self.observer.stop()
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("Force killing server process on exit...")
                    os.kill(self.process.pid, signal.SIGKILL)

        self.observer.join()


if __name__ == "__main__":
    watcher = Watcher()
    watcher.start()
