# gui.py
import os
import time
import json
import subprocess
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
from tkinter import ttk
import re
import shutil # Import shutil for file operations
import sys # Import sys to detect PyInstaller environment
from PIL import Image, ImageTk

# Import your core functions. blender_utils is no longer imported.
from core import list_shots, create_new_shot, duplicate_shot, delete_shot, create_new_shot_from_template
# Removed: from blender_utils import get_blender_file_info

CONFIG_FILE = "config.json"
CUSTOM_METADATA_SUBDIR = "_custom_meta" # Subdirectory for custom metadata JSONs

# Define the base directory for resources.
if getattr(sys, 'frozen', False):
    BASE_RESOURCE_PATH = sys._MEIPASS
else:
    BASE_RESOURCE_PATH = os.path.dirname(os.path.abspath(__file__))

DEFAULT_TEMPLATE_SOURCE_DIR = os.path.join(BASE_RESOURCE_PATH, "camera_shots", "templates")


def load_config():
    """
    Loads configuration from config.json.
    Ensures default values are present even if the file exists but is incomplete.
    """
    default_config = {
        "blender_path": "blender",
        "shot_directory": os.path.join(os.getcwd(), "camera_shots")
    }

    current_config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                current_config = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {CONFIG_FILE} is corrupted or empty. Using default configuration.")
            current_config = {} # Reset to empty if corrupted

    # Update current_config with any missing default values
    for key, value in default_config.items():
        if key not in current_config:
            current_config[key] = value

    # Save the potentially updated config back to the file to ensure it's complete
    save_config(current_config)
    return current_config

