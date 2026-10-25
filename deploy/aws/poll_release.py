#!/usr/bin/env python3
"""Poll GitHub for a verified release of the current main commit and deploy it."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


VERIFY_WORKFLOW_ID = 394882427
VERIFY_WORKFLOW_PATH = ".github/workflows/verify.yml@"
PUBLISH_WORKFLOW_PATH = ".github/workflows/deploy-staging.yml@"
PUBLISH_WORKFLOW = ".github/workflows/deploy-staging.yml"
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PARAMETER_RE = re.compile(r"^/[A-Za-z0-9/_-]+$")
IMAGE_RE = re.compile(r"^ghcr\.io/[a-z0-9][a-z0-9._/-]*$")
API_BASE = "https://api.github.com"
BASE = Path("/opt/moodprint")
CONFIG = BASE / "deployment.conf"
ACTIVE = BASE / "staging.env"
PREVIOUS = BASE / "staging.previous.env"
LOCK = Path("/run/lock/moodprint-release-poll.lock")


class ValidationError(ValueError):
    """Raised when release metadata does not match the expected provenance."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_manifest(
    manifest: Any,
    repository: str,
    commit_sha: str,
    api_image: str,
    web_image: str,
) -> dict[str, Any]:
    _require(isinstance(manifest, dict), "release manifest is not an object")
    _require(type(manifest.get("schema_version")) is int and manifest["schema_version"] == 1,
             "unsupported release manifest schema")
    _require(manifest.get("repository") == repository, "release repository does not match")
    _require(manifest.get("branch") == "main", "release branch is not main")
    _require(manifest.get("commit_sha") == commit_sha, "release commit does not match main")
    for key in ("ci_run_id", "publish_run_id"):
        _require(type(manifest.get(key)) is int and manifest[key] > 0,
                 f"release {key} is invalid")

    images = manifest.get("images")
    _require(isinstance(images, dict), "release image list is invalid")
    for component, expected_name in (("api", api_image), ("web", web_image)):
        image = images.get(component)
        _require(isinstance(image, dict), f"release {component} image is missing")
        _require(image.get("name") == expected_name,
                 f"release {component} image name does not match")
        digest = image.get("digest")
        _require(isinstance(digest, str) and DIGEST_RE.fullmatch(digest) is not None,
                 f"release {component} digest is invalid")
        _require(image.get("ref") == f"{expected_name}@{digest}",
                 f"release {component} reference is not digest-pinned")
        _require(image.get("revision") == commit_sha,
                 f"release {component} revision does not match main")
    return manifest


def validate_ci_run(run: Any, repository: str, commit_sha: str) -> None:
    _require(isinstance(run, dict), "CI run response is not an object")
    _require(run.get("head_sha") == commit_sha, "CI run commit does not match main")
    _require(run.get("head_branch") == "main", "CI run branch is not main")
    _require(run.get("event") == "push", "CI run was not triggered by a push")
    _require(run.get("status") == "completed" and run.get("conclusion") == "success",
             "CI run did not complete successfully")
    _require(run.get("workflow_id") == VERIFY_WORKFLOW_ID,
             "CI run is not the local application verification workflow")
    path = run.get("path")
    _require(isinstance(path, str) and path.startswith(VERIFY_WORKFLOW_PATH),
             "CI run workflow path does not match")
    head_repository = run.get("head_repository")
    repository_object = run.get("repository")
    _require(isinstance(head_repository, dict) and head_repository.get("full_name") == repository,
             "CI run source repository does not match")
    _require(isinstance(repository_object, dict) and repository_object.get("full_name") == repository,
             "CI run target repository does not match")


def validate_publish_run(
    run: Any, repository: str, commit_sha: str, run_id: int
) -> None:
    _require(isinstance(run, dict), "publish run response is not an object")
    _require(run.get("id") == run_id, "publish run ID does not match the manifest")
    _require(run.get("head_sha") == commit_sha, "publish run commit does not match main")
    _require(run.get("head_branch") == "main", "publish run branch is not main")
    _require(run.get("event") in ("workflow_run", "workflow_dispatch"),
             "publish run event is not allowed")
    _require(run.get("status") == "completed" and run.get("conclusion") == "success",
             "publish workflow did not complete successfully")
    path = run.get("path")
    _require(isinstance(path, str) and path.startswith(PUBLISH_WORKFLOW_PATH),
             "publish workflow path does not match")
    head_repository = run.get("head_repository")
    repository_object = run.get("repository")
    _require(isinstance(head_repository, dict) and head_repository.get("full_name") == repository,
             "publish run source repository does not match")
    _require(isinstance(repository_object, dict) and repository_object.get("full_name") == repository,
             "publish run target repository does not match")


