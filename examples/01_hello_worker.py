from __future__ import annotations

import os
import socket


def main() -> None:
    print("hello from deborgen")
    print(f"hostname={socket.gethostname()}")
    print(f"cwd={os.getcwd()}")


if __name__ == "__main__":
    main()
