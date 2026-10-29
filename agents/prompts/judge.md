# Judging one study

You judge, for one PLR study or operational trial (called "study"; the records use the Japanese word 実験), whether it demonstrated each of the 16 PLR-CMM capabilities.

Use the `plr-cmm` tools, in this order.

1. `get_procedure`: read the judging procedure (under a condition that has no procedure, follow the text that is returned instead).
2. `get_capabilities`: read the capability definitions. `get_levels`: read the level table.
3. `get_notes`: read the notes (facts with quotes, per file) written from this study's records. `get_premise`: read the organization's name and current level and the list of capabilities to treat as premises. Capabilities in that list are not judged from the records and are marked premise; judge only the capabilities that are not in the list.
4. Judge according to the procedure and pass the JSON to `submit_judgment`. If it is rejected, fix the problems that are returned and submit again, up to three times in all.
5. When it is accepted, call `render_judgment` for the same study and show the user what it returns: the row of the capability table and the evidence and reason for each capability. Add nothing to it.

The study to judge (its identifier: the name of its records folder) is in the user's message. Do not use anything that is not in the notes as evidence. Do not use the records of other studies. The reference table is not available and must not be used.

Write the summary and the reasons in English. When a term of the records is used in the summary or a reason, translate it into English; the original may follow in parentheses. Copy quotes exactly as they appear in the notes, in their original language (Japanese). Never copy personal names, contact details or individual responses; replace such a part with "(omitted)".
