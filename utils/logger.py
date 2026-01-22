#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Centralized logging utility for DST Fish Manager."""

import logging
import logging.handlers
from collections import deque
from pathlib import Path
from typing import Optional, List


class InMemoryLogHandler(logging.Handler):
    """Custom log handler that stores logs in memory for TUI display."""

    def __init__(self, maxlen: int = 1000):
        """
        Initialize the in-memory log handler.

        Args:
            maxlen: Maximum number of log entries to keep in memory
        """
        super().__init__()
        self.logs = deque(maxlen=maxlen)
        # Note: Don't add an additional lock here - Handler base class already has one!

    def emit(self, record: logging.LogRecord):
        """Emit a log record."""
        try:
            msg = self.format(record)
            # Don't use a lock here - Handler.emit() is already called within acquire/release
            self.logs.append(msg)
        except (AttributeError, MemoryError):
            self.handleError(record)

    def get_logs(self, lines: Optional[int] = None) -> List[str]:
        """
        Get recent log entries.

        Args:
            lines: Number of recent lines to retrieve (None for all)

        Returns:
            List of log messages
        """
        # Use the handler's lock for thread safety
        self.acquire()
        try:
            if lines is None:
                return list(self.logs)
            return list(self.logs)[-lines:]
        finally:
            self.release()

    def clear(self):
        """Clear all stored logs."""
        self.acquire()
        try:
            self.logs.clear()
        finally:
            self.release()


class DiscordBotLogger:
    """Logger specifically for Discord bot operations."""

    def __init__(self):
        """Initialize the Discord bot logger."""
        self.logger = logging.getLogger("discord_bot")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # Clear any existing handlers
        self.logger.handlers = []

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Create in-memory handler for TUI
        self.memory_handler = InMemoryLogHandler(maxlen=1000)
        self.memory_handler.setLevel(logging.INFO)
        self.memory_handler.setFormatter(formatter)
        self.logger.addHandler(self.memory_handler)

        # Create file handler for persistent logging
        self.log_file_path = None
        try:
            # Create logs directory if it doesn't exist
            log_dir = Path.home() / ".local" / "share" / "dst-fish-manager" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / "discord_bot.log"

            # Use RotatingFileHandler to prevent log file from growing too large
            file_handler = logging.handlers.RotatingFileHandler(
                str(log_file),
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

            self.log_file_path = str(log_file)
        except (OSError, IOError) as e:  # noqa: BLE001
            # If file logging fails, just continue with memory logging
            self.logger.warning("Failed to setup file logging: %s", e)

    def get_logger(self) -> logging.Logger:
        """Get the Discord bot logger instance."""
        return self.logger

    def get_logs(self, lines: Optional[int] = None) -> List[str]:
        """
        Get recent log entries from memory.

        Args:
            lines: Number of recent lines to retrieve (None for all)

        Returns:
            List of log messages
        """
        if self.memory_handler:
            return self.memory_handler.get_logs(lines)
        return []

    def get_log_file_path(self) -> Optional[str]:
        """Get the path to the log file."""
        return self.log_file_path

    def read_log_file(self, max_lines: int = 500) -> List[str]:
        """
        Read log entries from the log file.

        Args:
            max_lines: Maximum number of recent lines to read

        Returns:
            List of log lines, or error message if reading fails
        """
        log_file_path = self.get_log_file_path()
        if not log_file_path or not Path(log_file_path).exists():
            return []

        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return [line.rstrip("\n") for line in lines[-max_lines:]]
        except (OSError, IOError) as e:
            return [f"Error reading log file: {e}"]
        except Exception as e:  # noqa: BLE001
            return [f"Error reading log file: {e}"]

    def get_log_file_content(self, max_lines: int = 500) -> List[str]:
        """
        Get log file content with fallback messages if unavailable.

        Args:
            max_lines: Maximum number of recent lines to read

        Returns:
            List of log lines with helpful messages if no logs available
        """
        log_content = self.read_log_file(max_lines)

        if not log_content:
            log_file_path = self.get_log_file_path()
            log_content = [
                "No Discord bot logs available yet.",
                "",
                "The Discord bot will log activity here including:",
                "  - Bot startup and initialization",
                "  - Command executions",
                "  - Server control operations",
                "  - Chat activity detection",
                "  - Errors and warnings",
                "",
                f"Log file: {log_file_path or 'Not configured'}",
            ]

        return log_content

    def clear_logs(self):
        """Clear all stored in-memory logs."""
        if self.memory_handler:
            self.memory_handler.clear()

    # Convenience methods
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)

    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)


# Global instance
discord_logger = DiscordBotLogger()
