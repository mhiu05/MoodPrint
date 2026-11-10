-- Cover composite owner FKs for cascades and case/conversation history reads.
create index agent_runs_conversation_owner on app.agent_runs(conversation_id,owner_id);
create index messages_conversation_owner on app.messages(conversation_id,owner_id);
create index tool_approvals_run_owner on app.tool_approvals(run_id,owner_id);
