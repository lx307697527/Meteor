"""VoiceIME M3.1 — whisper.cpp Vulkan benchmark vs CPU faster-whisper baseline.

Usage:
  python scripts/benchmark_vulkan.py [--audio-duration 5] [--whisper-cpp-path ./whisper.cpp]
  python scripts/benchmark_vulkan.py --cpu-only  # skip Vulkan, just measure CPU baseline

Output: docs/qa/vulkan_benchmark_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPORT_PATH = Path("docs/qa/vulkan_benchmark_report.json")
_THRESHOLD_S = 1.5  # Vulkan must be <= 1.5s for 5s audio to justify migration
_TARGET_DURATION_S = 5  # Default test audio duration


def generate_test_audio(duration_s: float = _TARGET_DURATION_S) -> np.ndarray:
    """Generate synthetic 16kHz mono float32 audio (sine wave sweep)."""
    sample_rate = 16000
    n_samples = int(sample_rate * duration_s)
    t = np.linspace(0, duration_s, n_samples, dtype=np.float32)
    # Frequency sweep 100Hz -> 800Hz for realistic VAD behavior
    freq = 100 + 700 * (t / duration_s)
    audio = np.sin(2 * np.pi * freq * t).astype(np.float32)
    # Add slight noise
    audio += np.random.normal(0, 0.01, n_samples).astype(np.float32)
    return audio


def save_wav(audio: np.ndarray, path: Path, sample_rate: int = 16000) -> None:
    """Write numpy audio to 16-bit PCM WAV file."""
    import wave

    pcm = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def bench_cpu_faster_whisper(audio: np.ndarray) -> dict[str, Any]:
    """Benchmark faster-whisper CPU inference. Returns timing dict."""
    print("\n=== CPU Benchmark: faster-whisper ===\n")

    from faster_whisper import WhisperModel

    result: dict[str, Any] = {
        "backend": "faster-whisper (CTranslate2 CPU int8)",
        "audio_duration_s": len(audio) / 16000,
        "load_time_s": 0.0,
        "inference_time_s": 0.0,
        "total_time_s": 0.0,
        "error": None,
    }

    try:
        # Model load timing
        print("Loading model large-v3-turbo int8 CPU ...")
        t0 = time.monotonic()
        model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
        load_time = time.monotonic() - t0
        result["load_time_s"] = round(load_time, 2)
        print(f"  Loaded in {load_time:.1f}s")

        # Warm-up inference
        print("Warm-up inference (1s) ...")
        warm = audio[:16000]
        model.transcribe(warm, vad_filter=True)

        # Timed inference
        print(f"Timed inference ({result['audio_duration_s']:.0f}s audio) ...")
        t0 = time.monotonic()
        segments, info = model.transcribe(audio, vad_filter=True)
        # Consume segments
        text = "".join(seg.text for seg in segments)
        inference_time = time.monotonic() - t0
        result["inference_time_s"] = round(inference_time, 2)
        result["total_time_s"] = round(load_time + inference_time, 2)
        result["text_length"] = len(text.strip())
        print(f"  Inference: {inference_time:.2f}s, text: {len(text.strip())} chars")
        print(f"  Real-time factor: {inference_time / result['audio_duration_s']:.2f}x")

    except Exception as exc:
        result["error"] = str(exc)
        print(f"  ERROR: {exc}")

    return result


def bench_whisper_cpp_vulkan(
    audio_wav_path: Path, whisper_cpp_dir: Path, audio_duration_s: float
) -> dict[str, Any]:
    """Benchmark whisper.cpp Vulkan backend. Returns timing dict."""
    print("\n=== Vulkan Benchmark: whisper.cpp ===\n")

    result: dict[str, Any] = {
        "backend": "whisper.cpp Vulkan",
        "audio_duration_s": audio_duration_s,
        "inference_time_s": 0.0,
        "error": None,
        "binary_path": None,
        "model_path": None,
    }

    # Locate the whisper.cpp main binary
    exe_name = "whisper-cli.exe" if os.name == "nt" else "whisper-cli"
    candidates = [
        whisper_cpp_dir / "build" / "bin" / exe_name,
        whisper_cpp_dir / "build-vulkan" / "bin" / exe_name,
        whisper_cpp_dir / exe_name,
    ]
    binary = None
    for c in candidates:
        if c.exists():
            binary = c
            break

    if binary is None:
        result["error"] = (
            f"whisper-cli binary not found in {whisper_cpp_dir}. "
            "Build with: cmake -B build -DWHISPER_VULKAN=ON && cmake --build build"
        )
        print(f"  SKIPPED: {result['error']}")
        return result

    result["binary_path"] = str(binary)
    print(f"  Binary: {binary}")

    # Look for GGML model
    model_name = "ggml-large-v3-turbo.bin"
    model_path = whisper_cpp_dir / "models" / model_name
    if not model_path.exists():
        # Try smaller model
        model_name = "ggml-large-v3.bin"
        model_path = whisper_cpp_dir / "models" / model_name
    if not model_path.exists():
        model_name = "ggml-medium.bin"
        model_path = whisper_cpp_dir / "models" / model_name

    if not model_path.exists():
        result["error"] = (
            f"No GGML model found in {whisper_cpp_dir}/models/. "
            "Download: ./models/download-ggml-model.sh large-v3-turbo"
        )
        print(f"  SKIPPED: {result['error']}")
        return result

    result["model_path"] = str(model_path)
    print(f"  Model: {model_name}")

    # Run benchmark
    try:
        print(f"Timed Vulkan inference ({audio_duration_s:.0f}s audio) ...")
        t0 = time.monotonic()
        proc = subprocess.run(
            [
                str(binary),
                "-m", str(model_path),
                "-f", str(audio_wav_path),
                "-l", "auto",
                "--no-prints",
                "-t", "4",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = time.monotonic() - t0
        result["inference_time_s"] = round(elapsed, 2)

        if proc.returncode != 0:
            result["error"] = proc.stderr.strip() or f"exit code {proc.returncode}"
            print(f"  ERROR: {result['error']}")
            return result

        output_text = proc.stdout.strip()
        result["text_length"] = len(output_text)
        print(f"  Inference: {elapsed:.2f}s, text: {len(output_text)} chars")
        print(f"  Real-time factor: {elapsed / audio_duration_s:.2f}x")

    except subprocess.TimeoutExpired:
        result["error"] = "Timed out (120s)"
        print("  TIMEOUT")
    except Exception as exc:
        result["error"] = str(exc)
        print(f"  ERROR: {exc}")

    return result


def evaluate(cpu_result: dict, vulkan_result: dict) -> dict[str, Any]:
    """Produce recommendation based on benchmark results."""
    cpu_time = cpu_result.get("inference_time_s", 0) or 999
    vulkan_time = vulkan_result.get("inference_time_s", 0) or 999
    vulkan_error = vulkan_result.get("error")

    if vulkan_error:
        recommendation = "stay_cpu"
        reason = f"Vulkan benchmark failed: {vulkan_error}"
    elif vulkan_time <= _THRESHOLD_S:
        recommendation = "integrate_vulkan"
        speedup = cpu_time / vulkan_time if vulkan_time > 0 else 999
        reason = (
            f"Vulkan {vulkan_time:.2f}s <= {_THRESHOLD_S}s threshold -- "
            f"{speedup:.1f}x faster than CPU ({cpu_time:.2f}s). "
            "Recommended: integrate whisper.cpp Vulkan as primary backend."
        )
    else:
        recommendation = "stay_cpu"
        speedup = cpu_time / vulkan_time if vulkan_time > 0 else 0
        reason = (
            f"Vulkan {vulkan_time:.2f}s > {_THRESHOLD_S}s threshold. "
            f"Speedup vs CPU: {speedup:.1f}x. "
            "Stay on faster-whisper CPU for now."
        )

    return {"recommendation": recommendation, "reason": reason}


def build_report(
    cpu_result: dict,
    vulkan_result: dict | None,
    evaluation: dict,
    audio_duration_s: float,
) -> dict:
    """Assemble final benchmark report."""
    return {
        "report_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "milestone": "M3.1",
            "threshold_s": _THRESHOLD_S,
            "audio_duration_s": audio_duration_s,
            "python_version": sys.version,
            "platform": sys.platform,
        },
        "cpu_faster_whisper": cpu_result,
        "vulkan_whisper_cpp": vulkan_result,
        "evaluation": evaluation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VoiceIME M3.1 -- whisper.cpp Vulkan benchmark vs CPU baseline"
    )
    parser.add_argument(
        "--audio-duration", type=float, default=_TARGET_DURATION_S,
        help=f"Test audio duration in seconds (default: {_TARGET_DURATION_S})",
    )
    parser.add_argument(
        "--whisper-cpp-path", type=str, default=".",
        help="Path to whisper.cpp repository (default: current dir)",
    )
    parser.add_argument(
        "--cpu-only", action="store_true",
        help="Skip Vulkan benchmark, only measure CPU baseline",
    )
    parser.add_argument(
        "--output", type=str, default=str(REPORT_PATH),
        help=f"Output JSON path (default: {REPORT_PATH})",
    )
    parser.add_argument(
        "--no-cpu", action="store_true",
        help="Skip CPU benchmark (assumes baseline already measured)",
    )
    args = parser.parse_args()

    audio_dur = args.audio_duration
    print(f"VoiceIME M3.1 Benchmark -- {audio_dur}s audio, threshold={_THRESHOLD_S}s")
    print(f"Report: {args.output}")

    # Generate test audio
    print(f"\nGenerating {audio_dur}s test audio (16kHz mono sweep + noise) ...")
    audio = generate_test_audio(audio_dur)

    # CPU baseline
    cpu_result = bench_cpu_faster_whisper(audio) if not args.no_cpu else {}

    # Vulkan benchmark
    vulkan_result = None
    if not args.cpu_only:
        wav_path = Path("test_audio.wav")
        save_wav(audio, wav_path)
        print(f"  WAV saved to {wav_path} ({wav_path.stat().st_size} bytes)")

        cpp_path = Path(args.whisper_cpp_path)
        vulkan_result = bench_whisper_cpp_vulkan(wav_path, cpp_path, audio_dur)

        # Cleanup
        if wav_path.exists():
            wav_path.unlink()

    # Evaluate
    evaluation = evaluate(cpu_result, vulkan_result or {})
    print(f"\n=== Recommendation ===\n  {evaluation['recommendation'].upper()}")
    print(f"  {evaluation['reason']}")

    # Write report
    report = build_report(cpu_result, vulkan_result, evaluation, audio_dur)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport written to {output_path}")


if __name__ == "__main__":
    main()
