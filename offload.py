#!/usr/bin/env python
import json
import psutil
import subprocess
import socket
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
from pathlib import Path
import shutil
import requests

# Configuration variables
INTERFACE = "enp0s13f0u1"  # Replace with your Ethernet interface
LOCAL_DIR = "/home/hytech/hytech_data/temp_mcap_dir"
REMOTE_USER = "nixos"
REMOTE_HOST = "192.168.1.69"
REMOTE_DIR = "/home/nixos/recordings"
SSH_KEY = "~/.ssh/id_ed25519"
SSH_PORT = 22
SYNC_DEST_BASE = "/home/hytech/hytech_mcaps/synced_data"  # Where timestamped folders will be stored
UPLOAD_MANIFEST = "/root/data_offload_service/.upload_manifest.json"

UPLOAD_URL = "https://hytechracing.duckdns.org/mcaps/bulk_upload"


class EthernetSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ethernet Sync Service")

        window_width, window_height = 900, 700
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.ssh_status_label = tk.Label(root, text="SSH Status: Unknown", font=("Arial", 20), pady=10)
        self.ssh_status_label.pack()

        self.rsync_status_label = tk.Label(root, text="Status: Not Started", font=("Arial", 20), pady=10)
        self.rsync_status_label.pack()

        self.current_file_label = tk.Label(root, text="Current file: -", font=("Arial", 12))
        self.current_file_label.pack()

        self.progress_bar = ttk.Progressbar(root, orient="horizontal", mode="determinate", length=500)
        self.progress_bar.pack(pady=10)

        self.file_count_label = tk.Label(root, text="Files transferred: 0 / 0", font=("Arial", 14))
        self.file_count_label.pack()

        self.force_check_button = tk.Button(
            root, text="Force Offload", font=("Arial", 16), command=self.force_check, width=15, height=1
        )
        self.force_check_button.pack(pady=10)

        log_frame = tk.Frame(root)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        tk.Label(log_frame, text="Log output", font=("Arial", 10, "bold")).pack(anchor="w")
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, font=("Courier", 9), state="disabled", wrap="word"
        )
        self.log_text.pack(fill="both", expand=True)

        self.interface_label = tk.Label(root, text="", font=("Arial", 10))
        self.interface_label.pack(side="bottom", pady=5)

        Path(LOCAL_DIR).mkdir(parents=True, exist_ok=True)
        Path(SYNC_DEST_BASE).mkdir(parents=True, exist_ok=True)

        self._sync_lock = threading.Lock()
        self._manifest_lock = threading.Lock()
        self._uploaded = self._load_manifest()

        self.monitor_thread = threading.Thread(target=self.monitor_ethernet, daemon=True)
        self.monitor_thread.start()

    # --- Thread-safe UI helpers ---

    def _ui(self, fn, *args, **kwargs):
        self.root.after(0, lambda: fn(*args, **kwargs))

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}\n"
        print(line, end="")

        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self._ui(_append)

    def update_ssh_status(self, status):
        self._ui(self.ssh_status_label.config, text=f"SSH Status: {status}")

    def update_status(self, status):
        self._ui(self.rsync_status_label.config, text=f"Status: {status}")

    def update_current_file(self, name):
        self._ui(self.current_file_label.config, text=f"Current file: {name}")

    def set_progress(self, value, maximum=None):
        def _apply():
            if maximum is not None:
                self.progress_bar["maximum"] = maximum
            self.progress_bar["value"] = value
        self._ui(_apply)

    def set_file_count(self, text):
        self._ui(self.file_count_label.config, text=text)

    # --- Upload manifest ---

    def _load_manifest(self):
        try:
            with open(UPLOAD_MANIFEST, "r") as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def _save_manifest(self):
        with self._manifest_lock:
            tmp = UPLOAD_MANIFEST + ".tmp"
            with open(tmp, "w") as f:
                json.dump(sorted(self._uploaded), f)
            Path(tmp).replace(UPLOAD_MANIFEST)

    def _mark_uploaded(self, name):
        with self._manifest_lock:
            self._uploaded.add(name)
        self._save_manifest()

    # --- Network / sync logic ---

    def is_ssh_available(self):
        try:
            with socket.create_connection((REMOTE_HOST, SSH_PORT), timeout=2):
                self.update_ssh_status("Available")
                return True
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            self.update_ssh_status(f"Unavailable: {e}")
            return False

    def list_remote_files(self):
        ssh_command = [
            "ssh", "-i", SSH_KEY, f"{REMOTE_USER}@{REMOTE_HOST}",
            f"ls {REMOTE_DIR}",
        ]
        self.log(f"$ {' '.join(ssh_command)}")
        try:
            result = subprocess.run(
                ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, check=True,
            )
            remote_files = [name for name in result.stdout.splitlines() if name]
            self.log(f"Remote listing: {len(remote_files)} file(s)")
            return set(remote_files)
        except subprocess.CalledProcessError as e:
            self.update_status("SSH Error: Unable to list files")
            self.log(f"SSH list failed (exit {e.returncode}): {e.stderr.strip()}")
            return set()

    def list_local_files(self):
        local_files = set()
        base = Path(SYNC_DEST_BASE)
        if not base.exists():
            return local_files
        for path in base.rglob("*"):
            if path.is_file():
                local_files.add(path.name)
        return local_files

    def _run_streaming(self, command):
        self.log(f"$ {' '.join(command)}")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for raw in process.stdout:
            line = raw.rstrip()
            if line:
                self.log(line)
        process.wait()
        return process.returncode

    def _upload_files(self, file_paths):
        """POST all files in a single bulk request. Return True on 2xx."""
        if not file_paths:
            return True
        self.log(f"Bulk uploading {len(file_paths)} file(s) -> {UPLOAD_URL}")
        handles = []
        try:
            multipart = []
            for path in file_paths:
                handle = open(path, "rb")
                handles.append(handle)
                multipart.append(("files", (path.name, handle)))
            response = requests.post(UPLOAD_URL, files=multipart, timeout=600)
            self.log(f"Upload response: {response.status_code} {response.reason}")
            if not response.ok:
                self.log(f"Response body: {response.text[:500]}")
                return False
            return True
        except requests.RequestException as e:
            self.log(f"Bulk upload error: {e}")
            return False
        finally:
            for handle in handles:
                handle.close()

    def sync_directory(self):
        if not self._sync_lock.acquire(blocking=False):
            self.log("Sync already running, skipping duplicate trigger")
            return
        try:
            remote_files = self.list_remote_files()
            local_files = self.list_local_files()

            # A file is "new" only if it is neither present on disk nor already
            # uploaded according to the manifest. This is the single source of
            # truth that prevents duplicate uploads.
            candidates = sorted(remote_files - local_files - self._uploaded)

            if not candidates:
                self.update_status("No New Files to Sync")
                self.update_current_file("-")
                self.log("No new files to sync")
                return

            self.log(f"Found {len(candidates)} new file(s) to sync")
            self.set_progress(0, maximum=len(candidates))
            self.update_status("Rsyncing files...")

            downloaded = []
            for idx, name in enumerate(candidates, 1):
                self.update_current_file(name)
                self.set_file_count(f"Files transferred: {idx - 1} / {len(candidates)}")

                rsync_command = [
                    "rsync", "-avz", "--progress",
                    "-e", f"ssh -i {SSH_KEY} -o StrictHostKeyChecking=no",
                    f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/{name}",
                    LOCAL_DIR + "/",
                ]
                rc = self._run_streaming(rsync_command)
                if rc != 0:
                    self.log(f"Rsync failed for {name} (exit {rc}); skipping")
                    self.set_progress(idx)
                    continue

                local_path = Path(LOCAL_DIR) / name
                if not local_path.exists():
                    self.log(f"Expected file missing after rsync: {local_path}; skipping")
                    self.set_progress(idx)
                    continue

                downloaded.append(local_path)
                self.set_progress(idx)
                self.set_file_count(f"Files transferred: {idx} / {len(candidates)}")

            self.update_current_file("-")
            self.update_status("Rsync completed")
            self.log(f"Rsync stage complete ({len(downloaded)}/{len(candidates)} downloaded)")

            if not downloaded:
                return

            self.update_status("Uploading to backend...")
            if self._upload_files(downloaded):
                for path in downloaded:
                    self._mark_uploaded(path.name)
                self.update_status("Backend upload succeeded")
                self.move_to_timestamped_folder([p.name for p in downloaded])
            else:
                self.update_status("Backend upload failed")
                self.log("Bulk upload failed; leaving files staged for retry")
        finally:
            self._sync_lock.release()

    def move_to_timestamped_folder(self, filenames):
        """Move the specific files we just uploaded into a timestamped folder."""
        if not filenames:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        destination = Path(SYNC_DEST_BASE) / timestamp

        try:
            destination.mkdir(parents=True, exist_ok=True)
            self.set_progress(0, maximum=len(filenames))
            self.update_status("Archiving uploaded files...")
            self.log(f"Moving {len(filenames)} file(s) to {destination}")

            for idx, name in enumerate(filenames, 1):
                src = Path(LOCAL_DIR) / name
                self.update_current_file(name)
                if not src.exists():
                    self.log(f"Skip archive: {src} missing")
                elif src.resolve() == (destination / name).resolve():
                    self.log(f"Skip archive: {src} already in destination")
                else:
                    shutil.move(str(src), str(destination / name))
                    self.log(f"Archived {name}")

                self.set_progress(idx)
                self.set_file_count(f"Files archived: {idx} / {len(filenames)}")

            self.update_status(f"Archived to: {destination}")
            self.update_current_file("-")
            self.log(f"Archive complete -> {destination}")
        except Exception as e:
            self.update_status("Error: Archive failed")
            self.log(f"Archive failed: {e}")

    def update_interface_list(self):
        net_if_addrs = psutil.net_if_addrs()
        ethernet_interfaces = [
            iface for iface in net_if_addrs
            if any(addr.family == socket.AF_INET for addr in net_if_addrs[iface])
        ]
        self._ui(
            self.interface_label.config,
            text=f"Available Ethernet Interfaces: {', '.join(ethernet_interfaces)}",
        )

    def monitor_ethernet(self):
        while True:
            self.update_interface_list()
            net_if_addrs = psutil.net_if_addrs()
            if INTERFACE in net_if_addrs:
                if any(addr.family == socket.AF_INET for addr in net_if_addrs[INTERFACE]):
                    self.update_ssh_status(f"{INTERFACE} Connected")
                    if self.is_ssh_available():
                        self.sync_directory()
            time.sleep(5)

    def force_check(self):
        self.update_ssh_status("Forcing a check of connected devices...")
        self.log("Force Offload pressed")
        threading.Thread(target=self._force_check_worker, daemon=True).start()

    def _force_check_worker(self):
        if self.is_ssh_available():
            self.sync_directory()


def main():
    root = tk.Tk()
    app = EthernetSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
