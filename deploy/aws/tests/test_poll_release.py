import json
import pathlib
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import poll_release


REPOSITORY = "mhiu05/MoodPrint"
SHA = "a" * 40
API_IMAGE = "ghcr.io/mhiu05/moodprint-api"
WEB_IMAGE = "ghcr.io/mhiu05/moodprint-web"
API_DIGEST = "sha256:" + "1" * 64
WEB_DIGEST = "sha256:" + "2" * 64


def valid_manifest():
    return {
        "schema_version": 1,
        "repository": REPOSITORY,
        "branch": "main",
        "commit_sha": SHA,
        "ci_run_id": 12345,
        "publish_run_id": 67890,
        "images": {
            "api": {
                "name": API_IMAGE,
                "digest": API_DIGEST,
                "ref": f"{API_IMAGE}@{API_DIGEST}",
                "revision": SHA,
            },
            "web": {
                "name": WEB_IMAGE,
                "digest": WEB_DIGEST,
                "ref": f"{WEB_IMAGE}@{WEB_DIGEST}",
                "revision": SHA,
            },
        },
    }


def valid_ci_run():
    return {
        "head_sha": SHA,
        "head_branch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "workflow_id": poll_release.VERIFY_WORKFLOW_ID,
        "path": ".github/workflows/verify.yml",
        "head_repository": {"full_name": REPOSITORY},
        "repository": {"full_name": REPOSITORY},
    }


def valid_publish_run():
    return {
        "id": 67890,
        "head_sha": SHA,
        "head_branch": "main",
        "event": "workflow_run",
        "status": "completed",
        "conclusion": "success",
        "path": ".github/workflows/deploy-staging.yml",
        "head_repository": {"full_name": REPOSITORY},
        "repository": {"full_name": REPOSITORY},
    }


class ManifestValidationTests(unittest.TestCase):
    def test_accepts_current_main_manifest_with_digest_pinned_images(self):
        result = poll_release.validate_manifest(
            valid_manifest(), REPOSITORY, SHA, API_IMAGE, WEB_IMAGE
        )
        self.assertEqual(result["ci_run_id"], 12345)
        self.assertEqual(result["images"]["api"]["ref"], f"{API_IMAGE}@{API_DIGEST}")

    def test_rejects_wrong_repository_or_commit(self):
        for key, value in (("repository", "attacker/other"), ("commit_sha", "b" * 40)):
            with self.subTest(key=key):
                manifest = valid_manifest()
                manifest[key] = value
                with self.assertRaises(poll_release.ValidationError):
                    poll_release.validate_manifest(
                        manifest, REPOSITORY, SHA, API_IMAGE, WEB_IMAGE
                    )

    def test_rejects_mutable_or_unexpected_image_references(self):
        manifest = valid_manifest()
        manifest["images"]["api"]["ref"] = f"{API_IMAGE}:latest"
        with self.assertRaises(poll_release.ValidationError):
            poll_release.validate_manifest(manifest, REPOSITORY, SHA, API_IMAGE, WEB_IMAGE)

    def test_rejects_invalid_digest_and_run_ids(self):
        for change in (
            lambda m: m["images"]["web"].update(digest="latest"),
            lambda m: m.update(ci_run_id=0),
            lambda m: m.update(publish_run_id="67890"),
        ):
            with self.subTest(change=change):
                manifest = valid_manifest()
                change(manifest)
                with self.assertRaises(poll_release.ValidationError):
                    poll_release.validate_manifest(
                        manifest, REPOSITORY, SHA, API_IMAGE, WEB_IMAGE
                    )


class CiRunValidationTests(unittest.TestCase):
    def test_accepts_only_successful_push_verification_on_main(self):
        run = valid_ci_run()
        poll_release.validate_ci_run(run, REPOSITORY, SHA)
        run["path"] += "@refs/heads/main"
        poll_release.validate_ci_run(run, REPOSITORY, SHA)

    def test_rejects_pull_request_or_non_successful_runs(self):
        for key, value in (("event", "pull_request"), ("conclusion", "failure"),
                           ("head_branch", "feature"), ("head_sha", "b" * 40),
                           ("workflow_id", 1), ("path", ".github/workflows/other.yml")):
            with self.subTest(key=key):
                run = valid_ci_run()
                run[key] = value
                with self.assertRaises(poll_release.ValidationError):
                    poll_release.validate_ci_run(run, REPOSITORY, SHA)


class PublishRunValidationTests(unittest.TestCase):
    def test_accepts_completed_publish_run_for_same_main_commit(self):
        run = valid_publish_run()
        poll_release.validate_publish_run(run, REPOSITORY, SHA, 67890)
        run["path"] += "@refs/heads/main"
        poll_release.validate_publish_run(run, REPOSITORY, SHA, 67890)

    def test_rejects_wrong_workflow_event_or_run_id(self):
        for key, value in (("event", "pull_request"), ("head_sha", "b" * 40),
                           ("conclusion", "failure"), ("path", "verify.yml")):
            with self.subTest(key=key):
                run = valid_publish_run()
                run[key] = value
                with self.assertRaises(poll_release.ValidationError):
                    poll_release.validate_publish_run(run, REPOSITORY, SHA, 67890)
        with self.assertRaises(poll_release.ValidationError):
            poll_release.validate_publish_run(valid_publish_run(), REPOSITORY, SHA, 1)


