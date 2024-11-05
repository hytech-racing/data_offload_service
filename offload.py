#!/usr/bin/env python
import psutil
import subprocess
import socket
import time
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from pathlib import Path
import shutil

# Configuration variables
INTERFACE = "enp0s13f0ul"  # Replace with your Ethernet interface
LOCAL_DIR = "/home/hytech/hytech_data/temp_mcap_dir"
REMOTE_USER = "nixos"
REMOTE_HOST = "192.168.1.69"
REMOTE_DIR = "/home/nixos/recordings"
SSH_KEY = "~/.ssh/id_ed25519"
SSH_PORT = 22
SYNC_DEST_BASE = "/home/hytech/hytech_mcaps/synced_data"  # Where timestamped folders will be stored

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

        # Progress Bar
        self.progress_bar = ttk.Progressbar(root, orient="horizontal", mode="determinate", length=300)
        self.progress_bar.pack(pady=20)

        self.force_check_button = tk.Button(
            root, text="Force Offload", font=("Arial", 20), command=self.force_check, width=15, height=2
        )
        self.force_check_button.pack(pady=20)

        # Add small font Ethernet interface list at the bottom
        self.interface_label = tk.Label(root, text="", font=("Arial", 10))
        self.interface_label.pack(side="bottom", pady=10)

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

    def list_remote_files(self):
        """List files on the remote server using SSH."""
        ssh_command = [
            "/run/current-system/sw/bin/ssh", "-i", SSH_KEY, f"{REMOTE_USER}@{REMOTE_HOST}",
            f"ls {REMOTE_DIR}"
        ]
        try:
            result = subprocess.run(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            remote_files = result.stdout.splitlines()
            return set(remote_files)
        except subprocess.CalledProcessError as e:
            self.update_rsync_status(f"SSH Error: Womp Womp")
            return set()

    def list_local_files(self):
        """List all files in the synced_data directory and its subdirectories."""
        local_files = set()
        for path in Path(SYNC_DEST_BASE).rglob("*"):
            if path.is_file():
                local_files.add(path.name)
        return local_files

    def sync_directory(self):
        """Sync only the new files from remote directory to local."""
        remote_files = self.list_remote_files()
        local_files = self.list_local_files()

        # Calculate the difference - files that are on the remote but not locally
        new_files = remote_files - local_files

        if new_files:
            self.progress_bar["maximum"] = len(new_files)
            self.progress_bar["value"] = 0

            for idx, file in enumerate(new_files, 1):
                rsync_command = [
                    "/run/current-system/sw/bin/rsync", "-avz",
                    "-e", "/run/current-system/sw/bin/ssh",
                    f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/{file}",
                    LOCAL_DIR
                ]
                try:
                    self.update_rsync_status("In Progress...")
                    subprocess.run(rsync_command, check=True)
                    self.progress_bar["value"] = idx
                    self.root.update_idletasks()  # Refresh the progress bar
                except subprocess.CalledProcessError:
                    self.update_rsync_status(f"Error: womp womp")
                    return

            self.update_rsync_status("Completed")
            self.move_to_timestamped_folder(new_files)
        else:
            self.update_rsync_status("No New Files to Sync")

    def move_to_timestamped_folder(self, new_files):
        """Move the newly synced files to a timestamped folder."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        destination = Path(SYNC_DEST_BASE) / timestamp

        try:
            destination.mkdir(parents=True, exist_ok=True)
            for file in new_files:
                item = Path(LOCAL_DIR) / file
                if item.is_dir():
                    shutil.copytree(str(item), destination / item.name)
                else:
                    shutil.copy2(item, destination / item.name)

            self.update_rsync_status(f"Files moved to: {destination}")
        except Exception:
            self.update_rsync_status(f"Move Error: Womp womp ")

    def update_interface_list(self):
        """Retrieve and update the list of Ethernet interfaces."""
        net_if_addrs = psutil.net_if_addrs()
        ethernet_interfaces = [iface for iface in net_if_addrs if any(addr.family == socket.AF_INET for addr in net_if_addrs[iface])]
        self.interface_label.config(text=f"Available Ethernet Interfaces: {', '.join(ethernet_interfaces)}")

    def monitor_ethernet(self):
        """Monitor the Ethernet interface and trigger rsync if SSH is available."""
        while True:
            print("monitoring")
            self.update_interface_list()  # Refresh the list of interfaces
            net_if_addrs = psutil.net_if_addrs()
            if INTERFACE in net_if_addrs:
                if any(addr.family == socket.AF_INET for addr in net_if_addrs[INTERFACE]):
                    self.update_ssh_status(f"{INTERFACE} Connected")
                    if self.is_ssh_available():
                        self.sync_directory()
            time.sleep(5)

    def force_check(self):
        """Force a check of SSH availability and sync."""
        self.update_ssh_status("Forcing a check of connected devices...")
        if self.is_ssh_available():
            self.sync_directory()

def main():
    root = tk.Tk()
    app = EthernetSyncApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()