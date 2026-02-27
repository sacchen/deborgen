from __future__ import annotations

import math
import time


def is_prime(value: int) -> bool:
    if value < 2:
        return False
    if value == 2:
        return True
    if value % 2 == 0:
        return False

    limit = int(math.isqrt(value))
    for divisor in range(3, limit + 1, 2):
        if value % divisor == 0:
            return False
    return True


def main() -> None:
    upper_bound = 20_000
    started = time.perf_counter()
    primes = [value for value in range(upper_bound + 1) if is_prime(value)]
    elapsed = time.perf_counter() - started

    print(f"counted {len(primes)} primes up to {upper_bound}")
    print(f"largest_prime={primes[-1]}")
    print(f"elapsed_seconds={elapsed:.4f}")


if __name__ == "__main__":
    main()
