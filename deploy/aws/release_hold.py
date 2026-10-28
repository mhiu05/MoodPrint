"""Fail-closed, repository-controlled publication hold for both release events."""

import argparse
import os
import sys
from pathlib import Path


def release_held(root: Path) -> bool:
    try:
        (root / 'deploy/guest-experience.release-hold').lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(argv)
    held = release_held(args.root)
    try:
        output = os.environ['GITHUB_OUTPUT']
        if not output:
            raise ValueError('missing runner output')
        with open(output, 'a', encoding='utf-8') as stream:
            stream.write(f'held={str(held).lower()}\n')
    except (KeyError, OSError, ValueError):
        print('Cannot emit release-hold decision; publication remains disabled.', file=sys.stderr)
        return 1
    print(f'Release hold: {str(held).lower()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
