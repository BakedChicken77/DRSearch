import subprocess
import time
import platform

def run_api_server(python_script: str):
    try:
        if platform.system() == 'Windows':
            # Using start command to open a new terminal and run poetry to start the script
            subprocess.Popen(['start', 'cmd', '/k', f'poetry run python {python_script}'], shell=True)
        else:
            # For Unix-like systems (Linux, macOS), use appropriate terminal command
            subprocess.Popen(['gnome-terminal', '--', 'poetry', 'run', 'python', python_script])

        print("API server started in a new terminal.")
    except Exception as e:
        print(f"Failed to start API server: {e}")

if __name__ == "__main__":
    script_path = '.\\plotly_project\\api_server_weaviate.py'
    run_api_server(script_path)
