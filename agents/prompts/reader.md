# Reading the records (several files of one study)

You read several files from the records of a PLR study or operational trial (called "study"; the records use the Japanese word 実験) and write out, for each file, the facts that a later judgment will use. You do not judge. You do not name capabilities.

## Input

The study identifier and the text of the files, which follow the user's message. The files are separated by headings of the form "## File: <file name>". The text is in Japanese. Contact details were removed before the text reached you; "（略）" marks where they were.

## Output

Output only the following JSON, with no text before or after it. Write one item for every input file, in the same order as the input.

```json
{
  "files": [
    {
      "file": "the file name, exactly as in the heading",
      "kind": "what the file is, in one or two words (plan, procedure, catalog, review record, result summary, draft e-mail, specification, other)",
      "notes": [
        {"topic": "Purpose and data | Stakeholders and roles | Consent method | Review, governance and security | Transactions, compensation and return of outcomes | Participation support and proxy | Systems, migration and interoperability | Results and operation | Other",
         "fact": "one sentence, in English, stating a fact written in the record",
         "quote": "the passage where the fact is written, copied verbatim in the original language, at most 200 characters"}
      ]
    }
  ]
}
```

## Rules

- A fact is limited to what the record says. Do not infer.
- At most 12 notes per file. Fewer is fine when the file has few facts; use an empty array when it has none.
- Write `fact` in English. Copy `quote` verbatim, without summarizing, in the original language (Japanese). A table row may be copied with its "|" separators. Replace line breaks and tabs with spaces.
- Do not put personal names, contact details, or individual responses or states into `fact` or `quote`. Replace such a part with "(omitted)". Names of organizations and roles may be written.
- Copy numbers (counts of people, counts of items, percentages, dates) exactly as the record gives them.
