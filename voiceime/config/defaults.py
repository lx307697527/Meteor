"""Default configuration values for VoiceIME."""

DEFAULT_CONFIG: dict = {
    "hotkey": "caps_lock",
    "asr": {
        "model": "large-v3-turbo",
        "quantization": "int8",
        "device": "cpu",
        "language": "auto",
        "beam_size": 5,
        "vad_filter": True,
        "vad_threshold": 0.5,
    },
    "postprocess": {
        "punct_normalize": True,
        "t2s_enabled": False,
        "hotword_enabled": True,
    },
    "llm": {
        "provider": "",
        "api_key_stored_in_keyring": False,
        "model_id": "",
        "polish_mode": "manual",
        "system_prompt": "",
        "timeout_seconds": 10,
    },
    "ui": {
        "quick_mode": True,
        "memory_lock": False,
        "memory_lock_limit_gb": 3.5,
        "auto_restore_clipboard": True,
        "clipboard_restore_delay_ms": 50,
        "min_record_ms": 200,
        "max_record_s": 60,
    },
    "advanced": {
        "log_level": "INFO",
        "log_path": "",
    },
}
