#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Shard manager for handling shard operations."""

from typing import List, Tuple

from services.systemd_service import SystemDService
from utils.config import Shard, read_desired_shards


class ShardManager:
    """Manages shard operations."""

    def __init__(self):
        self.systemd_service = SystemDService()

    def get_shards(self) -> List[Shard]:
        """
        Reads desired shards from the config file and gets their current status.
        """
        desired_shards = read_desired_shards()
        enabled_shards = self.systemd_service.get_systemd_instances(
            "list-unit-files", "enabled"
        )
        running_shards = self.systemd_service.get_systemd_instances(
            "list-units", "active"
        )

        shards = []
        for name in desired_shards:
            shard = Shard(name)
            shard.is_enabled = name in enabled_shards
            shard.is_running = name in running_shards
            shards.append(shard)
        return shards

    def control_shard(self, shard_name: str, action: str) -> Tuple[bool, str, str]:
        """
        Controls a single shard through systemd.
        Returns: (success, stdout, stderr)
        """
        return self.systemd_service.control_shard(shard_name, action)

    def control_all_shards(
        self, action: str, shard_list: List[Shard]
    ) -> Tuple[bool, str, str]:
        """
        Controls all shards in the list.
        Returns: (success, stdout, stderr)
        """
        names = [shard.name for shard in shard_list]
        return self.systemd_service.control_all_shards(action, names)

    def get_logs(self, shard_name: str, lines: int = 50) -> str:
        """Gets the latest journalctl logs for a shard."""
        return self.systemd_service.get_logs(shard_name, lines)

    def sync_shards(self) -> None:
        """
        Synchronizes systemd units with shards.conf.
        """
        desired_names = set(read_desired_shards())
        self.systemd_service.sync_shards_and_target(desired_names)
