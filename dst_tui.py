#!/usr/bin/env python
# -*- coding: utf-8 -*-

import curses
import curses.textpad
import threading
import time

from manager import Manager


class NcursesApp:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.manager = Manager()
        self.shards = []
        self.selected_shard_idx = 0
        self.selected_action_idx = 0
        self.selected_global_action_idx = -1  # -1 means not selected
        self.last_refresh_time = 0

        self.log_viewer_active = False
        self.log_content = []
        self.log_scroll_pos = 0
        self.is_working = False  # Track background tasks

        self.setup_windows()

        # Catppuccin Mocha Palette
        if curses.can_change_color():
            # Define colors (scaled to 0-1000)
            curses.init_color(10, 117, 117, 180)  # Base (#1e1e2e)
            curses.init_color(11, 803, 839, 956)  # Text (#cdd6f4)
            curses.init_color(12, 705, 745, 996)  # Lavender (#b4befe)
            curses.init_color(13, 650, 890, 631)  # Green (#a6e3a1)
            curses.init_color(14, 952, 545, 658)  # Red (#f38ba8)
            curses.init_color(15, 976, 886, 686)  # Yellow (#f9e2af)
            curses.init_color(16, 192, 196, 266)  # Surface0 (#313244)
            curses.init_color(17, 423, 439, 525)  # Overlay0 (#6c7086)

            self.bg = 10
            self.fg = 11
            self.title = 12
            self.success = 13
            self.error = 14
            self.warning = 15
            self.highlight_bg = 16
            self.border = 17
        else:
            # Fallback for terminals that don't support init_color
            self.bg = curses.COLOR_BLACK
            self.fg = curses.COLOR_WHITE
            self.title = curses.COLOR_CYAN
            self.success = curses.COLOR_GREEN
            self.error = curses.COLOR_RED
            self.warning = curses.COLOR_YELLOW
            self.highlight_bg = curses.COLOR_WHITE
            self.border = curses.COLOR_BLUE

        curses.init_pair(1, self.fg, self.bg)  # Default text
        curses.init_pair(2, self.title, self.bg)  # Title (Lavender)
        curses.init_pair(3, self.success, self.bg)  # Success (Green)
        curses.init_pair(4, self.error, self.bg)  # Error (Red)
        curses.init_pair(5, self.warning, self.bg)  # Warning (Yellow)
        curses.init_pair(6, self.title, self.bg)  # Border (Lavender)
        curses.init_pair(7, self.bg, self.fg)  # Highlight (Inverted)
        curses.init_pair(8, self.fg, self.bg)  # Footer (Base background)

        # Box characters (btop style) - including junctions
        self.box_chars = {
            "tl": "╭",
            "tr": "╮",
            "bl": "╰",
            "br": "╯",
            "v": "│",
            "h": "─",
            "ml": "├",
            "mr": "┤",
            "mt": "┬",
            "mb": "┴",
        }

    def setup_windows(self):
        try:
            h, w = self.stdscr.getmaxyx()
            target_lw = int(w * 0.45) if w > 120 else w // 2
            lw = max(58, target_lw) if w > 80 else w // 2

            available_h = h - 3  # Reserve space for footer

            # Prevent negative heights
            if available_h < 10:  # Minimum height for all panes
                shards_h = global_h = available_h // 2
            else:
                shards_h = global_h = available_h // 2

            shards_y = 1
            global_y = shards_y + shards_h

            self.shards_win = self.stdscr.derwin(
                max(1, shards_h), max(1, lw), shards_y, 0
            )
            self.global_win = self.stdscr.derwin(
                max(1, global_h), max(1, lw), global_y, 0
            )
            self.right_pane = self.stdscr.derwin(
                max(1, available_h), max(1, w - lw), 1, lw
            )

            self.shards_win.bkgd(" ", curses.color_pair(1))
            self.global_win.bkgd(" ", curses.color_pair(1))
            self.right_pane.bkgd(" ", curses.color_pair(1))
            self.stdscr.bkgd(" ", curses.color_pair(1))
        except curses.error:
            pass

    def run(self):
        curses.curs_set(0)

        self.stdscr.nodelay(1)

        self.shards = self.manager.get_shards()
        while True:
            self.draw()

            key = self.stdscr.getch()

            if key == ord("q") or key == 27:  # q or Esc
                if self.log_viewer_active:
                    self.log_viewer_active = False
                    continue
                else:
                    break

            if key == curses.KEY_RESIZE:
                self.stdscr.clear()  # Force a full terminal clear/redraw
                self.setup_windows()
                continue

            if self.log_viewer_active:
                if key == curses.KEY_DOWN:
                    self.log_scroll_pos += 1
                elif key == curses.KEY_UP:
                    self.log_scroll_pos = max(0, self.log_scroll_pos - 1)
                elif key == curses.KEY_LEFT:
                    self.log_viewer_active = False
            else:
                self.handle_main_input(key)

            # Refresh shards periodically (every 2 seconds)
            current_time = time.time()
            if current_time - self.last_refresh_time > 2.0:
                if not self.log_viewer_active:
                    self.shards = self.manager.get_shards()
                self.last_refresh_time = current_time
            elif key == -1:
                # No input and no refresh needed, just wait a bit
                time.sleep(0.05)
                continue

    def handle_main_input(self, key):
        if key == curses.KEY_DOWN:
            if self.selected_global_action_idx != -1:
                # From SHARDS to GLOBAL
                if (
                    self.selected_global_action_idx >= 4
                ):  # Last row of global, nowhere to go
                    pass
                else:
                    self.selected_global_action_idx += 2
            elif self.shards and self.selected_shard_idx == len(self.shards) - 1:
                # From SHARDS to GLOBAL
                self.selected_global_action_idx = 0
            elif self.shards:
                self.selected_shard_idx += 1

        elif key == curses.KEY_UP:
            if self.selected_global_action_idx != -1:
                # From GLOBAL to SHARDS
                if self.selected_global_action_idx < 2:  # First row of global
                    self.selected_global_action_idx = -1
                else:
                    self.selected_global_action_idx -= 2
            else:
                self.selected_shard_idx = max(0, self.selected_shard_idx - 1)

        elif key == curses.KEY_RIGHT:
            if self.selected_global_action_idx != -1:
                self.selected_global_action_idx = (
                    self.selected_global_action_idx + 1
                ) % 6
            else:
                self.selected_action_idx = (self.selected_action_idx + 1) % 4

        elif key == curses.KEY_LEFT:
            if self.selected_global_action_idx != -1:
                self.selected_global_action_idx = (
                    self.selected_global_action_idx - 1
                ) % 6
            else:
                self.selected_action_idx = (self.selected_action_idx - 1) % 4

        elif key == ord("\n"):
            self.execute_action()

        elif key == ord("e"):
            self.execute_toggle_enable()
        elif key == ord("c"):
            self.prompt_for_chat()

    def execute_action(self):
        if self.is_working:
            return  # Prevent multiple simultaneous tasks

        if self.selected_global_action_idx != -1:
            # Reordered to match UI pairs: Start/Stop, Enable/Disable, Restart/Update
            actions = ["start", "stop", "enable", "disable", "restart", "update"]
            action = actions[self.selected_global_action_idx]

            if action == "update":
                self.manager.run_updater()
                self.shards = self.manager.get_shards()
            else:
                self.run_in_background(
                    self.manager.control_all_shards, action, self.shards
                )
            return

        if not self.shards:
            return

        shard = self.shards[self.selected_shard_idx]
        actions = ["start", "stop", "restart", "logs"]
        action = actions[self.selected_action_idx]

        if action == "logs":
            self.log_content = self.manager.get_logs(shard.name, lines=200).split("\n")
            self.log_viewer_active = True
            self.log_scroll_pos = 0
        else:
            self.run_in_background(self.manager.control_shard, shard.name, action)

    def prompt_for_chat(self):
        h, w = self.stdscr.getmaxyx()

        # Create a popup window for the chat input
        popup_h, popup_w = 3, w // 2
        popup_y = (h - popup_h) // 2
        popup_x = (w - popup_w) // 2

        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.bkgd(" ", curses.color_pair(1))
        popup.keypad(True)
        self.draw_block(popup, "Enter Chat Message")

        # Create a textpad for input
        input_win = popup.derwin(1, popup_w - 2, 1, 1)
        input_win.bkgd(" ", curses.color_pair(7))  # Highlight background

        self.stdscr.nodelay(0)  # Make getch blocking
        curses.curs_set(1)  # Show cursor

        popup.refresh()

        box = curses.textpad.Textbox(input_win)
        box.edit()
        message = box.gather().strip()

        curses.curs_set(0)
        self.stdscr.nodelay(1)  # Go back to non-blocking

        if message:
            success, msg = self.manager.send_chat_message("Master", message)
            if success:
                pass

    def execute_toggle_enable(self):
        if self.is_working or self.selected_global_action_idx != -1 or not self.shards:
            return
        shard = self.shards[self.selected_shard_idx]
        action = "disable" if shard.is_enabled else "enable"
        self.run_in_background(self.manager.control_shard, shard.name, action)

    def run_in_background(self, func, *args):
        def worker():
            self.is_working = True
            try:
                func(*args)
            finally:
                self.shards = self.manager.get_shards()
                self.is_working = False

        threading.Thread(target=worker, daemon=True).start()

    def draw_block(self, win, title=""):
        """Draws a themed box with a title on a subwindow."""
        try:
            h, w = win.getmaxyx()
            if h < 2 or w < 2:
                return

            win.attron(curses.color_pair(6))

            # Corners
            win.addstr(0, 0, self.box_chars["tl"])
            win.addstr(0, w - 1, self.box_chars["tr"])
            win.addstr(h - 1, 0, self.box_chars["bl"])
            try:
                win.addstr(h - 1, w - 1, self.box_chars["br"])
            except curses.error:
                try:
                    win.insstr(h - 1, w - 1, self.box_chars["br"])
                except curses.error:
                    pass

            # Lines
            for x in range(1, w - 1):
                win.addstr(0, x, self.box_chars["h"])
                win.addstr(h - 1, x, self.box_chars["h"])
            for y in range(1, h - 1):
                win.addstr(y, 0, self.box_chars["v"])
                win.addstr(y, w - 1, self.box_chars["v"])
            win.attroff(curses.color_pair(6))

            if title and w > len(title) + 4:
                win.addstr(0, 2, f" {title} ", curses.color_pair(2) | curses.A_BOLD)
        except curses.error:
            pass

    def draw(self):
        h, w = self.stdscr.getmaxyx()

        # Technical minimal size
        if h < 12 or w < 40:
            self.stdscr.erase()
            msg = "Terminal too small"
            start_x = (w - len(msg)) // 2
            start_y = h // 2
            if start_y >= 0 and start_x >= 0 and start_x + len(msg) < w:
                self.stdscr.addstr(start_y, start_x, msg, curses.color_pair(4))
            self.stdscr.refresh()
            return

        self.stdscr.erase()
        self.shards_win.erase()
        self.global_win.erase()
        self.right_pane.erase()

        # Draw Title
        title = "DST SYSTEMD MANAGER"
        if self.is_working:
            title += " [WAITING...]"
        start_x = (w - len(title)) // 2
        if start_x > 0 and w > len(title):
            self.stdscr.addstr(0, start_x, title, curses.color_pair(2) | curses.A_BOLD)

        # Draw Blocks
        self.draw_block(self.shards_win, "SHARDS")
        self.draw_block(self.global_win, "GLOBAL")
        self.draw_block(self.right_pane, "LOGS")

        # Shard Management Content
        actions = ["🚀 Start", "🛑 Stop", "🔄 Restart", "📜 Logs"]
        for i, shard in enumerate(self.shards):
            # This block is wrapped to prevent crashes on terminal resize
            try:
                wh, ww = self.shards_win.getmaxyx()
                if i >= wh - 2:  # Stop if not enough vertical space
                    break

                marker = (
                    ">"
                    if (
                        i == self.selected_shard_idx
                        and self.selected_global_action_idx == -1
                    )
                    else " "
                )
                self.shards_win.addstr(i + 1, 1, marker, curses.color_pair(2))

                # Stop drawing this line if the window is too narrow
                if ww < 14:
                    continue

                self.shards_win.addstr(i + 1, 2, shard.name[:10])

                # Status
                status_color = (
                    curses.color_pair(3) if shard.is_running else curses.color_pair(4)
                )
                status_icon = "●" if shard.is_running else "○"
                self.shards_win.addstr(i + 1, 13, status_icon, status_color)

                # Buttons
                for j, label in enumerate(actions):
                    btn_col = 14 + j * 11  # Increased to 11 to avoid clipping

                    # Don't draw button if it would go off screen
                    if btn_col + len(label) + 3 >= ww:
                        break

                    style = curses.color_pair(1)
                    if (
                        i == self.selected_shard_idx
                        and j == self.selected_action_idx
                        and self.selected_global_action_idx == -1
                    ):
                        style = curses.color_pair(7)

                    self.shards_win.addstr(i + 1, btn_col, f" {label} ", style)
            except curses.error:
                # Ignore curses errors, which can happen on rapid resizing.
                # The screen will correct itself on the next draw cycle.
                pass

        # Global Control Content
        gl_actions = [
            ("Start", 3),
            ("Stop", 4),
            ("Enable", 3),
            ("Disable", 4),
            ("Restart", 6),
            ("Update", 2),
        ]
        for i, (label, color_pair) in enumerate(gl_actions):
            try:
                gh, gw = self.global_win.getmaxyx()
                row = 1 + (i // 2)
                col = 2 + (i % 2) * 19

                # Don't draw if it would go off screen
                if row >= gh - 1 or col + len(label) + 2 >= gw:
                    continue

                style = curses.color_pair(color_pair)
                if i == self.selected_global_action_idx:
                    style = curses.color_pair(7)

                marker = ">" if i == self.selected_global_action_idx else " "
                self.global_win.addstr(row, col, f"{marker}{label}", style)
            except curses.error:
                # Ignore curses errors on resize
                pass

        # Right pane content - show chat logs when not viewing logs
        if self.log_viewer_active:
            lh, lw_box = self.right_pane.getmaxyx()
            # Draw log content inside the box border
            for i in range(1, lh - 1):
                idx = self.log_scroll_pos + i - 1
                if idx < len(self.log_content) and lw_box > 2:
                    try:
                        line = self.log_content[idx]
                        self.right_pane.addstr(i, 1, line[: lw_box - 2])
                    except curses.error:
                        # Ignore errors on resize
                        pass
        else:
            # Show game chat logs with proper formatting
            chat_logs = self.manager.get_chat_logs(50)
            lh, lw_box = self.right_pane.getmaxyx()

            # Calculate available width (account for borders and margins)
            available_width = lw_box - 2  # Subtract 2 for borders

            if chat_logs and available_width > 0:
                # Show the actual chat logs (inside the box borders)
                # Display only as many lines as fit vertically inside the borders
                display_lines = (
                    chat_logs[-(lh - 2) :] if len(chat_logs) >= (lh - 2) else chat_logs
                )
                for i, line in enumerate(display_lines):
                    try:
                        y = i + 1  # Start from line 1 (below top border)

                        # Truncate line to fit in available width
                        if line and len(line) > available_width:
                            line = line[: available_width - 3] + "..."

                        self.right_pane.addstr(y, 1, line, curses.color_pair(1))
                    except curses.error:
                        # Ignore errors on resize
                        pass
            else:
                # Show info message when no chat logs available
                info_msg = "Game chat will appear here"
                if lh > 2 and lw_box > len(info_msg) + 2:
                    try:
                        # Center the message properly
                        start_y = lh // 2
                        start_x = 1 + (available_width - len(info_msg)) // 2
                        self.right_pane.addstr(
                            start_y, start_x, info_msg, curses.color_pair(8)
                        )
                    except curses.error:
                        # Ignore errors on resize
                        pass

        # Footer
        footer = " ARROWS:NAV | ENTER:RUN | E:ENABLE | Q:BACK "
        if h > 0 and w > len(footer) + 2:  # +2 for margin
            self.stdscr.addstr(h - 1, 1, footer, curses.color_pair(8))

        # Chat info in footer
        chat_info = " Press C to chat "
        if h > 0 and w > len(chat_info) + 1:
            self.stdscr.addstr(
                h - 1, w - len(chat_info) - 1, chat_info, curses.color_pair(2)
            )

        self.stdscr.noutrefresh()
        self.shards_win.noutrefresh()
        self.global_win.noutrefresh()
        self.right_pane.noutrefresh()
        curses.doupdate()


def main(stdscr):
    app = NcursesApp(stdscr)
    app.run()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"An error occurred: {e}")