def parse_config(path: Path = CONFIG) -> dict[str, str]:
    info = path.lstat()
    _require(stat.S_ISREG(info.st_mode) and info.st_uid == 0,
             "deployment.conf must be a root-owned regular file")
    _require(info.st_mode & 0o022 == 0,
             "deployment.conf must not be writable by group or others")
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValidationError(f"invalid deployment.conf line {number}")
        key, value = stripped.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in values:
            raise ValidationError(f"invalid deployment.conf key on line {number}")
        if any(character in value for character in "\r\n\x00"):
            raise ValidationError(f"invalid deployment.conf value on line {number}")
        values[key] = value
    return values


def validate_config(values: dict[str, str]) -> None:
    required = (
        "AWS_REGION",
        "GITHUB_REPOSITORY",
        "GHCR_API_IMAGE",
        "GHCR_WEB_IMAGE",
        "GHCR_USERNAME",
        "APP_DOMAIN",
        "PARAMETER_NAME",
    )
    missing = [key for key in required if not values.get(key)]
    _require(not missing, f"deployment.conf is missing {', '.join(missing)}")
    _require(re.fullmatch(r"[a-z]{2}-[a-z]+-\d", values["AWS_REGION"]) is not None,
             "AWS_REGION is invalid")
    _require(REPOSITORY_RE.fullmatch(values["GITHUB_REPOSITORY"]) is not None,
             "GITHUB_REPOSITORY is invalid")
    for key in ("GHCR_API_IMAGE", "GHCR_WEB_IMAGE"):
        _require(IMAGE_RE.fullmatch(values[key]) is not None and "@" not in values[key],
                 f"{key} must be a GHCR repository name")
    _require(values["GHCR_USERNAME"].lower() == values["GITHUB_REPOSITORY"].split("/", 1)[0].lower(),
             "GHCR_USERNAME must match the repository owner")
    _require(re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", values["APP_DOMAIN"]) is not None,
             "APP_DOMAIN is invalid")
    _require(PARAMETER_RE.fullmatch(values["PARAMETER_NAME"]) is not None,
             "PARAMETER_NAME is invalid")
    token_parameter = values.get("GHCR_TOKEN_PARAMETER_NAME", "")
    _require(not token_parameter or PARAMETER_RE.fullmatch(token_parameter) is not None,
             "GHCR_TOKEN_PARAMETER_NAME is invalid")


def github_get(url: str) -> dict[str, Any] | None:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "MoodPrint-release-poller",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError(f"GitHub API returned HTTP {error.code}") from None
    except (TimeoutError, urllib.error.URLError) as error:
        raise RuntimeError("GitHub API request failed") from error
    if len(raw) > 1024 * 1024:
        raise RuntimeError("GitHub API response exceeded the size limit")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("GitHub API returned invalid JSON") from error
    if not isinstance(value, dict):
        raise RuntimeError("GitHub API returned an unexpected response")
    return value


def download_manifest(url: str, expected_url: str, destination: Path) -> dict[str, Any]:
    _require(url == expected_url, "release manifest asset URL does not match its SHA tag")
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/octet-stream", "User-Agent": "MoodPrint-release-poller"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(256 * 1024 + 1)
    except (urllib.error.HTTPError, TimeoutError, urllib.error.URLError) as error:
        raise RuntimeError("release manifest download failed") from error
    if len(raw) > 256 * 1024:
        raise RuntimeError("release manifest exceeded the size limit")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("release manifest is invalid JSON") from error
    if not isinstance(manifest, dict):
        raise RuntimeError("release manifest is not an object")
    destination.write_bytes(raw)
    os.chmod(destination, 0o600)
    return manifest


def download_attestation_bundles(
    subject_digest: str, repository: str, destination: Path
) -> None:
    _require(DIGEST_RE.fullmatch(subject_digest) is not None,
             "attestation subject digest is invalid")
    response = github_get(
        f"{API_BASE}/repos/{repository}/attestations/{subject_digest}?per_page=100"
    )
    _require(response is not None, "attestation bundles were not found")
    attestations = response.get("attestations")
    _require(isinstance(attestations, list) and attestations,
             "attestation bundle list is invalid")

    bundles: list[str] = []
    for attestation in attestations:
        _require(isinstance(attestation, dict), "attestation entry is invalid")
        bundle = attestation.get("bundle")
        _require(
            isinstance(bundle, dict)
            and isinstance(bundle.get("dsseEnvelope"), dict)
            and isinstance(bundle.get("verificationMaterial"), dict),
            "attestation bundle is invalid",
        )
        bundles.append(json.dumps(bundle, separators=(",", ":")))

    destination.write_text("\n".join(bundles) + "\n", encoding="utf-8")
    os.chmod(destination, 0o600)


