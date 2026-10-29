# Ingesting the records of a new study (inventory, extraction, reading)

You ingest the records of one PLR study or operational trial (called "study"; the records use the Japanese word 実験) and write out, for each file, the facts that a later judgment will use. You do not judge. You do not name capabilities.

Use the `plr-cmm` tools, in this order.

1. Pass the study's records folder (its name, or its path) to `inventory_experiment`. The result gives the study identifier (the folder name), which every later call takes, and the list of files to use and files to exclude. Show the user the names of the files to use, with the number of excluded files and the reasons, and ask whether to go on to extraction. Do not open any file before the user approves.
2. After approval, extract the text with `extract_experiment`. Show the user the result (the state and the number of characters of each file). If any file is in the state error, name it.
3. Get the list of extracted files with `list_texts`. If there is a file whose name contains "overview" or "概要" (the overview sheet; see resources/record_template.md), handle it first. Then handle, one at a time, each file whose notes are not done (notes_done is false).
4. For each file, read the text with `get_text`. If the result says "continued", advance offset and read to the end. When you have read it all, write the notes by the rules below and pass them to `submit_notes` in the shape given by `notes_schema`. If they are rejected, fix the problems that are returned and submit again, up to three times in all. If they are still rejected after three tries, skip the file and keep its name.
5. When all files are handled, report to the user the number of files, the number of notes, and the names of any skipped files. If there was no overview sheet, say that the next study should have one (the template). Judging is done under a separate instruction, not here: tell the user that the next step is `/mcp__plr-cmm__judge_experiment <folder>`.

The study to ingest (its records folder) is in the user's message. Do not use the records of other studies. Do not write anything the records do not say.

## How to write the notes

The notes for one file are one JSON object with `experiment` (the study identifier, exactly as `inventory_experiment` returned it), `file` (the file name exactly as `list_texts` returned it, including .txt), `kind` (what the file is, in one or two words: plan, procedure, catalog, review record, result summary, draft e-mail, specification, other) and `notes`. Each item of `notes` has `topic`, `fact` and `quote`.

- `topic` is one of: Purpose and data, Stakeholders and roles, Consent method, Review, governance and security, Transactions, compensation and return of outcomes, Participation support and proxy, Systems, migration and interoperability, Results and operation, Other
- `fact` is one sentence, in English, stating a fact written in the record
- `quote` is the passage where the fact is written, copied verbatim in the original language (Japanese), at most 200 characters
- Do not put personal names, contact details, or individual responses or states into `fact` or `quote`. Replace such a part with "(omitted)". Names of organizations and roles may be written.
