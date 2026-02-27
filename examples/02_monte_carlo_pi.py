from __future__ import annotations

import math
import random
import time


def render_accuracy_bar(abs_error: float, width: int = 24) -> str:
    # Treat 0.05 as the "fully off" bound for this tiny demo.
    closeness = max(0.0, 1.0 - min(abs_error / 0.05, 1.0))
    filled = round(closeness * width)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def main() -> None:
    samples = 200_000
    seed = 42
    rng = random.Random(seed)
    started = time.perf_counter()
    inside_circle = 0
    for _ in range(samples):
        x = rng.uniform(-1.0, 1.0)
        y = rng.uniform(-1.0, 1.0)
        if x * x + y * y <= 1.0:
            inside_circle += 1
    elapsed = time.perf_counter() - started

    pi_estimate = 4.0 * inside_circle / samples
    abs_error = abs(pi_estimate - math.pi)
    accuracy_bar = render_accuracy_bar(abs_error)
    print(f"samples={samples}")
    print(f"seed={seed}")
    print(f"inside_circle={inside_circle}")
    print(f"pi_estimate={pi_estimate:.6f}")
    print(f"abs_error={abs_error:.6f}")
    print(f"accuracy={accuracy_bar}")
    print(f"elapsed_seconds={elapsed:.4f}")


if __name__ == "__main__":
    main()
