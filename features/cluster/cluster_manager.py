#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Cluster management feature."""

from pathlib import Path
from typing import List, Optional

from utils.config import ConfigManager


class ClusterManager:
    """Manages game clusters and configuration."""

    def __init__(self):
        self.config_manager = ConfigManager()

    def get_available_clusters(self) -> List[str]:
        """Get list of available clusters."""
        return self.config_manager.get_available_clusters()

    def get_current_cluster(self) -> str:
        """Get currently selected cluster."""
        config = self.config_manager.read_config()
        return config.get("CLUSTER_NAME", "auto")

    def set_cluster(self, cluster_name: str) -> bool:
        """Set the active cluster."""
        return self.config_manager.update_config_value("CLUSTER_NAME", cluster_name)

    def get_cluster_info(self, cluster_name: str) -> Optional[dict]:
        """Get information about a specific cluster."""
        config = self.config_manager.read_config()
        dst_dir = Path(
            config.get("DONTSTARVE_DIR", "$HOME/.klei/DoNotStarveTogether")
        ).expanduser()

        cluster_path = dst_dir / cluster_name
        if not cluster_path.exists():
            return None

        cluster_ini = cluster_path / "cluster.ini"
        cluster_token = cluster_path / "cluster_token.txt"

        shards = []
        if cluster_path.is_dir():
            for item in cluster_path.iterdir():
                if item.is_dir() and (item / "server.ini").exists():
                    shards.append(item.name)

        return {
            "name": cluster_name,
            "path": cluster_path,
            "has_cluster_ini": cluster_ini.exists(),
            "has_token": cluster_token.exists(),
            "shards": sorted(shards),
        }


class BranchManager:
    """Manages game branch configuration."""

    def __init__(self):
        self.config_manager = ConfigManager()

    def get_available_branches(self) -> List[str]:
        """Get list of available branches."""
        return self.config_manager.get_available_branches()

    def get_current_branch(self) -> str:
        """Get currently selected branch."""
        config = self.config_manager.read_config()
        return config.get("BRANCH", "main")

    def set_branch(self, branch_name: str) -> bool:
        """Set the active branch."""
        if branch_name not in self.get_available_branches():
            return False
        return self.config_manager.update_config_value("BRANCH", branch_name)
