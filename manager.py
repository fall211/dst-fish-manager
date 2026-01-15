#!/usr/bin/env python
# -*- coding: utf-8 -*-

import collections
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Set

# --- Configuration ---
HOME_DIR = Path.home()
CONFIG_DIR = HOME_DIR / ".config" / "dontstarve"
SHARDS_FILE = CONFIG_DIR / "shards.conf"
GAME_CONFIG_FILE = CONFIG_DIR / "config"
UNIT_PREFIX = "dontstarve@"
UNIT_SUFFIX = ".service"


class Shard:
    """Represents a single server shard."""

    def __init__(self, name: str):
        self.name = name
        self.is_running = False
        self.is_enabled = False

    @property
    def unit_name(self) -> str:
        """The full systemd unit name."""
        return f"{UNIT_PREFIX}{self.name}{UNIT_SUFFIX}"

    def __repr__(self) -> str:
        return (
            f"Shard({self.name}, running={self.is_running}, enabled={self.is_enabled})"
        )


class Manager:
    """Handles all interactions with systemd and game files."""

    _game_config_cache: Dict[str, str] = {}

    @staticmethod
    def _run_systemctl_command(args: list[str]) -> tuple[bool, str, str]:
        """Runs a systemctl command and returns success, stdout, and stderr."""
        try:
            process = subprocess.run(
                ["systemctl", "--user", *args],
                capture_output=True,
                text=True,
                check=False,
            )
            return (
                process.returncode == 0,
                process.stdout.strip(),
                process.stderr.strip(),
            )
        except FileNotFoundError:
            return False, "", "systemctl command not found."

    @classmethod
    def _get_game_config(cls) -> Dict[str, str]:
        """Reads and caches the game config file."""
        if cls._game_config_cache:
            return cls._game_config_cache
        config = {}
        if GAME_CONFIG_FILE.is_file():
            with open(GAME_CONFIG_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # Use regex to handle potential quotes and comments
                    match = re.match(r'^\s*([^#\s=]+)\s*=\s*"?([^"]*)"?', line)
                    if match:
                        key, value = match.groups()
                        config[key] = os.path.expandvars(value)
        cls._game_config_cache = {
            "DONTSTARVE_DIR": config.get(
                "DONTSTARVE_DIR", HOME_DIR / ".klei" / "DoNotStarveTogether"
            ),
            "CLUSTER_NAME": config.get("CLUSTER_NAME", "MyDediServer"),
        }
        return cls._game_config_cache

    @classmethod
    def get_shards(cls) -> list[Shard]:
        """
        Reads desired shards from the config file and gets their current status.
        """
        desired_shards = cls.read_desired_shards()
        enabled_shards = cls._get_systemd_instances("list-unit-files", "enabled")
        running_shards = cls._get_systemd_instances("list-units", "active")

        shards = []
        for name in desired_shards:
            shard = Shard(name)
            shard.is_enabled = name in enabled_shards
            shard.is_running = name in running_shards
            shards.append(shard)
        return shards

    @staticmethod
    def read_desired_shards() -> list[str]:
        """Reads shard names from the shards.conf file."""
        if not SHARDS_FILE.is_file():
            return []
        with open(SHARDS_FILE, "r") as f:
            lines = f.readlines()
        return [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]

    @classmethod
    def _get_systemd_instances(cls, command: str, state_filter: str) -> Set[str]:
        """
        Helper to get a set of shard names from systemd commands.
        Args:
            command: The systemctl command to run (e.g., "list-units").
            state_filter: The state to look for (e.g., "active", "enabled").
        """
        args = [command, "--no-legend", f"{UNIT_PREFIX}*.service"]
        if command == "list-units":
            args.extend(["--state", state_filter])

        success, stdout, _ = cls._run_systemctl_command(args)
        if not success:
            return set()

        instances = set()
        for line in stdout.splitlines():
            parts = line.split()
            if not parts:
                continue

            unit_file = parts[0]
            # For list-unit-files, the state is in the second column
            if command == "list-unit-files" and len(parts) > 1:
                unit_state = parts[1]
                if unit_state != state_filter:
                    continue

            # Extract shard name from 'dontstarve@SHARD.service'
            if unit_file.startswith(UNIT_PREFIX) and unit_file.endswith(UNIT_SUFFIX):
                start = len(UNIT_PREFIX)
                end = len(unit_file) - len(UNIT_SUFFIX)
                shard_name = unit_file[start:end]
                if shard_name:
                    instances.add(shard_name)
        return instances

    @classmethod
    def control_shard(cls, shard_name: str, action: str) -> tuple[bool, str, str]:
        """
        Controls a single shard.
        Actions: "start", "stop", "enable", "disable", "restart"
        """
        unit_name = f"{UNIT_PREFIX}{shard_name}{UNIT_SUFFIX}"
        return cls._run_systemctl_command([action, unit_name])

    @classmethod
    def control_all_shards(cls, action: str, shard_list: list[Shard]) -> None:
        """
        Controls all shards in the list.
        Actions: "start", "stop", "restart"
        """
        for shard in shard_list:
            cls.control_shard(shard.name, action)

    @classmethod
    def get_logs(cls, shard_name: str, lines: int = 50) -> str:
        """Gets the latest journalctl logs for a shard."""
        unit_name = f"{UNIT_PREFIX}{shard_name}{UNIT_SUFFIX}"
        try:
            process = subprocess.run(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    unit_name,
                    "-n",
                    str(lines),
                    "--no-pager",
                    "-o",
                    "cat",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return (
                process.stdout.strip()
                if process.returncode == 0
                else process.stderr.strip()
            )
        except FileNotFoundError:
            return "journalctl command not found."

    @classmethod
    def get_chat_logs(cls, lines: int = 50) -> list[str]:
        """Gets the latest chat messages from the game chat log."""
        # Get cluster name from config
        config = cls._get_game_config()
        cluster_name = config.get("CLUSTER_NAME", "MyDediServer")

        # Construct the correct path to the chat log
        chat_log_path = (
            HOME_DIR
            / ".klei"
            / "DoNotStarveTogether"
            / cluster_name
            / "Master"
            / "server_chat_log.txt"
        )

        if not chat_log_path.exists():
            return [
                f"Chat log file not found at {chat_log_path}. Make sure the server is running."
            ]

        try:
            with open(chat_log_path, "r") as f:
                last_lines = collections.deque(f, maxlen=lines)
            if last_lines:
                return [line.strip() for line in last_lines]
            else:
                return ["No chat messages yet."]
        except Exception as e:
            return [f"Error reading chat log: {e}"]

    @classmethod
    def run_updater(cls) -> subprocess.Popen:
        """Runs the dst-updater script."""
        updater_path = Path(__file__).parent / ".local" / "bin" / "dst-updater"
        if not updater_path.is_file() or not os.access(updater_path, os.X_OK):
            # Fallback to the original location if not found next to the TUI script
            updater_path = HOME_DIR / ".local" / "bin" / "dst-updater"

        if not updater_path.is_file():
            raise FileNotFoundError(f"Updater script not found at {updater_path}")

        return subprocess.Popen(
            [str(updater_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    @classmethod
    def send_command(cls, shard_name: str, command: str) -> tuple[bool, str]:
        """Sends a command to the specified shard's console."""
        if shard_name != "Master":
            return False, "Commands can only be sent to the 'Master' shard."

        fifo_path = HOME_DIR / ".cache" / "dontstarve" / f"dst-{shard_name}.fifo"
        if not fifo_path.exists():
            return False, f"FIFO for shard '{shard_name}' not found at {fifo_path}"

        # In a TUI, you might want to open this once and keep it open.
        # For a single command, we open and close it.
        try:
            with open(fifo_path, "w") as f:
                f.write(command + "\n")
            return True, "Command sent successfully."
        except Exception as e:
            return False, f"Failed to write to FIFO: {e}"

    @classmethod
    def send_chat_message(cls, shard_name: str, message: str) -> tuple[bool, str]:
        """Sends a chat message using c_announce() command."""
        if shard_name != "Master":
            return False, "Chat messages can only be sent to the 'Master' shard."

        # Use c_announce() command to send chat message
        command = f'c_announce("{message}")'
        return cls.send_command(shard_name, command)

    @classmethod
    def sync_shards(cls) -> None:
        """
        Synchronizes systemd units with shards.conf:
        1. Enables and starts shards listed in shards.conf.
        2. Disables and stops shards NOT listed in shards.conf but currently active/enabled.
        """
        desired_names = set(cls.read_desired_shards())
        enabled_names = cls._get_systemd_instances("list-unit-files", "enabled")
        running_names = cls._get_systemd_instances("list-units", "active")

        # 1. Apply: Enable and start desired shards
        for name in desired_names:
            print(f"Ensuring {name} is enabled and started...")
            cls.control_shard(name, "enable")
            cls.control_shard(name, "start")

        # 2. Prune: Disable and stop shards not in desired list
        all_managed_names = enabled_names.union(running_names)
        for name in all_managed_names:
            if name not in desired_names:
                print(f"Pruning {name} (not in shards.conf)...")
                cls.control_shard(name, "stop")
                cls.control_shard(name, "disable")

        # Also ensure the main target is enabled
        cls._run_systemctl_command(["enable", "--now", "dontstarve.target"])


if __name__ == "__main__":
    import sys

    def print_help():
        print(f"Usage: {sys.argv[0]} <command> [args]")
        print("Commands:")
        print("  sync            - Synchronize systemd with shards.conf")
        print("  list            - List shards and their status")
        print("  start <name>    - Start a shard")
        print("  stop <name>     - Stop a shard")
        print("  restart <name>  - Restart a shard")
        print("  enable <name>   - Enable autostart for a shard")
        print("  disable <name>  - Disable autostart for a shard")
        print("  logs <name>     - Show logs for a shard")
        print("  cmd <command>   - Send command to the Master shard")
        print("  update          - Run server updater")

    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    cmd = sys.argv[1]
    manager = Manager()

    try:
        if cmd == "sync":
            manager.sync_shards()
        elif cmd == "list":
            for shard in manager.get_shards():
                print(shard)
        elif cmd in ["start", "stop", "restart", "enable", "disable"]:
            if len(sys.argv) < 3:
                print(f"Error: {cmd} requires a shard name")
                sys.exit(1)
            success, out, err = manager.control_shard(sys.argv[2], cmd)
            if not success:
                print(f"Error: {err}")
        elif cmd == "logs":
            if len(sys.argv) < 3:
                print("Error: logs requires a shard name")
                sys.exit(1)
            print(manager.get_logs(sys.argv[2]))
        elif cmd == "cmd":
            if len(sys.argv) < 3:
                print("Error: cmd requires a command string")
                sys.exit(1)
            command = " ".join(sys.argv[2:])
            success, msg = manager.send_command("Master", command)
            if not success:
                print(f"Error: {msg}")
            else:
                print(msg)
        elif cmd == "update":
            proc = manager.run_updater()
            if proc.stdout:
                for line in proc.stdout:
                    print(line, end="")
            proc.wait()
        else:
            print_help()
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
