"""SystemTray — pystray system tray icon with status indicators."""

from __future__ import annotations

import io
import logging
import threading
from queue import Queue

import PIL.Image as PILImage
import pystray

from voiceime.protocols import TrayCommand

logger = logging.getLogger("voiceime.ui.tray")

# Status constants
STATUS_READY = "ready"          # Green
STATUS_LOADING = "loading"      # Yellow
STATUS_RECORDING = "recording"  # Red
STATUS_ERROR = "error"          # Red
STATUS_PAUSED = "paused"        # Gray


def _create_icon(color: str) -> PILImage.Image:
    """Generate a simple 32x32 colored circle icon."""
    size = 32
    img = PILImage.new("RGBA", (size, size), (0, 0, 0, 0))

    colors = {
        "green": (76, 175, 80, 255),
        "yellow": (255, 193, 7, 255),
        "red": (244, 67, 54, 255),
        "gray": (158, 158, 158, 255),
    }
    rgba = colors.get(color, colors["green"])

    # Draw filled circle
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse([margin, margin, size - margin, size - margin], fill=rgba)

    return img


_STATUS_ICONS = {
    STATUS_READY: "green",
    STATUS_LOADING: "yellow",
    STATUS_RECORDING: "red",
    STATUS_ERROR: "red",
    STATUS_PAUSED: "gray",
}


class SystemTray:
    """System tray icon running in a dedicated thread."""

    def __init__(self, cmd_queue: Queue[TrayCommand]) -> None:
        self._cmd_queue = cmd_queue
        self._status = STATUS_READY
        self._paused = False
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start tray icon in a dedicated thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("SystemTray thread started")

    def stop(self) -> None:
        """Stop tray icon."""
        if self._icon:
            self._icon.stop()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("SystemTray stopped")

    def set_status(self, status: str) -> None:
        """Update tray icon to reflect current status."""
        self._status = status
        if self._icon:
            color = _STATUS_ICONS.get(status, "green")
            try:
                self._icon.icon = _create_icon(color)
                self._icon.title = f"VoiceIME — {status}"
            except Exception as exc:
                logger.warning("Failed to update tray icon: %s", exc)

    def _run(self) -> None:
        """Run pystray event loop (called in dedicated thread)."""
        icon_img = _create_icon("green")
        self._icon = pystray.Icon(
            name="VoiceIME",
            icon=icon_img,
            title="VoiceIME — Ready",
            menu=pystray.Menu(
                pystray.MenuItem("状态: 就绪", lambda: None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "暂停", self._on_toggle_pause, checked=lambda item: self._paused
                ),
                pystray.MenuItem("设置", self._on_settings),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._on_exit),
            ),
        )
        self._icon.run()

    def _on_toggle_pause(self, icon, item) -> None:
        self._paused = not self._paused
        action = "resume" if not self._paused else "pause"
        self._cmd_queue.put(TrayCommand(action=action))
        self.set_status(STATUS_PAUSED if self._paused else STATUS_READY)

    def _on_settings(self, icon, item) -> None:
        self._cmd_queue.put(TrayCommand(action="settings"))

    def _on_exit(self, icon, item) -> None:
        self._cmd_queue.put(TrayCommand(action="exit"))
        icon.stop()
