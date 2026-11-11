"""Pinned, isolated local Supabase stacks with deterministic port offsets."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

CLI_VERSION = "2.122.1"
ROOT = Path(__file__).resolve().parents[2]


def ensure_signing_key(path: Path) -> None:
    if path.exists():
        return
    from cryptography.hazmat.primitives.asymmetric import ec
    from jwt.algorithms import ECAlgorithm

    path.parent.mkdir(parents=True, exist_ok=True)
    key = json.loads(ECAlgorithm.to_jwk(ec.generate_private_key(ec.SECP256R1())))
    key.update(kid=str(uuid4()), use="sig", alg="ES256", key_ops=["sign", "verify"], ext=True)
    path.write_text(json.dumps([key]), encoding="utf-8")


def _linked(path: Path) -> bool:
    """True for symlinks and Windows junctions. exists() follows both."""
    if path.is_symlink():
        return True
    if not path.exists():
        return False
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & 0x400)


def _sync_directory(source: Path, destination: Path) -> None:
    """Replace an isolated copy so files deleted from source do not linger."""
    if _linked(destination) or (destination.exists() and not destination.is_dir()):
        raise ValueError("Refusing to replace a linked or non-directory stack path")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def prepare(name: str, offset: int, *, lite: bool = False) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", name):
        raise ValueError("Stack name must be a short lowercase identifier")
    if not 0 <= offset <= 9000:
        raise ValueError("Port offset must be between 0 and 9000")
    if lite and name == "foundation" and offset == 0:
        raise ValueError(
            "Use a named isolated stack with --lite; tracked config must stay unchanged"
        )
    workdir = ROOT if name == "foundation" and offset == 0 else ROOT / ".local/stacks" / name
    config = (ROOT / "supabase/config.toml").read_text(encoding="utf-8")
    if workdir != ROOT:
        stack_parent = (ROOT / ".local/stacks").resolve()
        if not stack_parent.is_relative_to(ROOT.resolve()):
            raise ValueError("Stack path escapes the isolated stack directory")
        if _linked(workdir):
            raise ValueError(
                "Refusing a symlinked stack path; it escapes the isolated stack directory"
            )
        if workdir.exists() and workdir.resolve().parent != stack_parent:
            raise ValueError("Stack path escapes the isolated stack directory")
        workdir.mkdir(parents=True, exist_ok=True)
        if workdir.resolve().parent != stack_parent:
            raise ValueError("Stack path escapes the isolated stack directory")
        # bootstrap/reset call prepare without repeating --lite. A named stack
        # that was prepared lite must stay lite; rewriting the template would
        # turn Studio back on.
        marker = workdir / ".stack-lite"
        if lite:
            marker.write_text("lite\n", encoding="utf-8")
        elif marker.is_file():
            lite = True
        (workdir / "supabase").mkdir(parents=True, exist_ok=True)
        config = re.sub(r'project_id = "[^"]+"', f'project_id = "safevoice-{name}"', config)
        config = re.sub(
            r"(?m)^(\w*port\s*=\s*)(\d+)$", lambda m: m[1] + str(int(m[2]) + offset), config
        )
        config = config.replace("../.local/signing_keys.json", "../signing_keys.json")
        frontend = f"http://127.0.0.1:{5178 + offset}"
        config = re.sub(r"(?m)^site_url\s*=.*$", f'site_url = "{frontend}"', config)
        config = re.sub(
            r"(?m)^additional_redirect_urls\s*=.*$",
            f'additional_redirect_urls = ["{frontend}"]',
            config,
        )
        if lite:
            config = re.sub(r"(\[studio\]\s*\n)enabled\s*=\s*true", r"\1enabled = false", config)
        (workdir / "supabase/config.toml").write_text(config, encoding="utf-8")
        shutil.copy2(ROOT / "supabase/seed.sql", workdir / "supabase/seed.sql")
        for directory in ("migrations", "tests"):
            _sync_directory(ROOT / "supabase" / directory, workdir / "supabase" / directory)
    ensure_signing_key(
        workdir / (".local/signing_keys.json" if workdir == ROOT else "signing_keys.json")
    )
    return workdir


def cli(workdir: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    # Capture all CLI output: start/status include secret local keys by default.
    return subprocess.run(
        [
            "npx.cmd" if os.name == "nt" else "npx",
            "--yes",
            f"supabase@{CLI_VERSION}",
            "--workdir",
            str(workdir),
            *arguments,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "start", "reset", "test", "stop", "status"))
    parser.add_argument("--name", default=os.environ.get("SAFEVOICE_STACK_NAME", "foundation"))
    parser.add_argument(
        "--offset", type=int, default=int(os.environ.get("SAFEVOICE_PORT_OFFSET", "0"))
    )
    parser.add_argument("--lite", action="store_true")
    args = parser.parse_args()
    workdir = prepare(args.name, args.offset, lite=args.lite)
    commands = {
        "start": ["start"],
        "reset": ["db", "reset", "--local", "--yes"],
        "test": ["test", "db", "--local"],
        "stop": ["stop"],
        "status": ["status", "-o", "json"],
    }
    if args.command != "prepare":
        result = cli(workdir, *commands[args.command])
        if result.returncode:
            parser.exit(
                1,
                f"Local Supabase {args.command} failed (exit {result.returncode}); captured output withheld because CLI output can contain keys.\n",
            )
        if args.command == "test":
            print(result.stdout)
    print(
        f"Local stack {args.name}: {args.command} complete; API port {54321 + args.offset}, DB port {54322 + args.offset}."
    )


if __name__ == "__main__":
    main()