def prepare_gh_environment(config_dir: Path) -> dict[str, str]:
    config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(config_dir, 0o700)
    environment = os.environ.copy()
    environment["GH_CONFIG_DIR"] = str(config_dir)
    environment["GH_PROMPT_DISABLED"] = "1"
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN"):
        environment.pop(name, None)
    return environment


def download_trusted_root(destination: Path, environment: dict[str, str]) -> None:
    try:
        result = subprocess.run(
            ["gh", "attestation", "trusted-root"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
        )
    except FileNotFoundError as error:
        raise RuntimeError("GitHub CLI is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Sigstore trusted root request timed out") from error
    _require(result.returncode == 0 and result.stdout.strip(),
             "Sigstore trusted root could not be retrieved")
    destination.write_text(result.stdout, encoding="utf-8")
    os.chmod(destination, 0o600)


def attestation_command(
    subject: str,
    repository: str,
    commit_sha: str,
    bundle_path: Path,
    trusted_root_path: Path,
) -> list[str]:
    return [
        "gh", "attestation", "verify", subject,
        "--bundle", str(bundle_path),
        "--custom-trusted-root", str(trusted_root_path),
        "--repo", repository,
        "--cert-identity",
        f"https://github.com/{repository}/{PUBLISH_WORKFLOW}@refs/heads/main",
        "--source-digest", commit_sha,
        "--source-ref", "refs/heads/main",
        "--deny-self-hosted-runners",
    ]


def verify_attestation(subject: str, repository: str, commit_sha: str,
                       bundle_path: Path, trusted_root_path: Path,
                       environment: dict[str, str] | None = None) -> None:
    command = attestation_command(
        subject, repository, commit_sha, bundle_path, trusted_root_path
    )
    try:
        result = subprocess.run(command, env=environment, check=False,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=120)
    except FileNotFoundError as error:
        raise RuntimeError("GitHub CLI is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("GitHub attestation verification timed out") from error
    if result.returncode != 0:
        raise RuntimeError("GitHub attestation verification failed")


def read_state_sha(path: Path) -> str | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"deployment state {path.name} is not a regular file")
    if path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
        raise RuntimeError(f"deployment state {path.name} has unsafe ownership or mode")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("RELEASE_SHA="):
            value = line.split("=", 1)[1]
            return value if SHA_RE.fullmatch(value) else None
    return None


def prepare_registry_environment(
    values: dict[str, str], docker_config: Path
) -> dict[str, str]:
    docker_config.mkdir(mode=0o700)
    os.chmod(docker_config, 0o700)
    config_file = docker_config / "config.json"
    config_file.write_text("{}\n", encoding="utf-8")
    os.chmod(config_file, 0o600)
    environment = os.environ.copy()
    environment["DOCKER_CONFIG"] = str(docker_config)

    token_parameter = values.get("GHCR_TOKEN_PARAMETER_NAME", "")
    if not token_parameter:
        return environment

    try:
        result = subprocess.run(
            [
                "aws", "ssm", "get-parameter", "--region", values["AWS_REGION"],
                "--name", token_parameter, "--with-decryption",
                "--query", "Parameter.Value", "--output", "text",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("AWS CLI is not installed") from error
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("GHCR read token could not be retrieved from Parameter Store")

    try:
        login = subprocess.run(
            ["docker", "login", "ghcr.io", "--username", values["GHCR_USERNAME"],
             "--password-stdin"],
            input=result.stdout.strip() + "\n",
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Docker is not installed") from error
    if login.returncode != 0:
        raise RuntimeError("Docker could not authenticate to GHCR")
    return environment


def cleanup_images(api_image: str, web_image: str) -> None:
    keep_refs: set[str] = set()
    for state_path in (ACTIVE, PREVIOUS):
        if not state_path.exists():
            continue
        for line in state_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(("API_IMAGE=", "WEB_IMAGE=")):
                ref = line.split("=", 1)[1]
                if "@sha256:" in ref:
                    keep_refs.add(ref)

    keep_ids: set[str] = set()
    for reference in keep_refs:
        result = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", reference],
                                check=False, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            keep_ids.add(result.stdout.strip())

    for repository in (api_image, web_image):
        result = subprocess.run(
            ["docker", "image", "ls", "--format", "{{.ID}}", repository],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            continue
        for image_id in set(result.stdout.split()):
            if image_id not in keep_ids:
                subprocess.run(["docker", "image", "rm", image_id],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_once(values: dict[str, str]) -> None:
    repository = values["GITHUB_REPOSITORY"]
    api_image = values["GHCR_API_IMAGE"]
    web_image = values["GHCR_WEB_IMAGE"]

    main = github_get(f"{API_BASE}/repos/{repository}/commits/main")
    if not main or not isinstance(main.get("sha"), str) or not SHA_RE.fullmatch(main["sha"]):
        raise RuntimeError("GitHub did not return a valid main commit SHA")
    commit_sha = main["sha"]
    if read_state_sha(ACTIVE) == commit_sha:
        return

    tag = f"staging-{commit_sha}"
    release = github_get(f"{API_BASE}/repos/{repository}/releases/tags/{tag}")
    if release is None:
        print(f"No verified release is available for current main {commit_sha} yet.")
        return
    _require(release.get("tag_name") == tag and release.get("prerelease") is True
             and release.get("draft") is False,
             "release metadata does not match the current main SHA")
    assets = release.get("assets")
    _require(isinstance(assets, list), "release assets are invalid")
    manifest_assets = [asset for asset in assets if isinstance(asset, dict)
                       and asset.get("name") == "release.json"]
    _require(len(manifest_assets) == 1, "release must contain one release.json asset")

    expected_asset_url = (
        f"https://github.com/{repository}/releases/download/{tag}/release.json"
    )
    with tempfile.TemporaryDirectory(prefix="release-poll-", dir="/run/moodprint") as temp_name:
        temp = Path(temp_name)
        manifest_path = temp / "release.json"
        manifest = download_manifest(
            str(manifest_assets[0].get("browser_download_url", "")),
            expected_asset_url,
            manifest_path,
        )
        validate_manifest(manifest, repository, commit_sha, api_image, web_image)
        gh_environment = prepare_gh_environment(temp / "gh-config")
        trusted_root_path = temp / "trusted-root.jsonl"
        download_trusted_root(trusted_root_path, gh_environment)
        manifest_digest = "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        manifest_bundle = temp / "manifest-attestations.jsonl"
        download_attestation_bundles(manifest_digest, repository, manifest_bundle)
        verify_attestation(
            str(manifest_path), repository, commit_sha, manifest_bundle,
            trusted_root_path, gh_environment,
        )

        ci_run_id = manifest["ci_run_id"]
        ci_run = github_get(f"{API_BASE}/repos/{repository}/actions/runs/{ci_run_id}")
        validate_ci_run(ci_run, repository, commit_sha)
        publish_run_id = manifest["publish_run_id"]
        publish_run = github_get(f"{API_BASE}/repos/{repository}/actions/runs/{publish_run_id}")
        validate_publish_run(publish_run, repository, commit_sha, publish_run_id)

        environment = prepare_registry_environment(values, temp / "docker-config")
        environment.update(gh_environment)
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN"):
            environment.pop(name, None)
        try:
            for component in ("api", "web"):
                image = manifest["images"][component]
                bundle_path = temp / f"{component}-attestations.jsonl"
                download_attestation_bundles(
                    image["digest"], repository, bundle_path
                )
                verify_attestation(
                    f"oci://{image['ref']}", repository, commit_sha,
                    bundle_path, trusted_root_path, environment,
                )

            latest = github_get(f"{API_BASE}/repos/{repository}/commits/main")
            if not latest or latest.get("sha") != commit_sha:
                print("Main moved during verification; release deployment was skipped.")
                return

            deploy_script = BASE / "deploy.sh"
            if not deploy_script.is_file() or deploy_script.is_symlink():
                raise RuntimeError("the root-owned deployment script is unavailable")
            result = subprocess.run(
                [str(deploy_script), manifest["images"]["api"]["ref"],
                 manifest["images"]["web"]["ref"], commit_sha],
                check=False,
                env=environment,
            )
            if result.returncode != 0:
                raise RuntimeError("deployment failed; deploy.sh recorded its rollback result")
            cleanup_images(api_image, web_image)
            print(f"Deployed verified MoodPrint release {commit_sha}.")
        finally:
            token_config = temp / "docker-config"
            if token_config.exists():
                for child in token_config.iterdir():
                    child.unlink(missing_ok=True)
                token_config.rmdir()


def main() -> int:
    if os.geteuid() != 0:
        print("Run as root.", file=sys.stderr)
        return 2
    try:
        values = parse_config()
        validate_config(values)
        LOCK.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        with LOCK.open("w", encoding="utf-8") as lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("Another release poll is already running.")
                return 0
            Path("/run/moodprint").mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod("/run/moodprint", 0o700)
            run_once(values)
    except (OSError, RuntimeError, ValidationError, json.JSONDecodeError) as error:
        print(f"Release poll failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
