"""VoiceIME entry point."""

from __future__ import annotations

import atexit
import logging
import sys

from voiceime import __version__
from voiceime.utils.paths import ensure_dirs
from voiceime.utils.log import setup_logging
from voiceime.utils.single_instance import (
    release_single_instance_lock,
    request_single_instance_lock,
)

logger = logging.getLogger("voiceime")


def main() -> None:
    # Version check
    if "--version" in sys.argv:
        print(f"VoiceIME v{__version__}")
        return

    # Ensure data directories exist
    ensure_dirs()

    # Setup logging
    setup_logging("INFO")
    logger.info("VoiceIME v%s starting...", __version__)

    # Single instance check
    if not request_single_instance_lock():
        logger.error("Another instance is already running. Exiting.")
        print("VoiceIME is already running.")
        sys.exit(1)

    atexit.register(release_single_instance_lock)

    # Import heavy deps only after basic checks
    from PyQt6.QtWidgets import QApplication

    from voiceime.config.manager import ConfigManager
    from voiceime.model.manager import ModelManager

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Tray-only app, no main window

    config = ConfigManager()
    models_dir = config.data_dir / "models"
    model_mgr = ModelManager(models_dir)

    # First-run wizard
    if not config.get("first_run_complete", False):
        from voiceime.ui.wizard import FirstRunWizard

        wizard = FirstRunWizard(config, model_mgr)
        if wizard.exec() != FirstRunWizard.DialogCode.Accepted:
            logger.info("First-run wizard cancelled, exiting")
            sys.exit(0)
        wizard.mark_complete(config)

    from voiceime.core import CoreController

    core = CoreController(config, model_mgr)

    if not core.initialize():
        logger.error("Initialization failed, exiting")
        sys.exit(1)

    core.start()

    # Cleanup on exit
    atexit.register(core.stop)

    logger.info("VoiceIME running")
    exit_code = app.exec()
    logger.info("VoiceIME exiting with code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
