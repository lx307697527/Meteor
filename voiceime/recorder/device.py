"""Microphone device enumeration."""

from __future__ import annotations

import logging

import sounddevice as sd

from voiceime.protocols import DeviceInfo

logger = logging.getLogger("voiceime.recorder.device")


def list_devices() -> list[DeviceInfo]:
    """Return available input (microphone) devices."""
    devices = sd.query_devices()
    default_input = sd.default.device[0] if sd.default.device else -1
    result: list[DeviceInfo] = []

    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            result.append(
                DeviceInfo(
                    id=i,
                    name=dev["name"],
                    is_default=(i == default_input),
                )
            )

    if not result:
        logger.warning("No microphone devices found")
    return result


def get_default_device_id() -> int | None:
    """Return the default input device ID, or None if unavailable."""
    dev_id = sd.default.device[0] if sd.default.device else None
    if dev_id is not None and dev_id >= 0:
        return dev_id
    devices = list_devices()
    return devices[0].id if devices else None
