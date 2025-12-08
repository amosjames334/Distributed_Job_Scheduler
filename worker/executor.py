import subprocess
import time

class DockerExecutor:
    def __init__(self):
        pass

    def run_job(self, image: str, command: list):
        """
        Runs a job using local docker CLI via subprocess.
        Returns (exit_code, logs).
        """
        # command list to string for CLI (simplified)
        # In real usage, be careful with shell escaping
        # but docker run [image] [command...] works well
        
        print(f"[{image}] Starting job: {command}")
        
        # We'll use --rm to cleanup
        cmd = ["docker", "run", "--rm", image] + command
        
        try:
            # Capture stdout/stderr
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False # Don't raise on non-zero exit
            )
            
            logs = result.stdout + "\n" + result.stderr
            return result.returncode, logs

        except Exception as e:
            print(f"Error running job: {e}")
            return 1, str(e)
