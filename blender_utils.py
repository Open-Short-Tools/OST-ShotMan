# blender_utils.py
import subprocess
import json
import os

def get_blender_file_info(blend_file_path, blender_executable_path):
    """
    Verifies if a .blend file can be opened by Blender without error.
    Returns a dictionary indicating success or failure.
    This function is designed to be lightweight, performing no data extraction.
    """
    if not os.path.exists(blender_executable_path):
        return {"error": f"Blender executable not found at: {blender_executable_path}"}
    if not os.path.exists(blend_file_path):
        return {"error": f"Blend file not found: {blend_file_path}"}

    # This script will be executed by Blender. It will simply open the file and quit.
    # No data extraction is performed to make it lightweight.
    blender_script = f"""
import bpy
# Open the file and immediately quit, without saving.
# This will trigger any load errors if the file is corrupted.
bpy.ops.wm.quit_blender()
    """

    try:
        # Command to run Blender in background mode, execute script, and exit
        command = [
            blender_executable_path,
            "-b",               # Run in background
            blend_file_path,    # The .blend file to open
            "--python-expr",    # Execute the following Python expression
            blender_script,
        ]
        # print(f"Executing command: {' '.join(command)}") # For debugging

        # Use subprocess.run for better error handling and capturing output
        # check=True will raise CalledProcessError if Blender exits with a non-zero code
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='ignore'
        )

        # If we reach here, it means Blender ran and exited successfully (check=True)
        # We don't expect any JSON output, so we return a success status.
        return {"status": "File opened successfully in Blender (lightweight check)."}

    except subprocess.CalledProcessError as e:
        # Blender exited with an error (e.g., file corrupted, script error)
        return {"error": f"Blender failed to open file or execute script. Error code: {e.returncode}. Stderr: {e.stderr.strip()}"}
    except FileNotFoundError:
        # This typically means blender_executable_path was not found
        return {"error": f"Blender executable not found at: {blender_executable_path}"}
    except Exception as e:
        # Catch any other unexpected errors
        return {"error": f"An unexpected error occurred during Blender file check: {e}"}
