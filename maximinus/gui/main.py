"""Entry point for the Maximinus GUI (`maximinus-gui`, or `maximinus gui`)."""

import sys


def main():
    from .window import run  # deferred: don't require gi to import the CLI

    return run()


if __name__ == "__main__":
    sys.exit(main())
