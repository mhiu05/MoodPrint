# AI validation coverage and gaps

- Unit/transport:exact input fields include instructions,history,tools,output schema;expansion rejected before
generation;bad count/model/output/hosted tools/stateful fields fail closed;zero prod budget denied.
- PostgreSQL:concurrent legacy20/50 budgets,bounded50parents+100children,unknown/cancel/crash retention,
guest detached liability,old uncertain child cascade,SET LOCAL lock deadline and pool cleanup.
- SDK/workflows:existingV3/collaboration/group/journal/guest tests are regression evidence only;large mixed
50-parent fanout/background soak not yet implemented in new harness.
- Streaming:joined running poll6queries vs9baseline,existing48history/recovery/event tests;ASGI SSE is not50
TCP/TLS/Caddy network streams. Slow-reader real-network/global-lifetime soak remains open.
- Load:legacyT4 fails25/50 by budget;boundedburst50/50peak,parent50/SSE50/provider48 in earlier profile;
known-usage15minute attempt hit localSQLAlchemy pool timeout. Keep failed artifacts,do not claimPASS.
- T5:0calls/no judge;quota/pricing/campaign guard incomplete. No realprovider capacity or quality claims.
- T6/T7/T8:full mixed/background/chaos not validated by burst/unit tests;must remain open.
- No production authorization/deployment/hosted load. Container resource sizing/credits under workload unknown.
