# DST Fish Manager

A terminal user interface (TUI) for managing Don't Starve Together (DST) dedicated servers using `systemd`.
Built with standard Python `curses` module.

## Features

-   **Per-Shard Controls**: Independent Start, Stop, and Restart actions for each shard.
-   **Live Log Viewer**: Real-time access to journalctl logs within the application.
-   **Systemd Powered**: Robust process management leveraging `systemd --user` instances.
-   **Built-in Updater**: Safe and easy server updates using the integrated updater runner.
-   **Chat Viewer**: View game chat logs in the right panel.

## Prerequisites

-   **Python 3.8+**
-   **Fish Shell**: Required for the server runner and updater scripts.
-   **Systemd**
-   **Unicode Terminal**: Required for rendering emojis and box-drawing characters.

## Installation

1.  **Scripts Setup**:
    Ensure the helper scripts (`dst-server`, `dst-updater`) are executable and placed in `~/.local/bin/`.
    The core management logic is handled by `manager.py`.

2.  **Configuration**:
    Create `~/.config/dontstarve/shards.conf` with your shard names, e.g.:
    ```text
    Master
    Caves
    Shard1
    ```

3.  **Game Paths**:
    Customize `~/.config/dontstarve/config` if your game or steamcmd is installed in non-standard locations.

4.  **Systemd Units**:
    Install `dontstarve@.service` and `dontstarve.target` in `~/.config/systemd/user/`.

## Usage

Launch the TUI application:

```bash
python3 dst_tui.py
```

**Keyboard Controls:**
- **Arrow Keys**: Navigate between shards and actions
- **Enter**: Execute selected action
- **E**: Toggle enable/disable for selected shard
- **C**: Open chat input to send messages to players
- **Q/Esc**: Quit the application

Or use the CLI for synchronization and manual management:

```bash
python3 manager.py sync
python3 manager.py list
```