class AttestationCommandTests(unittest.TestCase):
    def test_pins_exact_workflow_identity_and_main_source(self):
        bundle_path = pathlib.Path("/run/moodprint/test-bundle.jsonl")
        trusted_root_path = pathlib.Path("/run/moodprint/test-trusted-root.jsonl")
        command = poll_release.attestation_command(
            "release.json", REPOSITORY, SHA, bundle_path, trusted_root_path
        )
        self.assertEqual(command[3], "release.json")
        self.assertIn("--cert-identity", command)
        self.assertNotIn("--signer-workflow", command)
        self.assertEqual(command[command.index("--bundle") + 1], str(bundle_path))
        self.assertEqual(
            command[command.index("--custom-trusted-root") + 1], str(trusted_root_path)
        )
        identity_index = command.index("--cert-identity") + 1
        self.assertEqual(
            command[identity_index],
            "https://github.com/mhiu05/MoodPrint/.github/workflows/deploy-staging.yml@refs/heads/main",
        )
        self.assertEqual(command[command.index("--source-ref") + 1], "refs/heads/main")
        self.assertEqual(command[command.index("--source-digest") + 1], SHA)

    def test_uses_oci_scheme_for_container_image_subjects(self):
        bundle_path = pathlib.Path("/run/moodprint/test-bundle.jsonl")
        trusted_root_path = pathlib.Path("/run/moodprint/test-trusted-root.jsonl")
        for image_ref in (f"{API_IMAGE}@{API_DIGEST}", f"{WEB_IMAGE}@{WEB_DIGEST}"):
            with self.subTest(image_ref=image_ref):
                command = poll_release.attestation_command(
                    image_ref, REPOSITORY, SHA, bundle_path, trusted_root_path
                )
                self.assertEqual(command[3], f"oci://{image_ref}")


class GitHubEnvironmentTests(unittest.TestCase):
    def test_uses_writable_xdg_cache_for_sigstore_tuf(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = pathlib.Path(directory) / "gh-config"
            environment = poll_release.prepare_gh_environment(config_dir)
            expected_cache = pathlib.Path(directory) / "xdg-cache"

            self.assertEqual(environment["XDG_CACHE_HOME"], str(expected_cache))
            self.assertTrue(expected_cache.is_dir())
            self.assertEqual(stat.S_IMODE(expected_cache.stat().st_mode), 0o700)


class AttestationBundleTests(unittest.TestCase):
    def test_downloads_public_bundles_as_protected_jsonl(self):
        first_bundle = {
            "mediaType": "application/vnd.dev.sigstore.bundle+json;version=0.3",
            "dsseEnvelope": {},
            "verificationMaterial": {},
        }
        second_bundle = {
            "mediaType": "application/vnd.dev.sigstore.bundle+json;version=0.3",
            "dsseEnvelope": {"payload": "second"},
            "verificationMaterial": {},
        }
        response = {
            "attestations": [
                {
                    "repository_id": poll_release.GITHUB_REPOSITORY_ID,
                    "bundle": first_bundle,
                },
                {
                    "repository_id": poll_release.GITHUB_REPOSITORY_ID,
                    "bundle": second_bundle,
                },
            ]
        }

        with tempfile.TemporaryDirectory() as directory:
            destination = pathlib.Path(directory) / "bundles.jsonl"
            with patch.object(poll_release, "github_get", return_value=response) as get:
                poll_release.download_attestation_bundles(API_DIGEST, REPOSITORY, destination)

            self.assertEqual(
                [json.loads(line) for line in destination.read_text().splitlines()],
                [first_bundle, second_bundle],
            )
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertEqual(
                get.call_args.args[0],
                f"{poll_release.API_BASE}/repos/{REPOSITORY}/attestations/{API_DIGEST}?per_page=100",
            )

    def test_rejects_missing_or_malformed_attestation_bundles(self):
        valid_bundle = {
            "mediaType": "application/vnd.dev.sigstore.bundle+json;version=0.3",
            "dsseEnvelope": {},
            "verificationMaterial": {},
        }
        for response in (
            None,
            {"attestations": []},
            {"attestations": [{"repository_id": 1, "bundle": valid_bundle}]},
            {
                "attestations": [
                    {"repository_id": poll_release.GITHUB_REPOSITORY_ID, "bundle": {}}
                ]
            },
        ):
            with self.subTest(response=response):
                with tempfile.TemporaryDirectory() as directory:
                    destination = pathlib.Path(directory) / "bundles.jsonl"
                    with patch.object(poll_release, "github_get", return_value=response):
                        with self.assertRaises(poll_release.ValidationError):
                            poll_release.download_attestation_bundles(
                                API_DIGEST, REPOSITORY, destination
                            )


if __name__ == "__main__":
    unittest.main()
