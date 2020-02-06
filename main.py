import os
import json


def main() -> None:
    print("Hello, world!")

    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event: dict = json.load(f)

    print(event)


if __name__ == "__main__":
    main()
