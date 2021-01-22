#!/usr/bin/env python

import sys
import random

import requests


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <IMAGE_NAME>", file=sys.stderr)
        exit(1)

    image_name = sys.argv[1]
    session_id = "".join(random.choice("012345679abcdef") for _ in range(8))

    url = "http://localhost:4242"

    response = requests.post(
        f"{url}/api/new_target",
        json=dict(id=session_id, image_name=image_name),
    )

    assert response.json()["status"] == "ok"

    print(f"Explore target at: {url}/{session_id}")


if __name__ == "__main__":
    main()
