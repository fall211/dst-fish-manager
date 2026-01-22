#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Discord service for running the bot in the background."""

import threading
from typing import Optional

from features.discord.bot_manager import DiscordBotManager
from utils.logger import discord_logger


class DiscordService:
    """Service for managing Discord bot lifecycle."""

    def __init__(self, manager_service):
        """
        Initialize Discord service.

        Args:
            manager_service: The main manager service instance
        """
        self.manager_service = manager_service

        self.bot_manager: Optional[DiscordBotManager] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.is_running = False

    def start(self):
        """Start the Discord bot in a background thread."""
        if self.is_running:
            discord_logger.warning("Discord bot is already running")
            return

        try:
            discord_logger.info("Starting Discord service")
            self.bot_manager = DiscordBotManager(self.manager_service)

            # Start bot in background thread
            self.bot_thread = threading.Thread(
                target=self.bot_manager.run_in_background,
                daemon=True,
                name="DiscordBot"
            )
            self.bot_thread.start()
            self.is_running = True
            discord_logger.info("Discord service started successfully")

        except Exception as e:
            discord_logger.error(f"Failed to start Discord service: {e}")
            import traceback
            traceback.print_exc()
            raise

    def stop(self):
        """Stop the Discord bot."""
        if not self.is_running:
            return

        try:
            discord_logger.info("Stopping Discord service")
            # Since the bot runs in a daemon thread, it will be killed when the main process exits
            # No need to explicitly close the Discord client - it causes event loop conflicts
            self.is_running = False
            discord_logger.info("Discord service stopped (daemon thread will terminate)")
        except Exception as e:
            discord_logger.error(f"Error stopping Discord service: {e}")

    def is_enabled(self) -> bool:
        """Check if Discord integration is enabled."""
        import os
        return bool(os.getenv("DISCORD_BOT_TOKEN"))
