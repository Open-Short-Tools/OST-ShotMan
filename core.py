# core.py
import os
import shutil
import re

# CUSTOM_METADATA_SUBDIR is still needed to construct paths for metadata files
CUSTOM_METADATA_SUBDIR = "_custom_meta"

def list_shots(shot_directory): # Add shot_directory parameter
    """Lists all Blender shot files in the specified directory."""
    if not os.path.exists(shot_directory):
        return [] # Return empty list if directory doesn't exist yet
    blend_files = [f for f in os.listdir(shot_directory) if f.endswith('.blend') and not f.startswith('cam_template_')]
    return sorted(blend_files)

def create_new_shot(base_name, shot_directory): # Add shot_directory parameter
    """Creates an initial Blender shot file with version 01."""
    os.makedirs(shot_directory, exist_ok=True)
    filename = f"{base_name}_v01.blend"
    full_path = os.path.join(shot_directory, filename)
    if os.path.exists(full_path):
        raise FileExistsError(f"Shot '{filename}' already exists.")
    # Create an empty Blender file (or copy a minimal template if you have one)
    # For simplicity, let's create an empty dummy file for now.
    # In a real Blender app, you'd probably copy a base template.
    try:
        with open(full_path, 'w') as f:
            f.write("BLENDER_FILE_PLACEHOLDER") # This will be replaced by a real Blender file
    except Exception as e:
        raise IOError(f"Failed to create dummy Blender file at {full_path}: {e}")
    return filename

def create_new_shot_from_template(base_name, template_label, template_path, shot_directory): # Add shot_directory parameter
    """Creates a new shot by copying a specified template file."""
    os.makedirs(shot_directory, exist_ok=True)
    # Ensure the templates subdirectory exists if it's within shot_directory structure
    # This assumes templates are in a 'templates' subfolder directly under the shot_directory
    template_dir = os.path.join(shot_directory, "templates")
    # If template_path is not directly under shot_directory/templates,
    # you might need to adjust how template_path is determined or ensure it's absolute.
    # For this example, we assume template_path is the full path to the template file.

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found at: {template_path}")

    # The new shot file name will be base_name_v01.blend
    new_shot_filename = f"{base_name}_v01.blend"
    destination_path = os.path.join(shot_directory, new_shot_filename)

    if os.path.exists(destination_path):
        raise FileExistsError(f"Shot '{new_shot_filename}' already exists at '{shot_directory}'.")

    try:
        shutil.copy2(template_path, destination_path)
        # You might want to run a Blender script here to clear existing data,
        # but for now, a direct copy is sufficient for the file creation part.
        return new_shot_filename
    except Exception as e:
        raise Exception(f"Error copying template to new shot: {e}")


def duplicate_shot(original_filename, shot_directory): # Add shot_directory parameter
    """Duplicates an existing Blender shot file, incrementing its version number."""
    match = re.match(r"^(.*)_v(\d{2})\.blend$", original_filename)
    if not match:
        raise ValueError(f"Filename '{original_filename}' does not match expected versioning pattern (NAME_vXX.blend).")

    base_name = match.group(1)
    current_version = int(match.group(2))
    next_version = current_version + 1
    new_filename = f"{base_name}_v{next_version:02d}.blend"

    original_path = os.path.join(shot_directory, original_filename)
    new_path = os.path.join(shot_directory, new_filename)

    if not os.path.exists(original_path):
        raise FileNotFoundError(f"Original shot file not found: {original_path}")
    if os.path.exists(new_path):
        raise FileExistsError(f"Target file '{new_filename}' already exists. Please choose a different versioning strategy or delete the existing one.")

    try:
        shutil.copy2(original_path, new_path)
        return new_filename
    except Exception as e:
        raise Exception(f"Failed to duplicate shot '{original_filename}' to '{new_filename}': {e}")


def delete_shot(filename, shot_directory): # Add shot_directory parameter
    """Deletes a Blender shot file."""
    full_path = os.path.join(shot_directory, filename)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Shot file not found: {full_path}")
    try:
        os.remove(full_path)
    except Exception as e:
        raise Exception(f"Failed to delete shot '{filename}': {e}")
