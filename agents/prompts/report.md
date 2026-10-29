# Reporting the judgment of one study

Show the user the accepted judgment of one PLR study or operational trial (called "study"; the records use the Japanese word 実験).

Use the `plr-cmm` tool `render_judgment` with the study identifier (the name of its records folder) and show the user exactly what it returns: the organization and the level taken as premise, the row of the capability table (study, period, capability IDs with parentheses for partial, PDT variable), the summary, and the evidence and reason for each capability. Add nothing and leave nothing out. If it says there is no accepted judgment, tell the user that the study has not been judged yet and that the next step is `/mcp__plr-cmm__judge_experiment <folder>` (after `/mcp__plr-cmm__ingest_experiment <folder>` if the notes do not exist yet).

The study (its identifier) is in the user's message.
