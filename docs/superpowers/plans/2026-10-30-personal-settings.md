# Personal settings implementation plan

**Goal:** Remove the privacy settings surface, make personal AI, voice and saved history available by default, and move account actions into Cá nhân.

**Architecture:** Keep the existing React layout and account deletion protocol. Retire personal consent switches at the API boundary while preserving eligibility, provider availability, guest expiry, social publication and account security checks. No schema migration is needed; legacy flags no longer disable personal features.

**Design:** Preserve MoodPrint's green palette and typography. Use a flat list of account actions, clear section spacing, and a protected confirmation dialog for account deletion. Redirect the old settings URL to Cá nhân and remove privacy links and tour content.

**Constraints:** Preserve pre-existing edits. Do not modify either .gitignore. Do not publish, commit, or change live data.

- [x] Add regression coverage for legacy settings redirect, account actions, and personal feature availability.
- [x] Replace Settings/DataControls with account controls in the personal tab; clean navigation, feedback return links and onboarding.
- [x] Retire personal opt-out flags in backend authorization and use available saved history by default, including legacy preferences.
- [x] Run frontend unit tests, build, targeted browser journeys and backend tests; inspect mobile/desktop rendering.

**Review focus:** Existing disabled consent records; unavailable providers; guest expiry and trial ending; reauthentication and irreversible account deletion; narrow mobile layout and keyboard focus.

**Verification:** Frontend: 103 unit tests and production build passed. Browser: 96 journey tests passed, plus focused layout/voice checks and final account/reauthentication/accessibility checks. Backend: 433 passed, 697 skipped (including database integration tests requiring TEST_DATABASE_URL); scoped Ruff and diff checks passed. Mobile and desktop screenshots inspected. Independent read-only review found no material defects.

**Compatibility:** Retain the old settings URL as a redirect and personal consent endpoints as no-ops. Stored legacy flags do not block personal use. Provider availability, guest expiry, quotas, explicit social publication, and review of individual memory proposals remain enforced. Semantic provider configuration is unchanged. Fullstack browser tests were adapted to the removed UI but could not be executed without the database integration environment.
