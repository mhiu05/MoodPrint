# Per-agent check-in controls — implementation evidence

Scope: frontend K1/K2 of `06-agent-check-in-settings.md`, with route integration owned by the parent implementation. Existing user edits, backend, generated contracts, runtime credentials and `.gitignore` were left alone by this worker.

## Changes

- `useProactiveSettings.ts` shares one external store per `ApiClient`, user ID and client lifecycle epoch. Opening a panel only reads. It serializes writes, rolls back failed optimistic edits, refreshes account-wide limits and server-calculated delivery times, and refetches on foreground/cross-tab invalidation without polling or broadcasting settings content.
- Settings retries after `STALE_VERSION` merge only explicitly edited fields onto fresh server settings. Policy/version and unrelated journal consent always come from that fresh snapshot. A failed retry retains the fresh snapshot, including revoked journal consent. Quiet-hour conflicts also refresh schedules so the editor can link the conflicting owner.
- `AgentCheckInSettings`, `CheckInSlot`, `SharedCheckInSettings`, and `LegacyCheckInSettings` reuse the current schedule contracts. Slots follow route `botId`, independent of conversation/speaker. Journal consent appears only on `nhatky` in three-agent mode, or `nhip` in legacy mode. Global timezone/quiet hours/badges have a shared editor and affected-schedule preview. Legacy migration is explicit; legacy Cầu Nối offers view/disable/delete without an enable control.
- `ConversationInfo` accepts owner identity and an agent-settings slot immediately after the agent description. A stable native dialog host switches between desktop modeless `show()` (`role="region"`) and compact `showModal()`. This preserves editor state across breakpoint changes. During a child modal, compact info closes/hides while its subtree remains mounted; child dialogs portal to `document.body`. The focus loop includes selects/textareas, and portal events stay with the child dialog. Closing a child restores its exact trigger.
- `CheckInsPage` is now a compatibility redirect export. Its duplicate controller/manager is removed. New check-in components do not import `RealApp`.
- Existing `proactive.spec.ts` assertions now use per-agent info routes while retaining schedule payload/version/cap, unread badges, proactive history labels and read-marker assertions. The desktop resize check in `ux-redesign.spec.ts` asserts `dialog:modal`, because the desktop region is now a native modeless dialog.

## Integration contract

```tsx
import { AgentCheckInSettings } from "./checkins/AgentCheckInSettings";

// Props:
// api: ApiClient
// session: Pick<SessionView, "userId" | "features">
// botId: BotId (route owner, never message.speaker/activeAgent)
// botName?: string
// onChildModalChange?: (open: boolean) => void

const [checkInDialogOpen, setCheckInDialogOpen] = useState(false);
<ConversationInfo
  botId={bot.botId}
  botDescription={bot.description}
  suspended={historyOpen || renameOpen || deleteOpen || newConfirmOpen || checkInDialogOpen}
  agentSettings={
    <AgentCheckInSettings
      api={api}
      session={session}
      botId={bot.botId}
      botName={bot.name}
      onChildModalChange={setCheckInDialogOpen}
    />
  }
  {...otherInfoProps}
/>
```

Use the same combined suspension value with `useInfoPanelMounted`. New deep links use `/#/assistants/<botId>?panel=info&section=check-ins`; the focusable section heading ID is `agent-check-ins-<botId>`. Keep an existing `conversation` query when linking from its proactive bubble. Settings work before the first chat and do not require creating a conversation. The parent owns feature gating, Account cleanup, roster/specialist links, redirect wiring, and the Playwright whitelist entry.

## Verification

- RED: controller tests initially failed to import the absent shared controller. Component tests initially failed to import the absent per-agent component. ConversationInfo composition/focus tests failed on missing owner/slot and missing select/textarea support. A later quiet-conflict test failed because the old snapshot lacked another agent's newly enabled slot.
- GREEN: `npx.cmd vitest run src/features/real/checkins/useProactiveSettings.test.ts src/features/real/checkins/checkinsModel.test.ts src/features/real/checkins/AgentCheckInSettings.test.ts src/features/real/ConversationInfo.test.ts` — **23/23 passed, four files**. Coverage includes version-zero creation, authoritative global cap, shared stores/lifecycle isolation, optimistic rollback/serialization, stale settings consent preservation (success and failed retry), stale schedule reload without replay, quiet-conflict refresh, partial delete failure, per-owner slot composition, consent ownership, legacy behavior, unavailable state, and focusable controls.
- `node node_modules/typescript/bin/tsc --noEmit` completed **exit 0** after parent route integration and the main K1/K2 changes. A final pass will be recorded by the integrated worker after all concurrent frontend edits settle.
- `agent-check-in-settings.spec.ts` adds 14 synthetic fixture cases: before-first-chat per-agent controls, owner versus handoff speaker, local fetch failure, 320/390/768/1099/1100/1280px with axe, child modal/focus/draft preservation through resize, global conflict links, stale consent safety, explicit legacy migration/delete, and compact keyboard/200% text.

## Decisions and remaining checks

- Ruling: retain one native dialog host for both layouts instead of replacing a section with a dialog — replacing the host unmounts child editors and loses unsaved drafts on resize. Desktop is explicitly modeless and has no keyboard trap. Tests that intend to count modal overlays must use `dialog:modal`.
- Ruling: keep closed/hidden compact info DOM while a child owns modality — unmounting the parent would also destroy its portaled editor state. `useInfoPanelMounted` continues to represent visible trigger relationships.
- Ruling: after a partial delete failure, refresh server rows and leave the confirmation open with its error — deletion cannot be rolled back locally.
- Playwright execution, screenshots, axe results and visual/manual QA are pending the parent's coordinated frontend-stable window. This worker did not start a browser suite while other workers edited the UI. Static-render unit tests do not constitute visual QA.
- No live provider/API, AWS, scheduler mutation, secret read, deployment or commit was performed.
