import os
import sys


def main() -> None:
    print("Hello, world!")
    print(f"{sys.argv=}")
    print(f"{os.environ=}")


if __name__ == "__main__":
    main()
