import subprocess
import time

class DockerExecutor:
    def __init__(self):
        pass

    def run_job(self, image: str, command: list, script_content: str = None):
        """
        Runs a job using local docker CLI via subprocess.
        Returns (exit_code, logs).
        """
        # command list to string for CLI (simplified)
        # In real usage, be careful with shell escaping
        # but docker run [image] [command...] works well
        
        print(f"[{image}] Starting job: {command} (Script: {bool(script_content)})")
        
        # We'll use --rm to cleanup
        if script_content:
             # Run python script via stdin
             # image should be a python image or contain python
             cmd = ["docker", "run", "--rm", "-i", image, "python", "-"]
             input_data = script_content
        else:
             cmd = ["docker", "run", "--rm", image] + command
             input_data = None
        
        try:
            # Capture stdout/stderr
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                check=False # Don't raise on non-zero exit
            )
            
            logs = result.stdout + "\n" + result.stderr
            return result.returncode, logs

        except Exception as e:
            print(f"Error running job: {e}")
            return 1, str(e)
