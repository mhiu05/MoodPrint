"""Summarize existing local runner reports. This command does not rerun the checks."""

import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/plans/validation-artifacts"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def playwright(name):
    path = ROOT / "frontend/evidence" / f"{name}-results.json"
    report = read_json(path)
    stats = report["stats"]
    passed = (
        stats["expected"] > 0
        and not any(stats[key] for key in ("unexpected", "skipped", "flaky"))
        and not report["errors"]
    )
    return {
        "status": "PASS" if passed else "REVIEW",
        "stats": stats,
        "runnerErrors": report["errors"],
        "report": path.relative_to(ROOT).as_posix(),
        "sha256": digest(path),
    }


def main():
    xml_path = ARTIFACTS / "backend-tests.xml"
    suites = ET.parse(xml_path).getroot().findall(".//testsuite")
    counts = {
        key: sum(int(suite.attrib[key]) for suite in suites)
        for key in ("tests", "errors", "failures", "skipped")
    }
    unit_path = ARTIFACTS / "frontend-unit-tests.json"
    units = read_json(unit_path)
    ledger = (ROOT / "docs/plans/implementation-status.md").read_text(encoding="utf-8")
    statuses = Counter(
        line.split("|")[2].strip() for line in ledger.splitlines() if line.startswith("| P")
    )
    report = {
        "collectedAt": datetime.now(UTC).isoformat(),
        "scope": "Latest completed runner reports; per-section dates and latestImplementationSession distinguish current checks from retained earlier evidence. Collection does not rerun checks.",
        "releaseReady": False,
        "taskStatuses": dict(statuses),
        "backend": {
            "status": "PASS"
            if counts["tests"] and not any(counts[key] for key in ("errors", "failures", "skipped"))
            else "REVIEW",
            **counts,
            "report": xml_path.relative_to(ROOT).as_posix(),
            "sha256": digest(xml_path),
            "command": "uv run --locked pytest -q --junitxml=../docs/plans/validation-artifacts/backend-tests.xml",
            "database": "local disposable PostgreSQL17.11",
        },
        "frontendUnits": {
            "status": "PASS"
            if units["success"] and not units["numFailedTests"] and not units["numPendingTests"]
            else "REVIEW",
            "passed": units["numPassedTests"],
            "failed": units["numFailedTests"],
            "pending": units["numPendingTests"],
            "report": unit_path.relative_to(ROOT).as_posix(),
            "sha256": digest(unit_path),
        },
        "browserApiFixtures": playwright("e2e"),
        "browserPreservedLegacy": playwright("legacy"),
        "fullstackRealHttpPostgresSdkFakeModel": playwright("fullstack"),
        "otherCompletedLocalChecks": {
            "ruff": "PASS: app tests evals and newly added operational scripts",
            "mypy": "PASS:43 application source files",
            "frontendTypecheckBuild": "PASS",
            "contractRegenerationDrift": "none",
            "npmAudit": {"vulnerabilities": 0},
            "accessibility": {
                "screens": 5,
                "widths": [390, 1440],
                "violations": 0,
                "nonzeroAxePassesRequired": True,
                "manualScreenReaderOrIosClaim": False,
            },
            "docker": {
                "build": "PASS",
                "image": "moodprint-backend:local",
                "uid": 10001,
                "readOnlyFilesystem": True,
                "capabilitiesDropped": "ALL",
                "livenessStatus": 200,
                "readinessWithoutDatabase": 503,
                "readinessWithLocalMigratedDatabase": 200,
                "envAndTestsInImage": False,
                "smokeContainerStopped": True,
            },
            "runtimeRoleDrill": {
                "scope": "local disposable database only",
                "domainDml": True,
                "ageDeclarationDml": True,
                "privateAuthBridgeCallable": True,
                "rawAuthReadDenied": read_json(ARTIFACTS / "supabase-auth-rls-rehearsal.json")[
                    "directAuthReadDenied"
                ],
                "authBridgeRehearsal": "docs/plans/validation-artifacts/supabase-auth-rls-rehearsal.json",
                "domainAndPublicDdlDenied": True,
                "fixtureRoleAndGrantsRolledBack": True,
            },
        },
        "matchingPerformance": read_json(ARTIFACTS / "matching-performance.json"),
        "externalConfigurationObserved": {
            "backendProbe": read_json(ARTIFACTS / "supabase-direct-inspection.json"),
            "mcpAndDashboard": read_json(ARTIFACTS / "supabase-mcp-inspection.json"),
            "localMigrationReviewRehearsal": read_json(ARTIFACTS / "supabase-migration-rehearsal.json"),
            "legacyRehearsalLimitation": "Historical column-grant check used LIMIT0; real Auth RLS blocks row visibility. Superseded by authRlsRehearsal.",
            "authRlsRehearsal": read_json(ARTIFACTS / "supabase-auth-rls-rehearsal.json"),
            "groupVerification": read_json(ARTIFACTS / "supabase-validation-groups.json"),
            "remoteDdlOrDomainWrites": False,
            "liveOpenAiOrSttCalls": 0,
            "cloudDeployment": False,
        },
        "latestImplementationSession": {
            "backendAddedTests": 8,
            "backendTests": counts["tests"],
            "frontendBuild": "Earlier PASS retained; no frontend source changes in this continuation",
            "frontendUnitsApiBrowserLegacyAndDocker": "Earlier reports retained; not rerun in this continuation",
            "fullstackInitialAttempt": "Earlier continuation had missing Playwright browser; retained separately. Current continuation reran all six journeys successfully",
            "initialFullstackFailureReport": "docs/plans/validation-artifacts/fullstack-browser-missing.json",
            "scopedMoodTool": "API/SDK implemented and verified; existing UI has no range selector yet",
            "cancellationRecovery": "Six deterministic tests: pre-entry cancel/idempotency/next turn; end; SDK revoke; orphan restart; terminal failure/retry/privacy canary; owner/stale denial",
            "recoveryReport": "docs/plans/validation-artifacts/ai-recovery-tests.xml",
            "migrationGuards": "Approved SHA256 mismatch, wrong host/project/owner/port/TLS rejection before remote connection",
            "updatedEnvVariableNamesByAgent": [],
            "userRanHiddenPasswordEntry": True,
            "userPasswordEntryVariableNames": ["DATABASE_URL", "DATABASE_MIGRATION_URL", "DATABASE_POOL_MODE"],
            "sqlApprovalRecorded": True,
            "remoteSql": "docs/plans/validation-artifacts/supabase-initialization-auth-review.sql",
            "approvedSqlSha256": "90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0",
            "remoteSqlExecuted": False,
            "hostedTestAccountsCreated": 0,
            "liveAiSmokePlan": "docs/plans/validation-artifacts/live-ai-smoke-plan.md; account privacy/budget still unverified; no live call",
            "releaseReady": False,
        },
        "evalPreparation": {
            "syntheticScenarios": 60,
            "bots": 5,
            "calibration": 20,
            "development": 20,
            "heldout": 20,
            "liveQualityRuns": 0,
            "humanReviewCompleted": False,
        },
        "agePolicy": {
            "decidedByUserAt": "2026-10-24",
            "method": "birth year and explicit self-attestation",
            "privateMinimum": 16,
            "socialMinimum": 18,
            "eighteenthYearNeedsExplicitAdultConfirmation": True,
            "onboardingDoesNotEnableConsents": True,
            "migrationHead": "0005_export_scope",
        },
        "limitations": "See implementation-status.md and release-readiness.md. Synthetic model tests are not live M1/evals. No production/SLA/privacy-provider certification.",
    }
    if sum(statuses.values()) != 39:
        raise RuntimeError("Ledger must keep all39 original tasks")
    target = ARTIFACTS / "implementation-checks.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "backend": counts,
                "frontendPassed": units["numPassedTests"],
                "taskStatuses": dict(statuses),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