def save_config(config):
    """Saves configuration to config.json."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4) # Use indent for readability

# Load configuration at startup
config = load_config()

def ensure_shot_directories_exist(shot_dir):
    """Ensures the main shot directory and its custom metadata subdirectory exist."""
    if not isinstance(shot_dir, str):
        print(f"Warning: shot_directory is not a string ({type(shot_dir)}). Resetting to default.")
        shot_dir = os.path.join(os.getcwd(), "camera_shots")
        config["shot_directory"] = shot_dir # Update config in case it was bad
        save_config(config) # Save the corrected config
    os.makedirs(shot_dir, exist_ok=True)
    os.makedirs(os.path.join(shot_dir, CUSTOM_METADATA_SUBDIR), exist_ok=True)

# Call this at startup based on loaded config
ensure_shot_directories_exist(config["shot_directory"])


class ShotManagerGUI:
    """
    Main GUI class for the Shot Manager application.
    Manages display, creation, duplication, and deletion of Blender shot files.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("ShotMan GUI")
        self.root.geometry("900x650") # Slightly increased height for status bar
        self.root.configure(bg="#2b2b2b")

        icon_path = os.path.join(BASE_RESOURCE_PATH, "shotman.ico")
        try:
            if os.path.exists(icon_path):
                icon_image = Image.open(icon_path)
                self.photo_image = ImageTk.PhotoImage(icon_image)
                self.root.iconphoto(True, self.photo_image)
            else:
                print(f"Warning: .ico icon file not found at '{icon_path}'. Window will use default icon.")
        except Exception as e:
            print(f"Warning: Could not load .ico icon from '{icon_path}'. Error: {e}. Window will use default icon.")
            print("Please ensure Pillow is installed (pip install Pillow) and 'icon.ico' is a valid image file.")

        # Apply style
        self.style = ttk.Style()
        self.style.theme_use("clam") # 'clam' is a good modern theme
        self.style.configure("TFrame", background="#2b2b2b")
        self.style.configure("TButton", padding=5, font=("Segoe UI", 9))
        self.style.configure("TLabel", background="#2b2b2b", foreground="white", font=("Segoe UI", 9))
        self.style.configure("TNotebook", background="#2b2b2b")
        self.style.configure("TNotebook.Tab", padding=[10, 5], font=("Segoe UI", 10))
        self.style.map("TButton",
                       foreground=[('pressed', 'white'), ('active', 'white')],
                       background=[('pressed', '!focus', '#4a4a4a'), ('active', '#3a3a3a')])
        self.style.configure("TEntry", fieldbackground="#3a3a3a", foreground="white", borderwidth=0)
        self.style.configure("TCombobox", fieldbackground="#3a3a3a", foreground="white", borderwidth=0)


        # Status Bar - INITIALIZE THIS FIRST!
        self.status_bar = ttk.Label(root, text="Ready.", relief=tk.SUNKEN, anchor=tk.W, background="#3a3a3a", foreground="white")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, ipady=2)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0)) # Padding top, 0 bottom

        self.shots_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.log_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.shots_tab, text="Shots")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.log_tab, text="Log")

        self.create_log_tab()
        self.create_settings_tab()
        self.create_shots_tab() # This will call refresh, which uses status_bar, now defined.

        self.log("ShotMan GUI started.")
        self.update_status("Application ready.")

    # -------------- SHOTS TAB ------------------
    def create_shots_tab(self):
        """Initializes the UI elements for the 'Shots' tab."""
        # Top frame for sorting and filtering options
        top_frame = ttk.Frame(self.shots_tab)
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        # Search Bar
        ttk.Label(top_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = ttk.Entry(top_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 20))
        self.search_entry.bind("<KeyRelease>", self._filter_shots) # Filter on every key release

        # Sort Options
        ttk.Label(top_frame, text="Sort by:").pack(side=tk.LEFT)
        self.sort_var = tk.StringVar(value="Alphabetical (A-Z)")
        self.sort_options = ttk.Combobox(top_frame, textvariable=self.sort_var, state="readonly",
                                        values=["Alphabetical (A-Z)", "Date Created (Newest)", "Date Created (Oldest)",
                                                "File Size (Largest)", "File Size (Smallest)", "Shot Number"])
        self.sort_options.pack(side=tk.LEFT, padx=5)
        self.sort_options.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        # Main content frames
        left_frame = ttk.Frame(self.shots_tab)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        right_frame = ttk.Frame(self.shots_tab)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Shot Listbox with Scrollbar
        self.shot_listbox = tk.Listbox(left_frame, width=40, height=25, bg="#1e1e1e", fg="white", font=("Segoe UI", 10),
                                      selectbackground="#007acc", selectforeground="white", borderwidth=0, highlightthickness=0)
        self.shot_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.shot_listbox.bind("<Double-1>", self.open_in_blender)
        self.shot_listbox.bind("<<ListboxSelect>>", self.update_metadata)

        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.shot_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.shot_listbox.config(yscrollcommand=scrollbar.set)

        # Right-click context menu for the listbox
        self.listbox_menu = tk.Menu(self.shot_listbox, tearoff=0)
        self.listbox_menu.add_command(label="Open in Blender", command=self.open_in_blender_selected)
        self.listbox_menu.add_command(label="Duplicate Selected (New Version)", command=self.duplicate_selected)
        self.listbox_menu.add_command(label="Delete Selected", command=self.delete_selected)
        self.listbox_menu.add_separator()
        self.listbox_menu.add_command(label="Edit Custom Metadata", command=self.edit_custom_metadata_for_selected) # New!
        self.listbox_menu.add_command(label="Show in File Explorer", command=self.show_in_file_explorer)


        self.shot_listbox.bind("<Button-3>", self._show_listbox_context_menu) # Bind right-click

        # Buttons in the right frame
        button_frame = ttk.Frame(right_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(button_frame, text="Refresh", command=self.refresh).pack(fill="x", pady=2)
        ttk.Button(button_frame, text="Create New Shot", command=self.create_shot).pack(fill="x", pady=2)
        ttk.Button(button_frame, text="Create New Version", command=self.duplicate_selected).pack(fill="x", pady=2)
        ttk.Button(button_frame, text="Edit Custom Metadata", command=self.edit_custom_metadata_for_selected).pack(fill="x", pady=2)
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_selected).pack(fill="x", pady=2)
        ttk.Button(button_frame, text="Show in File Explorer", command=self.show_in_file_explorer).pack(fill="x", pady=2)


        # Metadata display
        ttk.Label(right_frame, text="Shot Metadata", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        self.meta_text = tk.Text(right_frame, width=50, height=15, bg="#1e1e1e", fg="white", font=("Consolas", 10),
                                 borderwidth=0, highlightthickness=0)
        self.meta_text.pack(fill=tk.BOTH, expand=True)
        self.meta_text.insert("1.0", "Select a shot to view metadata.")
        self.meta_text.config(state=tk.DISABLED)

        self.refresh()

    # -------------- SETTINGS TAB ------------------
    def create_settings_tab(self):
        """Initializes the UI elements for the 'Settings' tab."""
        settings_frame = ttk.Frame(self.settings_tab, padding="20")
        settings_frame.pack(fill="both", expand=True)

        # Blender Path Settings
        ttk.Label(settings_frame, text="Blender Executable Path:", font=("Segoe UI", 10, "bold")).pack(pady=(10, 5), anchor="w")
        self.blender_path_label = ttk.Label(settings_frame, text=config["blender_path"], font=("Segoe UI", 10, "italic"),
                                    wraplength=700, justify=tk.LEFT) # Added wraplength for long paths
        self.blender_path_label.pack(pady=(0, 10), anchor="w")
        ttk.Button(settings_frame, text="Change Blender Path", command=self.open_blender_path_dialog).pack(pady=5, anchor="w")

        ttk.Separator(settings_frame, orient="horizontal").pack(fill="x", pady=20)

        # Shot Directory Settings (NEW)
        ttk.Label(settings_frame, text="Shot Files Storage Directory:", font=("Segoe UI", 10, "bold")).pack(pady=(10, 5), anchor="w")
        self.shot_dir_label = ttk.Label(settings_frame, text=config["shot_directory"], font=("Segoe UI", 10, "italic"),
                                    wraplength=700, justify=tk.LEFT)
        self.shot_dir_label.pack(pady=(0, 10), anchor="w")
        ttk.Button(settings_frame, text="Change Shot Directory", command=self.open_shot_directory_dialog).pack(pady=5, anchor="w")

    # -------------- LOG TAB ------------------
    def create_log_tab(self):
        """Initializes the UI elements for the 'Log' tab."""
        self.log_text = tk.Text(self.log_tab, wrap="word", height=25, bg="#1e1e1e", fg="white",
                                font=("Segoe UI", 9), borderwidth=0, highlightthickness=0)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.log_text.insert("1.0", "[LOG] ShotMan ready.\n")
        self.log_text.config(state=tk.DISABLED)

    # -------------- LOGGING & STATUS FUNCTIONS ------------------
    def log(self, message):
        """Appends a timestamped message to the log text area."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{time.ctime()}: {message}\n")
        self.log_text.see(tk.END) # Auto-scroll to the end
        self.log_text.config(state=tk.DISABLED)

    def update_status(self, message):
        """Updates the text in the status bar."""
        self.status_bar.config(text=message)

    # -------------- SHOT LIST & FILTERING FUNCTIONS ------------------
    def _sort_files(self, files, sort_type):
        """Helper function to sort the list of Blender files based on the selected criteria."""
        def shot_number_key(filename):
            # Expecting SHOT_XXX_vYY.blend
            match = re.search(r"SHOT_(\d+)_v\d+\.blend$", filename)
            return int(match.group(1)) if match else 0

        # Remove the _vXX.blend suffix for alphabetical sorting if desired
        def alphabetical_key(filename):
            return re.sub(r'_v\d+\.blend$', '', filename)

        if sort_type == "Alphabetical (A-Z)":
            files.sort(key=alphabetical_key)
        elif sort_type == "Date Created (Newest)":
            files.sort(key=lambda f: os.path.getctime(os.path.join(config["shot_directory"], f)), reverse=True)
        elif sort_type == "Date Created (Oldest)":
            files.sort(key=lambda f: os.path.getctime(os.path.join(config["shot_directory"], f)))
        elif sort_type == "File Size (Largest)":
            files.sort(key=lambda f: os.path.getsize(os.path.join(config["shot_directory"], f)), reverse=True)
        elif sort_type == "File Size (Smallest)":
            files.sort(key=lambda f: os.path.getsize(os.path.join(config["shot_directory"], f)))
        elif sort_type == "Shot Number":
            files.sort(key=shot_number_key)
        return files

    def _populate_shot_listbox(self, shots_to_display):
        """Populates the listbox with the given list of shot filenames."""
        self.shot_listbox.delete(0, tk.END)
        for f in shots_to_display:
            self.shot_listbox.insert(tk.END, f)

    def refresh(self):
        """Refreshes the list of shots displayed in the listbox based on current filter and sort."""
        self.update_status("Refreshing shot list...")
        try:
            # Pass the current shot_directory to list_shots
            self.all_shots = list_shots(config["shot_directory"])
            self._filter_shots() # Apply current filter and sort
            self.log(f"[Refresh] Shot list updated with sort: {self.sort_var.get()}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load shots: {e}", parent=self.root)
            self.log(f"[Error] Could not load shots: {e}")
            self.update_status(f"Error refreshing shots: {e}")

    def _filter_shots(self, event=None):
        """Filters the shots based on the search entry and updates the listbox."""
        search_term = self.search_entry.get().lower()
        filtered_shots = []

        # Use self.all_shots which is populated by refresh()
        for shot_name in self.all_shots:
            if search_term in shot_name.lower():
                filtered_shots.append(shot_name)

        # Re-sort the filtered list
        sorted_filtered_shots = self._sort_files(filtered_shots, self.sort_var.get())
        self._populate_shot_listbox(sorted_filtered_shots)
        self.update_status(f"Filtered {len(sorted_filtered_shots)} shots.")


    # -------------- SHOT MANAGEMENT FUNCTIONS ------------------
    def create_shot(self):
        """Prompts for a new shot base name and creates its initial _v01 file using a selected template."""
        shot_window = tk.Toplevel(self.root)
        shot_window.title("Create New Shot")
        shot_window.geometry("400x200")
        shot_window.configure(bg="#2b2b2b")
        shot_window.transient(self.root)
        shot_window.grab_set()

        frame = ttk.Frame(shot_window, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Shot Name (e.g., SHOT_010):").pack(anchor="w")
        name_var = tk.StringVar()
        name_entry = ttk.Entry(frame, textvariable=name_var)
        name_entry.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Select Template:").pack(anchor="w")
        template_var = tk.StringVar()
        templates = {
            "Default": ("default", "cam_template_default.blend"),
            "Animation": ("anim", "cam_template_anim.blend"),
            "Layout": ("layout", "cam_template_layout.blend"),
            "Lighting": ("lighting", "cam_template_lighting.blend")
        }
        template_selector = ttk.Combobox(frame, textvariable=template_var, values=list(templates.keys()), state="readonly")
        template_selector.current(0)
        template_selector.pack(fill="x", pady=(0, 10))

        def on_create():
            base_name = name_var.get().strip()
            if not re.match(r"^[a-zA-Z0-9_]+$", base_name):
                messagebox.showwarning("Invalid Name", "Shot name can only contain letters, numbers, and underscores.")
                return

            template_label, template_filename = templates[template_var.get()]
            # Template path is relative to the shot_directory
            template_path = os.path.join(config["shot_directory"], "templates", template_filename)

            if not os.path.exists(template_path):
                messagebox.showerror("Missing Template", f"Template file not found:\n{template_path}")
                return

            try:
                # Pass shot_directory to the core function
                new_shot_file = create_new_shot_from_template(base_name, template_label, template_path, config["shot_directory"])
                self.refresh()
                self.log(f"[Create] New shot '{new_shot_file}' created using template '{template_filename}'.")
                self.update_status(f"Shot '{new_shot_file}' created.")
                shot_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create shot: {e}")
                self.log(f"[Error] Failed to create shot from template: {e}")

        ttk.Button(frame, text="Create Shot", command=on_create).pack(pady=10)


    def duplicate_selected(self):
        """Duplicates the currently selected shot, creating the next version of it."""
        selected_filename = self.get_selected()
        if selected_filename:
            # Parse the original filename to get the base name (e.g., "SHOT_010")
            match = re.match(r"^(.*)_v(\d{2})\.blend$", selected_filename)
            if not match:
                messagebox.showwarning("Invalid Shot Name",
                                       f"Selected shot '{selected_filename}' does not follow the expected versioning pattern (e.g., NAME_vXX.blend). Cannot duplicate.",
                                       parent=self.root)
                return

            try:
                # Pass shot_directory to the core function
                new_version_filename = duplicate_shot(selected_filename, config["shot_directory"]) # core.py returns the new filename
                self.refresh()
                # Select the newly duplicated shot
                try:
                    idx = self.shot_listbox.get(0, tk.END).index(new_version_filename)
                    self.shot_listbox.selection_set(idx)
                    self.shot_listbox.see(idx)
                    self.update_metadata()
                except ValueError:
                    pass # Not in current filtered view

                self.log(f"[Duplicate] Shot '{selected_filename}' duplicated as '{new_version_filename}'.")
                self.update_status(f"Shot '{new_version_filename}' created as new version.")
            except ValueError as e:
                messagebox.showwarning("Duplication Error", str(e), parent=self.root)
                self.log(f"[Warning] Duplication failed: {e}")
                self.update_status(f"Error duplicating shot: {e}")
            except FileExistsError as e:
                messagebox.showwarning("File Exists", str(e), parent=self.root)
                self.log(f"[Warning] Duplication failed: {e}")
                self.update_status(f"Error duplicating shot: {e}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to duplicate shot '{selected_filename}': {e}", parent=self.root)
                self.log(f"[Error] Failed to duplicate shot '{selected_filename}': {e}")
                self.update_status(f"Error duplicating shot: {e}")
        else:
            messagebox.showinfo("No Selection", "Please select a shot to duplicate.", parent=self.root)


    def delete_selected(self):
        """Deletes the currently selected shot after confirmation."""
        selected = self.get_selected()
        if selected:
            if messagebox.askyesno("Delete Shot", f"Are you sure you want to PERMANENTLY delete '{selected}'?", icon='warning', parent=self.root):
                try:
                    # Pass shot_directory to the core function
                    delete_shot(selected, config["shot_directory"]) # Use the function from core.py
                    self._delete_custom_metadata(selected) # Delete associated custom metadata
                    self.refresh()
                    self.log(f"[Delete] Shot '{selected}' deleted.")
                    self.update_status(f"Shot '{selected}' deleted.")
                    self.meta_text.config(state=tk.NORMAL)
                    self.meta_text.delete("1.0", tk.END)
                    self.meta_text.insert("1.0", "Shot deleted. Select another shot.")
                    self.meta_text.config(state=tk.DISABLED)
                except FileNotFoundError as e:
                    messagebox.showerror("Error", str(e), parent=self.root)
                    self.log(f"[Error] Deletion failed: {e}")
                    self.update_status(f"Error deleting shot: {e}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete shot '{selected}': {e}", parent=self.root)
                    self.log(f"[Error] Failed to delete shot '{selected}': {e}")
                    self.update_status(f"Error deleting shot: {e}")
        else:
            messagebox.showinfo("No Selection", "Please select a shot to delete.", parent=self.root)

    def open_in_blender_selected(self):
        """Opens the selected Blender file using the configured Blender executable."""
        selected = self.get_selected()
        if selected:
            self._open_in_blender(selected)
        else:
            messagebox.showinfo("No Selection", "Please select a shot to open in Blender.", parent=self.root)

    def open_in_blender(self, event):
        """Event handler for double-clicking a listbox item to open in Blender."""
        self.open_in_blender_selected()

    def _open_in_blender(self, filename):
        """Internal helper to open a specific Blender file."""
        full_path = os.path.abspath(os.path.join(config["shot_directory"], filename)) # Use config["shot_directory"]
        blender_path = config["blender_path"] # Get Blender path from your config

        if not blender_path: # Basic check if path is empty
            messagebox.showerror("Blender Path Error",
                                 "Blender executable path is not set.\n"
                                 "Please configure it in the Settings tab.", parent=self.root)
            self.log("[Error] Blender path is empty.")
            self.update_status("Error: Blender path not set.")
            return

        if not os.path.exists(blender_path): # Check if the path exists
            messagebox.showerror("Blender Path Error",
                                 f"Blender executable not found at: '{blender_path}'\n"
                                 "Please check the path in the Settings tab.", parent=self.root)
            self.log(f"[Error] Blender executable not found: {blender_path}")
            self.update_status(f"Error: Blender not found at '{blender_path}'")
            return

        try:
            # Use shell=True on Windows for default association, otherwise pass list
            if os.name == 'nt': # Windows
                subprocess.Popen(f'"{blender_path}" "{full_path}"', shell=True)
            else: # Linux/macOS
                subprocess.Popen([blender_path, full_path])
            self.log(f"[Open] Shot opened in Blender: {filename}")
            self.update_status(f"Opening '{filename}' in Blender...")
        except FileNotFoundError: # Catch if the program itself (blender_path) is not found
            messagebox.showerror("Blender Not Found",
                                 f"Cannot find Blender executable at: '{blender_path}'\n"
                                 "Please check the path in the Settings tab.", parent=self.root)
            self.log(f"[Error] Blender not found at path: {blender_path}")
            self.update_status(f"Error: Blender not found at '{blender_path}'")
        except Exception as e:
            messagebox.showerror("Error Opening Blender", f"An error occurred while trying to open Blender: {e}", parent=self.root)
            self.log(f"[Error] Failed to open Blender with '{filename}': {e}")
            self.update_status(f"Error opening Blender: {e}")

    def update_metadata(self, event=None):
        """Updates the metadata display for the currently selected shot, including file system info and custom metadata."""
        selected = self.get_selected()
        self.meta_text.config(state=tk.NORMAL)
        self.meta_text.delete("1.0", tk.END)

        if selected:
            full_path = os.path.abspath(os.path.join(config["shot_directory"], selected))

            if os.path.exists(full_path):
                # --- 1. Display basic file system info ---
                try:
                    stat = os.stat(full_path)
                    size_bytes = stat.st_size
                    size_kb = size_bytes // 1024
                    created = time.ctime(stat.st_ctime)
                    modified = time.ctime(stat.st_mtime)

                    file_info = (
                        f"File Name: {selected}\n"
                        f"Size: {size_kb} KB ({size_bytes} bytes)\n"
                        f"Created: {created}\n"
                        f"Modified: {modified}\n"
                    )
                    self.meta_text.insert("1.0", file_info + "\n") # Add a newline
                except Exception as e:
                    self.meta_text.insert("1.0", f"Error reading file system metadata: {e}\n")
                    self.log(f"[Error] Could not read file system metadata for {selected}: {e}")

                # --- 2. Display Custom Metadata ---
                self.meta_text.insert(tk.END, "\n--- Custom Metadata ---\n")
                custom_meta = self._load_custom_metadata(selected)
                if custom_meta:
                    for key, value in custom_meta.items():
                        formatted_key = key.replace('_', ' ').title()
                        self.meta_text.insert(tk.END, f"{formatted_key}: {value}\n")
                else:
                    self.meta_text.insert(tk.END, "No custom metadata.\n")

                # Removed Blender Specific Info section
                # self.meta_text.insert(tk.END, "\n--- Blender Specific Info ---\n")
                # self.meta_text.insert(tk.END, "Loading Blender data (may take a moment)...\n")
                # self.update_status(f"Extracting Blender info for '{selected}'...")
                # blender_info = get_blender_file_info(full_path, blender_path)
                # self.meta_text.delete("end-2l", tk.END)
                # if "error" in blender_info:
                #     self.meta_text.insert(tk.END, f"Error extracting Blender info: {blender_info['error']}\n")
                #     self.log(f"[Error] Failed to extract Blender info for {selected}: {blender_info['error']}")
                #     self.update_status(f"Error extracting Blender info for '{selected}'.")
                # else:
                #     if "status" in blender_info:
                #         self.meta_text.insert(tk.END, f"Blender Check: {blender_info['status']}\n")
                #     else:
                #         for key, value in blender_info.items():
                #             formatted_key = key.replace('_', ' ').title()
                #             self.meta_text.insert(tk.END, f"{formatted_key}: {value}\n")
                #     self.log(f"[Info] Successfully checked Blender file: {selected}.")
                #     self.update_status(f"Blender file check for '{selected}' complete.")

                # Update status bar to reflect only file system and custom metadata loaded
                self.update_status(f"Metadata loaded for '{selected}'.")

            else:
                self.meta_text.insert("1.0", f"File not found: {selected}\n")
        else:
            self.meta_text.insert("1.0", "Select a shot to view metadata.")

        self.meta_text.config(state=tk.DISABLED)

    def get_selected(self):
        """Returns the name of the currently selected shot from the listbox, or None if nothing is selected."""
        selected_indices = self.shot_listbox.curselection()
        if selected_indices:
            return self.shot_listbox.get(selected_indices[0])
        return None

    def open_blender_path_dialog(self):
        """Opens a file dialog to select the Blender executable path."""
        # Suggest initial directory if current path exists, otherwise default
        initial_dir = os.path.dirname(config["blender_path"]) if os.path.exists(config["blender_path"]) else "/"

        new_path = filedialog.askopenfilename(
            title="Select Blender Executable",
            initialdir=initial_dir,
            filetypes=[("Blender Executable", "blender.exe" if os.name == 'nt' else "blender"),
                       ("All Files", "*.*")], # Add All Files option
            parent=self.root
        )
        if new_path:
            config["blender_path"] = new_path
            save_config(config)
            self.blender_path_label.config(text=new_path)
            messagebox.showinfo("Path Saved", f"Blender path set to:\n{new_path}", parent=self.root)
            self.log(f"[Settings] Blender path set to {new_path}")
            self.update_status(f"Blender path updated to: {new_path}")

    def _copy_default_templates(self, source_dir, destination_dir):
        """
        Copies template files from a source directory (bundled or script-based)
        to the 'templates' subdirectory within the user's chosen shot_directory.
        """
        self.log(f"DEBUG: Attempting to copy templates from SOURCE: {source_dir}")
        self.log(f"DEBUG: To DESTINATION directory: {destination_dir}")

        if not os.path.exists(source_dir):
            self.log(f"[ERROR] Default template SOURCE directory does NOT exist: {source_dir}")
            messagebox.showerror("Template Error",
                                 f"Internal error: Default template source not found at '{source_dir}'. "
                                 "Please ensure your application is correctly bundled or run from the correct location.",
                                 parent=self.root)
            return

        # Check if the source directory is empty or doesn't contain expected files
        expected_template_file = os.path.join(source_dir, "cam_template_default.blend")
        if not os.path.exists(expected_template_file):
            self.log(f"[ERROR] Expected template file not found in SOURCE: {expected_template_file}. "
                     f"Contents of {source_dir}: {os.listdir(source_dir) if os.path.isdir(source_dir) else 'Not a directory'}")
            messagebox.showerror("Template Error",
                                 f"Internal error: Essential template '{os.path.basename(expected_template_file)}' not found in bundled source. "
                                 "Please ensure your 'camera_shots/templates' folder contains the necessary files before building the executable.",
                                 parent=self.root)
            return

        destination_templates_dir = os.path.join(destination_dir, "templates")
        self.log(f"DEBUG: Ensuring destination templates directory exists: {destination_templates_dir}")
        os.makedirs(destination_templates_dir, exist_ok=True)

        try:
            # Clear existing templates in the destination to ensure a clean copy.
            # This is important if previous copies were incomplete or corrupted.
            # Only remove if the destination is NOT the source itself (to prevent self-deletion).
            if os.path.exists(destination_templates_dir) and \
               os.path.isdir(destination_templates_dir) and \
               os.path.abspath(destination_templates_dir) != os.path.abspath(source_dir):
                self.log(f"DEBUG: Clearing existing templates in {destination_templates_dir} before copying.")
                shutil.rmtree(destination_templates_dir, ignore_errors=True)
                os.makedirs(destination_templates_dir, exist_ok=True) # Recreate empty dir

            # Copy the entire template directory tree
            if sys.version_info >= (3, 8):
                shutil.copytree(source_dir, destination_templates_dir, dirs_exist_ok=True)
            else:
                shutil.copytree(source_dir, destination_templates_dir)

            self.log(f"[SUCCESS] Successfully copied templates from {source_dir} to {destination_templates_dir}")
        except shutil.Error as e:
            self.log(f"[ERROR] shutil.Error during template copy: {e}")
            messagebox.showerror("Template Copy Error", f"Failed to copy templates: {e}. "
                                 "Check permissions for the selected shot directory.", parent=self.root)
        except Exception as e:
            self.log(f"[ERROR] General error during template copy: {e}")
            messagebox.showerror("Template Copy Error", f"An unexpected error occurred while copying templates: {e}", parent=self.root)


    def open_shot_directory_dialog(self):
        """Opens a directory dialog to select the Shot Files Storage Directory."""
        current_shot_dir = config["shot_directory"]
        initial_dir = current_shot_dir if os.path.exists(current_shot_dir) else os.getcwd()

        new_dir = filedialog.askdirectory(
            title="Select Shot Files Storage Directory",
            initialdir=initial_dir,
            parent=self.root
        )

        if new_dir and new_dir != current_shot_dir:
            config["shot_directory"] = new_dir
            save_config(config)
            self.shot_dir_label.config(text=new_dir)
            ensure_shot_directories_exist(new_dir) # Ensure new directory and its subdirs exist

            # Copy templates to the newly selected directory
            self._copy_default_templates(DEFAULT_TEMPLATE_SOURCE_DIR, new_dir)

            self.refresh() # Refresh the shot list based on the new directory
            messagebox.showinfo("Directory Saved", f"Shot files directory set to:\n{new_dir}\n\n"
                                 "The application will now refresh the shot list and ensure templates are present.", parent=self.root)
            self.log(f"[Settings] Shot directory set to {new_dir}")
            self.update_status(f"Shot directory updated to: {new_dir}")
        elif new_dir and new_dir == current_shot_dir:
            self.log("[Settings] Shot directory not changed (same directory selected).")
            self.update_status("Shot directory not changed.")
        else:
            self.log("[Settings] Shot directory selection cancelled.")
            self.update_status("Shot directory selection cancelled.")

    def show_in_file_explorer(self):
        """Opens the selected shot's directory in the native file explorer, highlighting the file."""
        selected = self.get_selected()
        if selected:
            full_path = os.path.abspath(os.path.join(config["shot_directory"], selected)) # Use config["shot_directory"]
            if not os.path.exists(full_path):
                messagebox.showerror("Error", f"File not found: {full_path}", parent=self.root)
                self.log(f"[Error] File not found for explore: {full_path}")
                self.update_status(f"Error: File '{selected}' not found.")
                return

            try:
                if os.name == 'nt':  # Windows
                    subprocess.Popen(f'explorer /select,"{full_path}"')
                elif os.uname().sysname == 'Darwin':  # macOS
                    subprocess.Popen(['open', '-R', full_path])
                else:  # Linux (using xdg-open)
                    directory_path = os.path.dirname(full_path)
                    subprocess.Popen(['xdg-open', directory_path])

                self.log(f"[Explore] Opened '{full_path}' in file explorer.")
                self.update_status(f"Showing '{selected}' in file explorer.")
            except FileNotFoundError as e:
                messagebox.showerror("Error", f"Required program not found to open file explorer: {e}\n"
                                     "Please ensure 'explorer.exe' (Windows), 'open' (macOS), or 'xdg-open' (Linux) is in your system's PATH.", parent=self.root)
                self.log(f"[Error] Required program not found for file explorer: {e}")
                self.update_status(f"Error: File explorer utility missing.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file explorer: {e}", parent=self.root)
                self.log(f"[Error] Failed to open file explorer for '{full_path}': {e}")
                self.update_status(f"Error showing in file explorer: {e}")
        else:
            messagebox.showinfo("No Selection", "Please select a shot to show in file explorer.", parent=self.root)

    def _show_listbox_context_menu(self, event):
        """Displays the right-click context menu for the listbox."""
        try:
            # Get the index of the item under the mouse pointer
            index = self.shot_listbox.nearest(event.y)
            if index != -1:
                self.shot_listbox.selection_clear(0, tk.END)
                self.shot_listbox.selection_set(index)
                self.shot_listbox.activate(index)
                self.update_metadata() # Update metadata for the right-clicked item

                self.listbox_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.listbox_menu.grab_release()

    # -------------- CUSTOM METADATA FUNCTIONS ------------------
    def _get_custom_metadata_path(self, filename):
        """Generates the path for the custom metadata JSON file."""
        name_no_ext = os.path.splitext(filename)[0]
        return os.path.join(config["shot_directory"], CUSTOM_METADATA_SUBDIR, f"{name_no_ext}.json")

    def _load_custom_metadata(self, filename):
        """Loads custom metadata for a given shot filename."""
        meta_path = self._get_custom_metadata_path(filename)
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                self.log(f"[Error] Could not decode custom metadata for {filename}: {e}")
                return {"error": "Corrupted custom metadata file."}
            except Exception as e:
                self.log(f"[Error] Error loading custom metadata for {filename}: {e}")
                return {"error": "Error loading custom metadata."}
        return {} # Return empty dict if no metadata file exists

    def _save_custom_metadata(self, filename, data):
        """Saves custom metadata for a given shot filename."""
        meta_path = self._get_custom_metadata_path(filename)
        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.log(f"[Info] Custom metadata saved for {filename}.")
            return True
        except Exception as e:
            self.log(f"[Error] Failed to save custom metadata for {filename}: {e}")
            messagebox.showerror("Error Saving Metadata", f"Failed to save custom metadata for '{filename}': {e}", parent=self.root)
            return False

    def _delete_custom_metadata(self, filename):
        """Deletes the custom metadata file associated with a shot."""
        meta_path = self._get_custom_metadata_path(filename)
        if os.path.exists(meta_path):
            try:
                os.remove(meta_path)
                self.log(f"[Info] Custom metadata file deleted for {filename}.")
                return True
            except Exception as e:
                self.log(f"[Error] Failed to delete custom metadata file for {filename}: {e}")
                return False
        return False


    def edit_custom_metadata_for_selected(self):
        """Opens a Toplevel window to edit custom metadata for the selected shot."""
        selected = self.get_selected()
        if not selected:
            messagebox.showinfo("No Selection", "Please select a shot to edit custom metadata.", parent=self.root)
            return

        current_meta = self._load_custom_metadata(selected)
        if "error" in current_meta:
            messagebox.showerror("Metadata Error", current_meta["error"], parent=self.root)
            return

        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Edit Metadata: {selected}")
        edit_window.transient(self.root) # Make it modal
        edit_window.grab_set() # Grab all events until window is closed
        edit_window.geometry("400x400")
        edit_window.configure(bg="#2b2b2b")

        frame = ttk.Frame(edit_window, padding="15")
        frame.pack(fill="both", expand=True)

        # Status
        ttk.Label(frame, text="Status:").grid(row=0, column=0, sticky="w", pady=5)
        status_var = tk.StringVar(value=current_meta.get("status", "WIP"))
        status_options = ["WIP", "Needs Review", "Approved", "Blocked", "Final"]
        status_combobox = ttk.Combobox(frame, textvariable=status_var, values=status_options, state="readonly", width=30)
        status_combobox.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Assigned Artist
        ttk.Label(frame, text="Assigned Artist:").grid(row=1, column=0, sticky="w", pady=5)
        artist_var = tk.StringVar(value=current_meta.get("assigned_artist", ""))
        artist_entry = ttk.Entry(frame, textvariable=artist_var, width=30)
        artist_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        # Due Date (simple text for now)
        ttk.Label(frame, text="Due Date:").grid(row=2, column=0, sticky="w", pady=5)
        due_date_var = tk.StringVar(value=current_meta.get("due_date", ""))
        due_date_entry = ttk.Entry(frame, textvariable=due_date_var, width=30)
        due_date_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        # Notes
        ttk.Label(frame, text="Notes:").grid(row=3, column=0, sticky="nw", pady=5)
        notes_text = tk.Text(frame, height=8, width=30, bg="#1e1e1e", fg="white", font=("Segoe UI", 9),
                             borderwidth=0, highlightthickness=0, insertbackground="white")
        notes_text.grid(row=3, column=1, sticky="nsew", padx=5, pady=5)
        notes_text.insert("1.0", current_meta.get("notes", ""))
        notes_scrollbar = ttk.Scrollbar(frame, command=notes_text.yview)
        notes_scrollbar.grid(row=3, column=2, sticky="ns")
        notes_text.config(yscrollcommand=notes_scrollbar.set)

        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        def save_and_close():
            new_meta = {
                "status": status_var.get(),
                "assigned_artist": artist_var.get().strip(),
                "due_date": due_date_var.get().strip(),
                "notes": notes_text.get("1.0", tk.END).strip()
            }
            if self._save_custom_metadata(selected, new_meta):
                self.update_metadata() # Refresh the display
            edit_window.destroy()

        def cancel_and_close():
            edit_window.destroy()

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        ttk.Button(button_frame, text="Save", command=save_and_close).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel_and_close).pack(side=tk.LEFT, padx=5)

        edit_window.protocol("WM_DELETE_WINDOW", cancel_and_close) # Handle window close button
        self.root.wait_window(edit_window) # Wait for the Toplevel window to close


if __name__ == "__main__":
    root = tk.Tk()
    app = ShotManagerGUI(root)
    root.mainloop()
