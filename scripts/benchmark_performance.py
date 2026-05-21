"""VoiceIME M3.3 — Performance acceptance benchmark.

Measures all Phase 3 performance targets:
  - Model cold-start time (target: <= 8s)
  - Second-wake latency (target: < 100ms)
  - 5s audio inference CPU (target: <= 2.5s)
  - Memory peak during inference (target: <= 4 GB)
  - Idle CPU usage (target: < 1%)

Usage:
  python scripts/benchmark_performance.py [--model-dir <path>] [--output <path>]
  python scripts/benchmark_performance.py --quick  # skip idle CPU measurement

Output: docs/qa/performance_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPORT_PATH = Path("docs/qa/performance_report.json")
_AUDIO_DURATION_S = 5
_SAMPLE_RATE = 16000
_COLD_START_LIMIT_S = 8.0
_WAKE_LIMIT_MS = 100
_INFERENCE_LIMIT_S = 2.5
_MEMORY_LIMIT_GB = 4.0
_IDLE_CPU_LIMIT_PCT = 1.0
_IDLE_WINDOW_S = 30


def generate_test_audio(duration_s: float = _AUDIO_DURATION_S) -> np.ndarray:
    """Generate synthetic 16kHz mono float32 audio with frequency sweep."""
    n_samples = int(_SAMPLE_RATE * duration_s)
    t = np.linspace(0, duration_s, n_samples, dtype=np.float32)
    freq = 100 + 700 * (t / duration_s)
    audio = np.sin(2 * np.pi * freq * t).astype(np.float32)
    audio += np.random.normal(0, 0.01, n_samples).astype(np.float32)
    return audio


def get_process_memory_mb() -> float:
    """Return current process RSS in MB."""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except ImportError:
        return -1.0


def get_process_cpu_pct() -> float:
    """Return current process CPU usage percent."""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        return proc.cpu_percent(interval=0.1)
    except ImportError:
        return -1.0


def measure_cold_start(model_dir: Path) -> dict[str, Any]:
    """Measure model load time from disk. Target: <= 8s."""
    print("\n=== Cold Start: Model Load Time ===\n")

    result: dict[str, Any] = {
        "metric": "model_cold_start",
        "target_s": _COLD_START_LIMIT_S,
        "measured_s": 0.0,
        "pass": False,
        "error": None,
    }

    try:
        from faster_whisper import WhisperModel

        print(f"Loading model from {model_dir} ...")
        mem_before = get_process_memory_mb()

        t0 = time.monotonic()
        model = WhisperModel(
            str(model_dir),
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
        )
        elapsed = time.monotonic() - t0

        mem_after = get_process_memory_mb()
        result["measured_s"] = round(elapsed, 2)
        result["pass"] = elapsed <= _COLD_START_LIMIT_S
        result["memory_before_mb"] = round(mem_before, 1) if mem_before > 0 else None
        result["memory_after_mb"] = round(mem_after, 1) if mem_after > 0 else None

        status = "PASS" if result["pass"] else "FAIL"
        print(f"  {status}: {elapsed:.2f}s (target <= {_COLD_START_LIMIT_S}s)")

        # Keep model ref alive for subsequent benchmarks
        result["_model"] = model
    except Exception as exc:
        result["error"] = str(exc)
        print(f"  ERROR: {exc}")

    return result


def measure_wake_latency(model: Any, audio: np.ndarray) -> dict[str, Any]:
    """Measure second-wake inference latency. Target: < 100ms."""
    print("\n=== Second Wake: Inference Latency (after warm) ===\n")

    result: dict[str, Any] = {
        "metric": "second_wake_latency",
        "target_ms": _WAKE_LIMIT_MS,
        "measured_ms": 0.0,
        "pass": False,
        "error": None,
    }

    if model is None:
        result["error"] = "Model not loaded"
        return result

    try:
        # Warm-up inference
        print("Warm-up inference (1s audio) ...")
        warm = audio[:_SAMPLE_RATE]
        model.transcribe(warm, vad_filter=True)

        # Timed short inference — simulates "second wake" scenario
        print("Timed short inference (1s audio) ...")
        short = audio[:_SAMPLE_RATE]
        t0 = time.monotonic()
        segments, _info = model.transcribe(short, vad_filter=True)
        _text = "".join(seg.text for seg in segments)
        elapsed_ms = (time.monotonic() - t0) * 1000

        result["measured_ms"] = round(elapsed_ms, 1)
        result["pass"] = elapsed_ms <= _WAKE_LIMIT_MS

        status = "PASS" if result["pass"] else "FAIL"
        print(f"  {status}: {elapsed_ms:.1f}ms (target < {_WAKE_LIMIT_MS}ms)")
    except Exception as exc:
        result["error"] = str(exc)
        print(f"  ERROR: {exc}")

    return result


def measure_inference(model: Any, audio: np.ndarray) -> dict[str, Any]:
    """Measure 5s audio inference time. Target: <= 2.5s."""
    print(f"\n=== Inference: {_AUDIO_DURATION_S}s Audio ===\n")

    result: dict[str, Any] = {
        "metric": "inference_5s_audio",
        "audio_duration_s": _AUDIO_DURATION_S,
        "target_s": _INFERENCE_LIMIT_S,
        "measured_s": 0.0,
        "real_time_factor": 0.0,
        "pass": False,
        "error": None,
    }

    if model is None:
        result["error"] = "Model not loaded"
        return result

    try:
        print(f"Timed inference ({_AUDIO_DURATION_S}s audio) ...")
        t0 = time.monotonic()
        segments, _info = model.transcribe(audio, vad_filter=True)
        text = "".join(seg.text for seg in segments)
        elapsed = time.monotonic() - t0

        rtf = elapsed / _AUDIO_DURATION_S
        result["measured_s"] = round(elapsed, 2)
        result["real_time_factor"] = round(rtf, 2)
        result["pass"] = elapsed <= _INFERENCE_LIMIT_S
        result["text_length"] = len(text.strip())

        status = "PASS" if result["pass"] else "FAIL"
        print(f"  {status}: {elapsed:.2f}s, RTF={rtf:.2f}x, text={len(text.strip())} chars")
        print(f"  (target <= {_INFERENCE_LIMIT_S}s)")
    except Exception as exc:
        result["error"] = str(exc)
        print(f"  ERROR: {exc}")

    return result


def measure_memory_peak(model: Any, audio: np.ndarray) -> dict[str, Any]:
    """Measure peak memory during inference. Target: <= 4 GB."""
    print("\n=== Memory Peak During Inference ===\n")

    result: dict[str, Any] = {
        "metric": "memory_peak",
        "target_gb": _MEMORY_LIMIT_GB,
        "measured_gb": 0.0,
        "measured_mb": 0.0,
        "pass": False,
        "error": None,
    }

    mem = get_process_memory_mb()
    if mem < 0:
        result["error"] = "psutil not available"
        print("  SKIPPED: psutil not installed")
        return result

    mem_before = mem
    print(f"  Memory before inference: {mem_before:.1f} MB")

    if model is not None:
        try:
            segments, _info = model.transcribe(audio, vad_filter=True)
            _text = "".join(seg.text for seg in segments)
        except Exception as exc:
            result["error"] = f"Inference failed: {exc}"
            print(f"  ERROR: {exc}")
            return result

    mem_after = get_process_memory_mb()
    peak_mb = max(mem_before, mem_after)
    peak_gb = peak_mb / 1024

    result["measured_mb"] = round(peak_mb, 1)
    result["measured_gb"] = round(peak_gb, 2)
    result["memory_before_mb"] = round(mem_before, 1)
    result["memory_after_mb"] = round(mem_after, 1)
    result["pass"] = peak_gb <= _MEMORY_LIMIT_GB

    status = "PASS" if result["pass"] else "FAIL"
    print(f"  {status}: {peak_mb:.1f} MB / {peak_gb:.2f} GB (target <= {_MEMORY_LIMIT_GB} GB)")
    return result


def measure_idle_cpu() -> dict[str, Any]:
    """Measure idle CPU usage over a sampling window. Target: < 1%."""
    print(f"\n=== Idle CPU (sampling {_IDLE_WINDOW_S}s) ===\n")

    result: dict[str, Any] = {
        "metric": "idle_cpu",
        "target_pct": _IDLE_CPU_LIMIT_PCT,
        "measured_pct": 0.0,
        "sample_window_s": _IDLE_WINDOW_S,
        "pass": False,
        "error": None,
    }

    cpu = get_process_cpu_pct()
    if cpu < 0:
        result["error"] = "psutil not available"
        print("  SKIPPED: psutil not installed")
        return result

    # First call to cpu_percent is always 0.0, need a second call
    import psutil
    proc = psutil.Process(os.getpid())
    proc.cpu_percent(interval=None)

    samples: list[float] = []
    print(f"  Sampling CPU every 1s for {_IDLE_WINDOW_S}s ...")
    for i in range(_IDLE_WINDOW_S):
        time.sleep(1)
        pct = proc.cpu_percent(interval=None)
        samples.append(pct)
        if (i + 1) % 10 == 0:
            print(f"    {i + 1}s: avg={sum(samples) / len(samples):.1f}%")

    avg_cpu = sum(samples) / len(samples) if samples else 0.0
    result["measured_pct"] = round(avg_cpu, 2)
    result["sample_count"] = len(samples)
    result["min_pct"] = round(min(samples), 2) if samples else 0
    result["max_pct"] = round(max(samples), 2) if samples else 0
    result["pass"] = avg_cpu < _IDLE_CPU_LIMIT_PCT

    status = "PASS" if result["pass"] else "FAIL"
    print(f"  {status}: avg={avg_cpu:.2f}% (target < {_IDLE_CPU_LIMIT_PCT}%)")
    return result


def build_report(metrics: list[dict]) -> dict:
    """Assemble final performance report with summary."""
    total = len(metrics)
    passed = sum(1 for m in metrics if m.get("pass"))
    failed = total - passed
    errors = sum(1 for m in metrics if m.get("error"))

    return {
        "report_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "milestone": "M3.3",
            "python_version": sys.version,
            "platform": sys.platform,
            "machine": os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        },
        "metrics": metrics,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "overall": "PASS" if failed == 0 and errors == 0 else "FAIL",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VoiceIME M3.3 — Performance acceptance benchmark"
    )
    parser.add_argument(
        "--model-dir", type=str, default=None,
        help="Path to faster-whisper model directory",
    )
    parser.add_argument(
        "--output", type=str, default=str(REPORT_PATH),
        help=f"Output JSON path (default: {REPORT_PATH})",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Skip idle CPU measurement (saves time)",
    )
    parser.add_argument(
        "--cpu-only", action="store_true",
        help="Skip memory peak measurement",
    )
    args = parser.parse_args()

    model_dir = args.model_dir
    if model_dir is None:
        # Default: check common locations
        from voiceime.utils.paths import model_dir as get_model_dir
        try:
            model_dir = str(get_model_dir())
        except Exception:
            model_dir = "models/large-v3-turbo"

    print("VoiceIME M3.3 Performance Benchmark")
    print(f"  Model dir: {model_dir}")
    print(f"  Report:    {args.output}")

    audio = generate_test_audio(_AUDIO_DURATION_S)

    # 1. Cold start
    cold_result = measure_cold_start(Path(model_dir))
    model = cold_result.pop("_model", None)

    # 2. Wake latency
    wake_result = measure_wake_latency(model, audio)

    # 3. Full inference
    inference_result = measure_inference(model, audio)

    # 4. Memory peak
    memory_result: dict[str, Any]
    if args.cpu_only:
        memory_result = {
            "metric": "memory_peak", "target_gb": _MEMORY_LIMIT_GB,
            "error": "Skipped via --cpu-only",
        }
    else:
        memory_result = measure_memory_peak(model, audio)

    # 5. Idle CPU
    cpu_result: dict[str, Any]
    if args.quick:
        cpu_result = {
            "metric": "idle_cpu", "target_pct": _IDLE_CPU_LIMIT_PCT,
            "error": "Skipped via --quick",
        }
    else:
        cpu_result = measure_idle_cpu()

    metrics = [cold_result, wake_result, inference_result, memory_result, cpu_result]

    # Clean up model reference
    del model

    # Summary
    print("\n" + "=" * 50)
    print("=== Summary ===")
    print("=" * 50)
    all_pass = True
    for m in metrics:
        name = m["metric"]
        if m.get("error") and "Skipped" in str(m.get("error", "")):
            status = "SKIP"
        elif m.get("error"):
            status = "ERROR"
            all_pass = False
        elif m.get("pass"):
            status = "PASS"
        else:
            status = "FAIL"
            all_pass = False
        measured = m.get("measured_s") or m.get("measured_ms") or m.get("measured_gb") or m.get("measured_pct") or "N/A"
        target = (
            m.get("target_s") or m.get("target_ms") or m.get("target_gb")
            or m.get("target_pct") or "N/A"
        )
        print(f"  [{status}] {name}: {measured} (target: {target})")

    print(f"\nOverall: {'PASS' if all_pass else 'FAIL'}")

    # Write report
    report = build_report(metrics)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    main()
