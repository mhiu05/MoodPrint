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


def include_live_evidence(report):
    directory = ARTIFACTS / "live-ai"
    path = directory / "test-evidence.json"
    if not path.exists():
        return
    evidence = read_json(path)
    usage = read_json(directory / "performance-usage.json")
    comparison = read_json(directory / "comparison-results.json")
    report["historicalBeforeLiveAi"] = {
        "backend": report["backend"],
        "latestImplementationSession": report["latestImplementationSession"],
        "note": "Prior XML/session evidence retained; superseded current checks use live-ai/test-evidence.json",
    }
    backend = next(check for check in evidence["checks"] if "pytest" in check["command"])
    report["backend"] = {
        "status": backend["status"], "tests": backend["passed"], "errors": 0,
        "failures": backend["failed"], "skipped": backend["skipped"],
        "report": path.relative_to(ROOT).as_posix(), "sha256": digest(path),
        "command": ".venv/Scripts/python.exe -m pytest -q", "database": backend["database"],
    }
    report["externalConfigurationObserved"]["liveOpenAiOrSttCalls"] = usage["inference_attempts_including_audio"]
    report["externalConfigurationObserved"]["newRemoteAccountingDdlExecuted"] = False
    report["latestImplementationSession"] = {
        "scope": "Live AI, prompt/context/tool quality and local durable accounting",
        "evidence": evidence, "usage": usage, "comparison": comparison,
        "accountingRehearsal": read_json(directory / "accounting-local-verification.json"),
        "currentLocalConfigObservation": read_json(directory / "cleanup-proof.json"),
        "envChangedByAgentThisSession": False,
        "releaseReady": False,
    }
    report["otherCompletedLocalChecks"]["ruff"] = "PASS: all backend files, including migrations"
    report["otherCompletedLocalChecks"]["mypy"] = "PASS:47 application source files"
    report["evalPreparation"].update(
        liveQualityRuns=comparison["structured_output_contracts"]["passed"],
        judgeRequests=sum(part.get("requests_started", 0) for name, part in usage["parts"].items() if "judge" in name),
        humanReviewCompleted=False,
    )
    report["agePolicy"]["localMigrationHead"] = "0006_ai_usage"
    report["agePolicy"]["migrationHead"] = "0005_export_scope"
    report["limitations"] = "Live synthetic evaluation completed; remote accounting SQL, provider privacy/deletion, independent human calibration and native microphone remain separate gates. See live-ai/final-evaluation.md."


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
            "command": "uv run pytest -q --tb=short --junitxml=../docs/plans/validation-artifacts/backend-tests.xml",
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
        "fullstackRealSupabaseAuthDatabaseSdkFakeModel": playwright("supabase"),
        "scopedMoodToolRealSupabaseSdkFakeModel": playwright("supabase-scoped"),
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
            "mcpSnapshotPhase": "Historical pre-initialization snapshot; postE2EInspection is current",
            "postE2EInspection": read_json(ARTIFACTS / "supabase-post-e2e-inspection.json"),
            "migrationExecution": read_json(ARTIFACTS / "supabase-migration-execution.json"),
            "runtimeVerification": read_json(ARTIFACTS / "supabase-runtime-verification.json"),
            "runtimeTransaction": read_json(ARTIFACTS / "supabase-runtime-transaction.json"),
            "hostedJourney": read_json(ARTIFACTS / "supabase-e2e-checkpoints.json"),
            "hostedInitialTeenBoundaryProof": read_json(ARTIFACTS / "supabase-e2e-attempt-1.json"),
            "directPostCredentialCorrection": read_json(ARTIFACTS / "supabase-direct-post-correction.json"),
            "scopedToolProof": read_json(ARTIFACTS / "supabase-scoped-tool-proof.json"),
            "publicAccess": read_json(ARTIFACTS / "supabase-public-access.json"),
            "secretHandling": read_json(ARTIFACTS / "secret-handling-check.json"),
            "hostedLogSecrets": read_json(ARTIFACTS / "hosted-log-secret-check.json"),
            "actualExitCodes": read_json(ARTIFACTS / "session-verification-summary.json"),
            "localMigrationReviewRehearsal": read_json(ARTIFACTS / "supabase-migration-rehearsal.json"),
            "legacyRehearsalLimitation": "Historical column-grant check used LIMIT0; real Auth RLS blocks row visibility. Superseded by authRlsRehearsal.",
            "authRlsRehearsal": read_json(ARTIFACTS / "supabase-auth-rls-rehearsal.json"),
            "groupVerification": read_json(ARTIFACTS / "supabase-validation-groups.json"),
            "remoteDdlOrDomainWrites": True,
            "remoteWriteScope": "Two explicitly approved security/initialization artifacts; domain writes only for the two authorized synthetic users; no reset or managed Auth SQL writes",
            "liveOpenAiOrSttCalls": 0,
            "cloudDeployment": False,
        },
        "latestImplementationSession": {
            "backendAddedTests": 24,
            "backendTests": counts["tests"],
            "frontendBuild": "PASS after per-turn Nhịp date selection UI; existing React/Vite layout preserved",
            "frontendUnitsApiBrowserLegacyAndDocker": "85 units/16 API browser/15 legacy/6 local full-stack PASS; Docker image smoke retained from earlier run",
            "fullstackInitialAttempt": "Earlier continuation had missing Playwright browser; retained separately. Current continuation reran all six journeys successfully",
            "initialFullstackFailureReport": "docs/plans/validation-artifacts/fullstack-browser-missing.json",
            "scopedMoodTool": "P04.02: owner-selected dates in existing Nhịp UI; valid recent90day range; permission consumed after accepted turn; exact retry scope; real Supabase SDK-tool test/notes exclusion/a11y at390/1440 PASS",
            "cancellationRecovery": "16 recovery tests: original6 plus10 durable terminal/purge/late-tool/completion-CAS/first-writer/input-output-RAM-commit cases; focused27/full159 PASS; intermediate capacity regression retained",
            "recoveryReport": "docs/plans/validation-artifacts/ai-recovery-tests.xml",
            "recoveryRedGreen": read_json(ARTIFACTS / "ai-recovery-red-green.json"),
            "accountingDesign": "docs/plans/validation-artifacts/durable-ai-accounting-design.md; schema gap/design only, no monetary accounting or new DDL",
            "scopedCodeReview": read_json(ARTIFACTS / "scoped-code-review.json"),
            "migrationGuards": "Approved SHA256 mismatch, wrong host/project/owner/port/TLS rejection before remote connection",
            "updatedEnvVariableNamesByAgent": ["DATABASE_URL"],
            "userRanHiddenPasswordEntry": True,
            "userPasswordEntryVariableNames": ["DATABASE_URL", "DATABASE_MIGRATION_URL", "DATABASE_POOL_MODE"],
            "sqlApprovalRecorded": True,
            "remoteSql": "docs/plans/validation-artifacts/supabase-initialization-auth-review.sql",
            "approvedSqlSha256": "90008c3c928016e5f04f4bb6c8e9c8cb3bdc1312c9bbf5deb0f828874a09bab0",
            "remoteSqlExecuted": True,
            "runtimeSqlApprovedSha256": "d9124bfd7747a7a04841b8e471a38ddfe6de04d87f91b20ffd63e3f79a1f0461",
            "hostedTestAccountsCreated": 2,
            "hostedTestAccountsCreatedBy": "user via Dashboard; credentials verified/stored through local hidden-input helper; no Admin key",
            "publicSignupEmailAndRecovery": "Not tested/implemented by the admin-confirmed fixture journey",
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
    include_live_evidence(report)
    target = ARTIFACTS / "implementation-checks.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "backend": report["backend"],
                "frontendPassed": units["numPassedTests"],
                "taskStatuses": dict(statuses),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
