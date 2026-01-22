#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Discord bot manager for DST Fish Manager."""

import asyncio
import os
from typing import Optional, Dict, Any
from enum import Enum

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.logger import discord_logger


class ServerState(Enum):
    """Server state enumeration."""
    STARTING = 1
    RUNNING = 2
    STOPPING = 3
    STOPPED = 4
    RESTARTING = 5


class DiscordBotManager:
    """Manages Discord bot integration with DST Fish Manager."""

    def __init__(self, manager_service):
        """
        Initialize Discord bot manager.

        Args:
            manager_service: The main manager service instance
        """
        self.manager_service = manager_service

        # Bot configuration
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN")
        self.guild_id = os.getenv("DISCORD_GUILD_ID")
        self.chat_channel_id = os.getenv("DISCORD_CHAT_CHANNEL_ID")

        discord_logger.info("Initializing Discord bot manager")

        if not self.bot_token:
            discord_logger.error("DISCORD_BOT_TOKEN environment variable not set")
            raise ValueError("DISCORD_BOT_TOKEN environment variable not set")

        if self.guild_id:
            discord_logger.info(f"Configured for guild ID: {self.guild_id}")
        if self.chat_channel_id:
            discord_logger.info(f"Chat relay channel ID: {self.chat_channel_id}")

        # Bot state
        self.server_state = ServerState.STOPPED
        self.previous_chat_log_count = 0
        self.just_started = False

        # Initialize Discord client
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        self.client = DiscordClient(self, intents=intents)
        self.tree = app_commands.CommandTree(self.client)

        # Setup commands
        self._setup_commands()

        # Setup error handler for app commands
        self.tree.error(self._on_app_command_error)

    def _setup_commands(self):
        """Setup Discord slash commands."""
        discord_logger.info("Setting up Discord slash commands")
        guild = discord.Object(id=int(self.guild_id)) if self.guild_id else None
        discord_logger.info(f"Commands will be registered to: {'guild ' + self.guild_id if guild else 'globally'}")

        @self.tree.command(
            name="panel",
            description="Opens the server control panel.",
            guild=guild
        )
        async def panel(interaction: discord.Interaction):
            discord_logger.info(f"User {interaction.user} opened the panel")
            await interaction.response.send_message(view=PanelMenu(self))

        @self.tree.command(
            name="status",
            description="Gets the server status.",
            guild=guild
        )
        async def status(interaction: discord.Interaction):
            discord_logger.info(f"User {interaction.user} requested server status")
            await interaction.response.defer(ephemeral=True)

            shards = self.manager_service.get_shards()
            status_lines = ["**Server Status:**\n"]

            for shard in shards:
                emoji = "🟢" if shard.is_running else "🔴"
                status_lines.append(f"{emoji} **{shard.name}**: {shard.status}")

            discord_logger.info(f"Sending status for {len(shards)} shards")
            await interaction.followup.send("\n".join(status_lines), ephemeral=True)

        @self.tree.command(
            name="announce",
            description="Send an announcement to the server.",
            guild=guild
        )
        async def announce(interaction: discord.Interaction, message: str, shard: str = "Master"):
            discord_logger.info(f"User {interaction.user} sending announcement to {shard}: {message}")
            await interaction.response.defer(ephemeral=True)

            success, result = self.manager_service.send_chat_message(shard, f"[Discord] {message}")

            if success:
                discord_logger.info(f"Announcement sent successfully to {shard}")
                await interaction.followup.send(f"Announcement sent to {shard}!", ephemeral=True)
            else:
                discord_logger.error(f"Failed to send announcement to {shard}: {result}")
                await interaction.followup.send(f"Failed to send announcement: {result}", ephemeral=True)

        @self.tree.command(
            name="players",
            description="List players on the server.",
            guild=guild
        )
        async def players(interaction: discord.Interaction):
            discord_logger.info(f"User {interaction.user} requested player list")
            await interaction.response.defer(ephemeral=True)

            # Request status update first
            self.manager_service.request_status_update()
            await asyncio.sleep(2)  # Wait for status update

            status = self.manager_service.get_server_status()

            if status and "players" in status:
                player_list = status["players"]
                if player_list:
                    discord_logger.info(f"Found {len(player_list)} players online")
                    players_text = "\n".join([f"• {p}" for p in player_list])
                    await interaction.followup.send(f"**Players Online:**\n{players_text}", ephemeral=True)
                else:
                    discord_logger.info("No players currently online")
                    await interaction.followup.send("No players online.", ephemeral=True)
            else:
                discord_logger.warning("Could not retrieve player list from server")
                await interaction.followup.send("Could not retrieve player list.", ephemeral=True)

        discord_logger.info(f"Registered {len(self.tree.get_commands(guild=guild))} commands: {', '.join([cmd.name for cmd in self.tree.get_commands(guild=guild)])}")

    async def start(self):
        """Start the Discord bot."""
        try:
            discord_logger.info("Starting Discord bot connection")
            await self.client.start(self.bot_token)
        except Exception as e:
            discord_logger.error(f"Failed to start Discord bot: {e}")
            raise

    async def stop(self):
        """Stop the Discord bot."""
        discord_logger.info("Stopping Discord bot")
        await self.client.close()

    async def _on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle app command errors."""
        discord_logger.error(f"App command error from {interaction.user} in command '{interaction.command.name if interaction.command else 'unknown'}': {error}")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {str(error)}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {str(error)}", ephemeral=True)
        except Exception as e:
            discord_logger.error(f"Failed to send error message: {e}")

    def run_in_background(self):
        """Run the Discord bot in a background thread."""
        discord_logger.info("Running Discord bot in background thread")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.start())
        except Exception as e:
            discord_logger.error(f"Error in Discord bot background thread: {e}")
        finally:
            loop.close()


class DiscordClient(discord.Client):
    """Custom Discord client."""

    def __init__(self, bot_manager: DiscordBotManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot_manager = bot_manager
        self.synced = False
        self.added = False

    async def on_ready(self):
        """Handle bot ready event."""
        discord_logger.info(f"Discord bot logged in as {self.user.name} (ID: {self.user.id})")

        try:
            if self.bot_manager.guild_id:
                discord_logger.info(f"Syncing commands to guild {self.bot_manager.guild_id}")
                synced = await self.bot_manager.tree.sync(guild=discord.Object(id=int(self.bot_manager.guild_id)))
                discord_logger.info(f"Synced {len(synced)} command(s) to guild: {[cmd.name for cmd in synced]}")
            else:
                discord_logger.info("Syncing commands globally (this may take up to 1 hour to appear)")
                synced = await self.bot_manager.tree.sync()
                discord_logger.info(f"Synced {len(synced)} command(s) globally: {[cmd.name for cmd in synced]}")

            self.synced = True
            discord_logger.info(f"Commands synced successfully. Bot is ready to receive interactions in guild {self.bot_manager.guild_id if self.bot_manager.guild_id else 'all guilds'}")
        except Exception as e:
            discord_logger.error(f"Failed to sync commands: {e}", exc_info=True)

        if not self.added:
            self.add_view(PanelMenu(self.bot_manager))
            self.added = True
            discord_logger.info("Panel menu view added")

        await self.change_presence(
            activity=discord.Activity(
                name="DST Server",
                type=discord.ActivityType.watching
            )
        )

        # Start chat log monitoring
        if not self.send_chat_log.is_running():
            discord_logger.info("Starting chat log monitoring")
            self.send_chat_log.start()

    async def on_command_error(self, interaction: discord.Interaction, error: Exception):
        """Handle command errors."""
        discord_logger.error(f"Command error from {interaction.user}: {error}")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"Error: {error}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Error: {error}", ephemeral=True)
        except:
            pass

    async def on_interaction(self, interaction: discord.Interaction):
        """Handle all interactions for debugging."""
        try:
            command_name = interaction.command.name if interaction.command else 'N/A'
            discord_logger.info(f"Received interaction from {interaction.user} (ID: {interaction.user.id}): type={interaction.type}, command={command_name}, guild={interaction.guild_id}")
        except Exception as e:
            discord_logger.error(f"Error logging interaction: {e}")

    async def on_message(self, message):
        """Handle incoming messages."""
        if message.author == self.user:
            return

        # Relay Discord messages to game server
        if (self.bot_manager.chat_channel_id and
            message.channel.id == int(self.bot_manager.chat_channel_id)):

            if self.bot_manager.server_state == ServerState.STOPPED:
                discord_logger.debug("Skipping message relay - server is stopped")
                return

            # Remove emojis and format message
            msg = message.content
            full_message = f"[Discord] {message.author.display_name}: {msg}"

            discord_logger.info(f"Relaying Discord message from {message.author.display_name}: {msg}")

            # Send to all running shards
            shards = self.bot_manager.manager_service.get_shards()
            relay_count = 0
            for shard in shards:
                if shard.is_running:
                    self.bot_manager.manager_service.send_chat_message(shard.name, full_message)
                    relay_count += 1

            discord_logger.info(f"Message relayed to {relay_count} running shard(s)")

    @tasks.loop(seconds=5)
    async def send_chat_log(self):
        """Monitor and relay chat logs to Discord."""
        if not self.bot_manager.chat_channel_id:
            return

        try:
            chat_logs = self.bot_manager.manager_service.get_chat_logs(lines=100)
            current_count = len(chat_logs)

            # Handle initial startup
            if self.bot_manager.just_started:
                if self.bot_manager.previous_chat_log_count - current_count > 25:
                    return
                self.bot_manager.just_started = False
                discord_logger.info("Chat log monitoring initialized")

            # Send new messages
            if current_count > self.bot_manager.previous_chat_log_count:
                new_messages = chat_logs[self.bot_manager.previous_chat_log_count:]
                # Chat relay to Discord disabled to reduce spam
                # Only log locally
                if len(new_messages) > 0:
                    discord_logger.info(f"Detected {len(new_messages)} new game chat message(s)")

                self.bot_manager.previous_chat_log_count = current_count
        except Exception as e:
            discord_logger.error(f"Error in chat log monitoring: {e}")


class PanelMenu(discord.ui.View):
    """Discord UI panel for server control."""

    def __init__(self, bot_manager: DiscordBotManager):
        super().__init__(timeout=None)
        self.bot_manager = bot_manager
        self.cooldown = commands.CooldownMapping.from_cooldown(
            1, 5, commands.BucketType.default
        )

    @discord.ui.button(
        label="Start Server",
        style=discord.ButtonStyle.success,
        custom_id="start",
        emoji="🟢"
    )
    async def start_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start the server."""
        bucket = self.cooldown.get_bucket(interaction.message)
        retry = bucket.update_rate_limit()
        if retry:
            return await interaction.response.send_message(
                "ERROR: Please do not spam commands.", ephemeral=True
            )

        discord_logger.info(f"User {interaction.user} initiated server start")
        await interaction.response.defer(ephemeral=True)

        shards = self.bot_manager.manager_service.get_shards()
        success, stdout, stderr = self.bot_manager.manager_service.control_all_shards("start", shards)

        if success:
            discord_logger.info("Server startup command executed successfully")
            await interaction.followup.send("Server startup initiated...", ephemeral=True)
            self.bot_manager.server_state = ServerState.RUNNING
            self.bot_manager.just_started = True
            self.bot_manager.previous_chat_log_count = 0
        else:
            discord_logger.error(f"Server startup failed: {stderr}")
            await interaction.followup.send(f"Failed to start server: {stderr}", ephemeral=True)

    @discord.ui.button(
        label="Stop Server",
        style=discord.ButtonStyle.danger,
        custom_id="stop",
        emoji="🔴"
    )
    async def stop_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop the server."""
        bucket = self.cooldown.get_bucket(interaction.message)
        retry = bucket.update_rate_limit()
        if retry:
            return await interaction.response.send_message(
                "ERROR: Please do not spam commands.", ephemeral=True
            )

        discord_logger.info(f"User {interaction.user} initiated server stop")
        await interaction.response.defer(ephemeral=True)

        # Announce shutdown
        discord_logger.info("Announcing server shutdown to players")
        self.bot_manager.manager_service.send_chat_message(
            "Master", "[Discord] Server is shutting down in 5 seconds."
        )
        await asyncio.sleep(5)

        self.bot_manager.server_state = ServerState.STOPPING

        shards = self.bot_manager.manager_service.get_shards()
        success, stdout, stderr = self.bot_manager.manager_service.control_all_shards("stop", shards)

        if success:
            discord_logger.info("Server shutdown command executed successfully")
            await interaction.followup.send("Server shutdown initiated...", ephemeral=True)
            self.bot_manager.server_state = ServerState.STOPPED
        else:
            discord_logger.error(f"Server shutdown failed: {stderr}")
            await interaction.followup.send(f"Failed to stop server: {stderr}", ephemeral=True)

    @discord.ui.button(
        label="Restart Server",
        style=discord.ButtonStyle.blurple,
        custom_id="restart",
        emoji="🔄"
    )
    async def restart_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Restart the server."""
        bucket = self.cooldown.get_bucket(interaction.message)
        retry = bucket.update_rate_limit()
        if retry:
            return await interaction.response.send_message(
                "ERROR: Please do not spam commands.", ephemeral=True
            )

        discord_logger.info(f"User {interaction.user} initiated server restart")
        await interaction.response.defer(ephemeral=True)

        # Announce restart
        discord_logger.info("Announcing server restart to players")
        self.bot_manager.manager_service.send_chat_message(
            "Master", "[Discord] Server is restarting in 5 seconds."
        )
        await asyncio.sleep(5)

        self.bot_manager.server_state = ServerState.RESTARTING

        shards = self.bot_manager.manager_service.get_shards()
        success, stdout, stderr = self.bot_manager.manager_service.control_all_shards("restart", shards)

        if success:
            discord_logger.info("Server restart command executed successfully")
            await interaction.followup.send("Server restart initiated...", ephemeral=True)
            await asyncio.sleep(30)
            self.bot_manager.server_state = ServerState.RUNNING
            self.bot_manager.just_started = True
            self.bot_manager.previous_chat_log_count = 0
        else:
            discord_logger.error(f"Server restart failed: {stderr}")
            await interaction.followup.send(f"Failed to restart server: {stderr}", ephemeral=True)

    @discord.ui.button(
        label="Update Server",
        style=discord.ButtonStyle.grey,
        custom_id="update",
        emoji="⬇️"
    )
    async def update_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Update the server."""
        bucket = self.cooldown.get_bucket(interaction.message)
        retry = bucket.update_rate_limit()
        if retry:
            return await interaction.response.send_message(
                "ERROR: Please do not spam commands.", ephemeral=True
            )

        discord_logger.info(f"User {interaction.user} initiated server update")
        await interaction.response.defer(ephemeral=True)

        await interaction.followup.send("Starting server update...", ephemeral=True)

        # Run updater
        success, stdout, stderr = self.bot_manager.manager_service.run_updater()

        if success:
            discord_logger.info("Server update completed successfully")
            await interaction.followup.send("Server updated successfully!", ephemeral=True)
        else:
            discord_logger.error(f"Server update failed: {stderr}")
            await interaction.followup.send(f"Update failed: {stderr}", ephemeral=True)
