# Retire Private Profile Notes

## Intent

Remove the user-authored “Hồ sơ riêng” notes feature because it adds an unclear second place to keep personal information. Preserve “Thông tin riêng có thể chia sẻ” identity fields, account support, and the existing AI memory feature.

## Goals

- Remove the private notes section, its create/edit/delete UI, API, and storage model.
- Remove the AI `private_item` proposal path that wrote to the same private notes store.
- Delete existing private-item records and private-item proposals through a forward database migration.
- Keep approved AI memories and ordinary memory proposals. Detach old source references from memories; expire pending memory proposals that depended on deleted private items.
- Keep the profile taxonomy endpoint used by the separate social profile feature.

## Non-goals

- Do not remove AI memories, the identity fields that can be shared by consent, moods, journals, or social profile taxonomy.
- Do not apply the migration to a hosted Supabase database in this code change.
- Do not edit `.gitignore` or overwrite the user's existing workspace changes.

## Approaches

1. Hide only the UI. Rejected because it leaves the create API, AI proposal path, and stored notes active.
2. Remove the private-notes subsystem and its data while preserving approved AI memories. Chosen because it removes the redundant feature without disabling the separate AI memory experience.
3. Remove both private notes and AI memories. Rejected because the user explicitly chose to keep AI memory.

## Data and migration behavior

The migration removes all `private_items` rows and `private_item` proposals. It expires pending memory proposals whose source was a private item, clears source links from other proposals, clears source links from already approved memories, and then drops the private-item table plus the obsolete source and proposal-purpose columns. Approved memory records remain intact. Active-database erasure does not change provider backup retention.

The migration is destructive and requires the repository's hosted Supabase review and release process before deployment. It will only be added to the repository here.

## Constraints

- Keep `OwnIdentity`, `AdultEligibility`, and `AccountActions` on the account page.
- Continue to expose `/taxonomy` from the profiles router.
- Remove obsolete export/deletion scopes and guest-cleanup inventory entries for private items.
- Regenerate the published OpenAPI and TypeScript contracts from the updated application.
- Do not add or run tests in this task; update existing references only where the removed contract requires it.
