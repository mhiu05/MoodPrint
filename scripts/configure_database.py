"""Enter a database password locally; never accept it as a command-line argument."""

import argparse
import getpass
import json
import re
import sys
import warnings
from io import StringIO
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationError(ValueError):
    """A fixed diagnostic code, never an exception containing credential input."""


def configure(path: Path, host: str, username: str, password: str, migration_mode: str):
    content = path.read_text(encoding="utf-8")
    values = dotenv_values(stream=StringIO(content))
    project_url = values.get("SUPABASE_URL", "") or ""
    match = re.fullmatch(r"https://([a-z0-9]+)\.supabase\.co/?", project_url)
    if not match or not username.endswith("." + match[1]):
        raise ConfigurationError("PROJECT_USERNAME_MISMATCH")
    if not re.fullmatch(r"[a-z0-9.-]+\.pooler\.supabase\.com", host):
        raise ConfigurationError("INVALID_POOLER_HOST")
    if not password:
        raise ConfigurationError("EMPTY_PASSWORD")
    if any(c in password for c in ("\n", "\r", "\x00")):
        raise ConfigurationError("INVALID_PASSWORD_CHARACTERS")
    if migration_mode not in ("session", "direct"):
        raise ConfigurationError("INVALID_MIGRATION_MODE")
    session = URL.create(
        "postgresql",
        username=username,
        password=password,
        host=host,
        port=5432,
        database="postgres",
        query={"sslmode": "require"},
    )
    migration = (
        session
        if migration_mode == "session"
        else URL.create(
            "postgresql",
            username="postgres",
            password=password,
            host=f"db.{match[1]}.supabase.co",
            port=5432,
            database="postgres",
            query={"sslmode": "require"},
        )
    )
    updates = {
        "DATABASE_URL": session.render_as_string(hide_password=False),
        "DATABASE_MIGRATION_URL": migration.render_as_string(hide_password=False),
        "DATABASE_POOL_MODE": "session",
    }
    for name, value in updates.items():
        # Single-quote dotenv values so percent-encoded credentials round-trip safely.
        replacement = name + "='" + value.replace("'", "\\'") + "'"
        if re.search(r"^" + name + r"=", content, re.M):
            content = re.sub(
                r"^" + name + r"=.*$", lambda _, value=replacement: value, content, flags=re.M
            )
        else:
            content += "\n" + replacement + "\n"
    # Validate encoding through the actual dotenv + URL parsers before touching the file.
    rendered = dotenv_values(stream=StringIO(content))
    if any(
        make_url(rendered[name]).password != password
        for name in ("DATABASE_URL", "DATABASE_MIGRATION_URL")
    ):
        raise ConfigurationError("PASSWORD_ENCODING_VALIDATION_FAILED")
    path.write_text(content, encoding="utf-8")
    return list(updates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Session pooler host copied from Connect")
    parser.add_argument("--username", required=True, help="Session pooler user copied from Connect")
    parser.add_argument("--migration-mode", choices=("direct", "session"), default="session")
    args = parser.parse_args()
    code = None
    try:
        if not sys.stdin.isatty():
            raise ConfigurationError("INTERACTIVE_TERMINAL_REQUIRED")
        with warnings.catch_warnings():
            # Fail before getpass can fall back to echoing input in an unsafe terminal.
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("PostgreSQL password (hidden, local only): ")
            confirmation = getpass.getpass("Confirm PostgreSQL password: ")
        if not password:
            raise ConfigurationError("EMPTY_PASSWORD")
        if password != confirmation:
            raise ConfigurationError("PASSWORD_MISMATCH")
        updated = configure(
            ROOT / "backend/.env", args.host, args.username, password, args.migration_mode
        )
    except ConfigurationError as error:
        code = str(error)  # Only fixed codes created in this module.
    except getpass.GetPassWarning:
        code = "HIDDEN_INPUT_UNAVAILABLE"
    except (EOFError, KeyboardInterrupt):
        code = "INPUT_CANCELLED"
    except FileNotFoundError:
        code = "ENV_FILE_NOT_FOUND"
    except PermissionError:
        code = "FILE_PERMISSION_DENIED"
    except OSError:
        code = "FILE_IO_FAILED"
    except (ValueError, UnicodeError):
        code = "CONFIGURATION_VALIDATION_FAILED"
    if code:
        print(
            json.dumps(
                {"status": "failed", "errorCode": code, "networkAccessPerformed": False}
            )
        )
        return 1
    print(
        json.dumps(
            {
                "updatedVariables": updated,
                "passwordRoundTripVerified": True,
                "networkAccessPerformed": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
