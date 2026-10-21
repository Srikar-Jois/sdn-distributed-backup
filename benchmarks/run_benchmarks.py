#!/usr/bin/env python3
import csv
import os
import subprocess
import sys
import time
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "benchmarks"
DATA = OUT / "generated_files"

CSV_PATH = OUT / "benchmark_results_repeated.csv"
SIZES_MIB = [1, 5, 10, 25]
TRIALS = 3
NODES = ["10.0.0.2:9001", "10.0.0.3:9002"]


def create_file(path, size_mib):
    # Write nontrivial, deterministic test data.
    block = bytes(range(256)) * 4096
    remaining = size_mib * 1024 * 1024

    with path.open("wb") as f:
        while remaining:
            part = block[:min(remaining, len(block))]
            f.write(part)
            remaining -= len(part)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    rows = []

    for size in SIZES_MIB:
        source = DATA / f"test_{size}MiB.bin"
        create_file(source, size)

        for trial in range(1, TRIALS + 1):
            command = [
                sys.executable,
                str(ROOT / "distributed_client.py"),
                str(source),
                *NODES,
            ]

            env = os.environ.copy()
            # Prevent long retry delays from distorting benchmark runs.
            env["BACKUP_RETRY_ATTEMPTS"] = "1"
            env["BACKUP_RETRY_DELAY"] = "0"

            print(
                f"\nTesting {size} MiB, trial {trial}/{TRIALS}",
                flush=True,
            )

            start = time.perf_counter()
            try:
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                elapsed = time.perf_counter() - start
                output = (result.stdout + "\n" + result.stderr).strip()
                success = result.returncode == 0
                notes = output[-1000:]
            except subprocess.TimeoutExpired as exc:
                elapsed = time.perf_counter() - start
                success = False
                notes = f"Timed out after 300 seconds: {exc}"

            print(notes)
            if not success:
                print("FAILED: check server/client output before retrying.")
            else:
                print(
                    f"Both-server replication time: {elapsed:.4f} s\n"
                    f"Logical throughput: {size / elapsed:.2f} MiB/s\n"
                    f"Aggregate replicated throughput: "
                    f"{2 * size / elapsed:.2f} MiB/s"
                )

            rows.append({
                "condition": "normal",
                "size_mib": size,
                "trial": trial,
                "elapsed_seconds": round(elapsed, 6),
                "logical_throughput_mib_s": (
                    round(size / elapsed, 3) if success and elapsed else ""
                ),
                "aggregate_replicated_throughput_mib_s": (
                    round(2 * size / elapsed, 3)
                    if success and elapsed else ""
                ),
                "success": success,
                "notes": notes,
            })

    fields = [
        "condition", "size_mib", "trial", "elapsed_seconds",
        "logical_throughput_mib_s",
        "aggregate_replicated_throughput_mib_s", "success", "notes",
    ]

    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved results to {CSV_PATH}")
    make_graphs(rows)


def make_graphs(rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Graphs require matplotlib. Install it in the Python environment.")
        return

    good = [
        r for r in rows
        if r["success"] and r["logical_throughput_mib_s"] != ""
    ]
    if not good:
        print("No successful runs; cannot generate graphs.")
        return

    grouped = {}
    for r in good:
        grouped.setdefault(r["size_mib"], []).append(r)

    sizes = sorted(grouped)
    avg_time = [
        mean(float(r["elapsed_seconds"]) for r in grouped[s])
        for s in sizes
    ]
    avg_throughput = [
        mean(float(r["logical_throughput_mib_s"]) for r in grouped[s])
        for s in sizes
    ]

    for values, ylabel, title, filename in [
        (avg_time, "Time to replicate to both servers (s)",
         "Distributed backup time vs file size",
         "distributed_elapsed_vs_size.png"),
        (avg_throughput, "Logical throughput (MiB/s)",
         "Distributed backup throughput vs file size",
         "distributed_throughput_vs_size.png"),
    ]:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(sizes, values, marker="o")
        ax.set_xlabel("File size (MiB)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = OUT / filename
        fig.savefig(path, dpi=160)
        plt.close(fig)
        print(f"Saved graph: {path}")

    print("\nMean successful results:")
    for size in sizes:
        group = grouped[size]
        print(
            f"{size} MiB: "
            f"{mean(float(r['elapsed_seconds']) for r in group):.4f} s, "
            f"{mean(float(r['logical_throughput_mib_s']) for r in group):.2f} "
            f"MiB/s, {len(group)} successful trial(s)"
        )


if __name__ == "__main__":
    main()
