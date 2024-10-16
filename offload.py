#!/usr/bin/env python
import psutil
import subprocess
import socket
import time
import threading
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path
import shutil

# Configuration variables
INTERFACE = "enp0s13f0u4c2"  # Replace with your Ethernet interface
LOCAL_DIR = "/home/ben/temp_mcap_dir"
REMOTE_USER = "nixos"
REMOTE_HOST = "192.168.1.69"
REMOTE_DIR = "/home/nixos/recordings"
SSH_KEY = "~/.ssh/id_ed25519"
SSH_PORT = 22
SYNC_DEST_BASE = "/home/ben/hytech_mcaps/synced_data/"  # Where timestamped folders will be stored

class EthernetSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ethernet Sync Service")

        # Set window size to be larger (800x400) and center it
        window_width, window_height = 800, 400
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # GUI Elements
        self.ssh_status_label = tk.Label(root, text="SSH Status: Unknown", font=("Arial", 24), pady=20)
        self.ssh_status_label.pack()

        self.rsync_status_label = tk.Label(root, text="Rsync Status: Not Started", font=("Arial", 24), pady=20)
        self.rsync_status_label.pack()

        self.force_check_button = tk.Button(
            root, text="Force Offload", font=("Arial", 20), command=self.force_check, width=15, height=2
        )
        self.force_check_button.pack(pady=20)

        # Start the monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_ethernet, daemon=True)
        self.monitor_thread.start()

    def update_ssh_status(self, status):
        """Update the SSH status label on the GUI."""
        self.ssh_status_label.config(text=f"SSH Status: {status}")

    def update_rsync_status(self, status):
        """Update the Rsync status label on the GUI."""
        self.rsync_status_label.config(text=f"Rsync Status: {status}")

    def is_ssh_available(self):
        """Check if the SSH service is available on the remote host."""
        try:
            with socket.create_connection((REMOTE_HOST, SSH_PORT), timeout=2):
                self.update_ssh_status("Available")
                return True
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            self.update_ssh_status(f"Unavailable: {e}")
            return False

    def sync_directory(self):
        """Sync the directories using rsync over SSH."""
        rsync_command = [
            "rsync", "-avz",
            "-e", f"ssh -i {SSH_KEY}",
            f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}", LOCAL_DIR
        ]
        try:
            self.update_rsync_status("In Progress...")
            subprocess.run(rsync_command, check=True)
            self.update_rsync_status("Completed")

            # Move the synced files to a timestamped folder
            self.move_to_timestamped_folder()
        except subprocess.CalledProcessError as e:
            self.update_rsync_status(f"Error: {e}")

    def move_to_timestamped_folder(self):
        """Move the synced files to a timestamped folder."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        destination = Path(SYNC_DEST_BASE) / timestamp

        try:
            # Create the destination folder if it doesn't exist
            destination.mkdir(parents=True, exist_ok=True)

            # Move all files from the local directory to the timestamped folder
            for item in Path(LOCAL_DIR).iterdir():
                shutil.move(str(item), destination / item.name)

            self.update_rsync_status(f"Files moved to: {destination}")
        except Exception as e:
            self.update_rsync_status(f"Move Error: {e}")

    def monitor_ethernet(self):
        """Monitor the Ethernet interface and trigger rsync if SSH is available."""
        while True:
            net_if_addrs = psutil.net_if_addrs()
            if INTERFACE in net_if_addrs:
                if any(addr.family == socket.AF_INET for addr in net_if_addrs[INTERFACE]):
                    self.update_ssh_status(f"{INTERFACE} Connected")
                    if self.is_ssh_available():
                        self.sync_directory()
            time.sleep(5)

    def force_check(self):
        """Force a check of SSH availability and sync."""
        messagebox.showinfo("Force Check", "Forcing a check of connected devices...")
        if self.is_ssh_available():
            self.sync_directory()

def main():
    root = tk.Tk()
    app = EthernetSyncApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
