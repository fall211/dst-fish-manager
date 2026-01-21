#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Status manager for handling server status operations."""

import os
import re
import time
from typing import Dict

from utils.config import config_manager, get_game_config


class StatusManager:
    """Manages server status operations."""

    @staticmethod
    def get_server_status(shard_name: str = "Master") -> Dict:
        config = get_game_config()
        cluster_name = config.get("CLUSTER_NAME", "MyDediServer")
        dst_dir = config.get("DONTSTARVE_DIR")
        log_path = dst_dir / cluster_name / shard_name / "server_log.txt"

        status = {
            "season": "Unknown",
            "day": "Unknown",
            "days_left": "Unknown",
            "phase": "Unknown",
            "players": [],
        }

        if not log_path.exists():
            available_clusters = config_manager.get_available_clusters()
            error_msg = f"Cluster '{cluster_name}' not found. Available: {', '.join(available_clusters) if available_clusters else 'None'}"
            return {**status, "season": error_msg, "error": True}

        try:
            with log_path.open("rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 32768), os.SEEK_SET)
                content = f.read().decode("utf-8", errors="ignore")

            # Parse Season and Day from c_dumpseasons()
            season_matches = re.findall(
                r"(?:\[Season\] Season:\s*|:\s*)(\w+)\s*(\d+)\s*(?:,\s*Remaining:|\s*->)\s*(\d+)\s*days?",
                content,
            )
            if season_matches:
                s_name, s_elapsed, s_rem = season_matches[-1]
                status["season"] = s_name.capitalize()
                status["day"] = str(int(s_elapsed) + 1)
                status["days_left"] = s_rem

            # Parse Day from explicit poll or natural World State logs
            day_matches = re.findall(
                r"(?:Current day:|\[World State\] day:)\s*(\d+)", content
            )
            if day_matches:
                last_match = day_matches[-1]
                if f"Current day: {last_match}" in content:
                    status["day"] = last_match
                else:
                    status["day"] = str(int(last_match) + 1)

            # Parse Phase
            phase_matches = re.findall(
                r"(?:Current phase:|\[World State\] phase:)\s*(\w+)", content
            )
            if phase_matches:
                status["phase"] = phase_matches[-1].capitalize()

            # Parse Players
            dumps = content.split("All players:")
            last_dump = dumps[-1] if dumps else content

            player_matches = re.findall(
                r"\[\d+\]\s+\((KU_[\w-]+)\)\s+(.*?)\s+<(.*?)>", last_dump
            )
            if player_matches:
                recent_players = {}
                for ku_id, name, char in player_matches:
                    recent_players[ku_id] = {"name": name, "char": char}

                status["players"] = list(recent_players.values())
            else:
                status["players"] = []

        except Exception:
            pass

        return status

    @staticmethod
    def request_status_update(shard_name: str = "Master") -> bool:
        """Sends Lua commands to the server to dump current status into the logs."""
        from features.chat.chat_manager import ChatManager

        commands = [
            "c_dumpseasons()",
            'print("Current day: " .. (TheWorld.components.worldstate.data.cycles + 1))',
            'print("Current phase: " .. TheWorld.components.worldstate.data.phase)',
            "c_listallplayers()",
        ]
        success = True
        for cmd in commands:
            s, _ = ChatManager.send_command(shard_name, cmd)
            if not s:
                success = False
            time.sleep(0.5)
        return success
