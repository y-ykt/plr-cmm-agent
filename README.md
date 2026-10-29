<!-- © 2026 The University of Osaka -->

# plr-cmm-agent

A tool that runs the PLR-CMM assessment on an organization's own operational records. PLR-CMM (the capability maturity model of the Personal Life Records paper) defines 16 capabilities at five levels; this tool reads the records of one study or operational trial, judges which of the 16 capabilities that study demonstrated, and reports the judgment with the evidence for each capability, in a form that gives the same result whoever runs it. The construction follows Paper2Agent (Miao et al., Nature, 2026, doi:10.1038/s41586-026-11044-y), applied to an assessment procedure that has no code: what is fixed is the procedure, the definitions, the output shape and the checks around the judgment, while the judgment itself is made by a large language model.

## What it does

The assessment runs in three stages.

1. Reading. The text of each record file is read, and for each file the agent writes notes: facts, each with a verbatim quote (at most 12 notes per file, quotes at most 200 characters). No judgment is made at this stage.
2. Judging. For one study at a time, the agent receives the procedure (`resources/procedure.md`), the capability definitions (`resources/capabilities.md`), the level table (`resources/levels.md`) and the notes of that study, and submits a judgment for all 16 capabilities (achieved, partial, none, or premise), each with evidence (file name and quote) and a reason. The submission is validated against a fixed schema and rejected if it does not fit.
3. Reporting. The accepted judgment is rendered as one row of the capability table of the paper (study, period, capability IDs, with parentheses for partial) followed by the evidence and the reason for each capability, so that a person can check every entry against the records.

The judging procedure follows the decisions stated in the Method section of the paper: a capability is recognized when its core practice is documented in the records, without requiring every element of its definition; whether a capability later entered routine operation is not judged from the records of one study; and a practice that is only a prerequisite of the study is not counted as a capability the study demonstrated.

## Layout

```
config.yaml            where the input records are, the rules for records that are not used, and the vocabularies of the notes (topics) and of a judgment (capability IDs, statuses, levels, variables)
resources/
  levels.md            level definitions (Table I of the paper, verbatim)
  capabilities.md      the 16 capability definitions (Section III of the paper, verbatim)
  procedure.md         the judging procedure
  record_template.md   the overview sheet to put in the records of a new study
plr_cmm_mcp/
  ids.py               the study identifier: the name of the records folder, checked before it is used in a path
  inventory.py         inventory of the records: decides by file name only what is used; never opens a file
  extract.py           extracts text from docx, pptx, xlsx, pdf and txt, and masks contact details
  notes.py             the shape and validation of the notes written per file (the topics come from config.yaml)
  config.py            where the repository and config.yaml are, and how config.yaml is read
  judge.py             the shape and validation of a judgment (the vocabulary comes from config.yaml)
  server.py            the MCP server (Model Context Protocol): 15 tools, 3 resources, 3 prompts
agents/
  prompts/             the instructions for the three stages: ingest.md and reader.md (reading), judge.md (judging), report.md (reporting)
  orchestrator.py      runs the reading and judging stages over many studies, through Claude Code (claude -p) or the Claude API
  api_backend.py       the Claude API path of the orchestrator: one request per reading batch; the plr-cmm tools run in-process for judging
tests/                 pytest, with fabricated files only
work/                  extracted text (not in the repository)
```

## Input and personal data

The input is an organization's operational records of its studies, one folder per study, under the experiments folder named in `config.yaml` (`experiments_dir`) or elsewhere under `input_root`. The records are not in this repository; set `input_root` in `config.yaml` to the folder that holds them (the published file carries a placeholder). A study is named by its folder, and the folder's name is the study's identifier: the extracted text, the notes and the judgment are kept under that name (`work/text/<name>/`, `runs/<run>/notes/<name>/`, `runs/<run>/judgments/<name>.json`), so the names of the study folders must be unique. No numbering is required. Personal data are not handled: records are excluded by folder and file name before any file is opened (the rules are in `config.yaml` and are applied by `inventory.py`; in the authors' use they exclude per-participant records), e-mail addresses and telephone numbers in the extracted text are masked, and the notes and judgments are rejected if they contain such patterns.

## Requirements

Python 3.14, the packages in `requirements.txt` (including `mcp`), and Claude Code for running the agents. For batch runs the model is set by `llm.model` in `config.yaml` or the environment variable `PLR_CMM_MODEL` (default `claude-opus-5-5`) and is recorded in `runs/<run>/calls.jsonl`; for interactive use it is the model of the Claude Code session.

## Judging one study interactively

Connect the MCP server `plr-cmm` to an MCP client such as Claude Code. When it connects, the server hands the client its usage guidance (`agents/prompts/instructions.md`), so the three stages can be asked for in plain words, naming the study by its records folder; no tool or command name needs to be typed:

- "Read the records of study <folder>" (Reading: the inventory is shown for approval before any file is opened, then extraction and notes per file)
- "Judge study <folder>" (Judging: the judgment of the 16 capabilities, validated, then shown as the report)
- "Show the judgment of study <folder>" (Reporting: the accepted judgment, at any later time)

`<folder>` is the study's records folder: its name when it lies in the experiments folder, or its path. The identifier that `inventory_experiment` returns (the folder name) is what the later requests take.

The same three stages are also available as the server's prompts, which Claude Code exposes as slash commands: `/mcp__plr-cmm__ingest_experiment <folder>`, `/mcp__plr-cmm__judge_experiment <folder>`, `/mcp__plr-cmm__report_experiment <folder>`.

The interactive agent itself does the work with the server's tools: in the reading stage it shows the result of `inventory_experiment` and waits for approval, then uses `extract_experiment`, `list_texts`, `get_text` (one file at a time) and `submit_notes`; in the judging stage it reads the procedure, the definitions, the notes and the premises, submits through `submit_judgment`, and ends by showing the report from `render_judgment`: the row of the capability table and the evidence and reason for each capability.

Put an overview sheet in the shape of `resources/record_template.md` in the study's plan folder. The reading step then misses less, and `render_judgment` fills in the name and period. The sheet also states the organization's current level, the highest level whose capabilities the organization all uses in routine operation. Capabilities at or below that level are returned by `get_premise` as premises and are marked premise instead of being judged from the records, because the records of a later study do not repeat the practices the organization already has. Only the capabilities above the level are judged, and `submit_judgment` rejects a judgment in which a premise capability has another status. The level belongs to the organization: never write another organization's level on an organization's records. An organization with no history writes "none", and all 16 capabilities are judged.

## Judging many studies in a batch

```
.venv/bin/python -m pytest -q
.venv/bin/python -m plr_cmm_mcp.inventory --config config.yaml --out work/inventory.json --names
.venv/bin/python -m plr_cmm_mcp.extract   --config config.yaml
.venv/bin/python -m agents.orchestrator read  --run r1 --experiments <folder> <folder> ...
.venv/bin/python -m agents.orchestrator judge --run r1 --experiments <folder> <folder> ...
```

Check the inventory before extracting text. The extraction step writes the text of every study under the experiments folder to `work/text/<identifier>/`. `--experiments` takes the identifiers (the names of the study folders) or the paths of those folders. The reading stage writes the notes under `runs/<run>/notes`, the judging stage writes the accepted judgments under `runs/<run>/judgments`, and `render_judgment` reports any of them. A judging run can reuse the notes of another run with `--notes-from`.

The orchestrator calls the model in one of two ways, chosen by the `llm` section of `config.yaml`:

- `api_key` empty (the published file): the Claude Code command `claude -p`. The judging stage attaches the plr-cmm MCP server as a separate process (`runs/<run>/mcp.json`).
- `api_key` set: the Claude API through the python package `anthropic`. The reading stage sends one request per batch; the judging stage gives the model the eight plr-cmm tools that `agents/prompts/judge.md` names, taken from the MCP server's own definitions, and runs them in the same process. `effort` sets the depth of the model's reasoning, `fallbacks` lets a request the model declines run on a fallback model, and `prices` (USD per million tokens) fills the cost column of `runs/<run>/calls.jsonl`, which the API does not return; without it the cost is recorded as 0. `PLR_CMM_MODEL` overrides `model` in both ways.

Do not commit a key: keep a `config.yaml` that holds one outside the repository and point `PLR_CMM_CONFIG` at it. In both ways the extracted text of the records is sent to Anthropic's API; the same records go to the same place when `claude -p` is used.

## Limitations

- The judgment is made by a large language model. Repeated runs with the same input can differ, and the results depend on the model and its version (recorded in `runs/<run>/calls.jsonl` for batch runs; not recorded for interactive use). Run the judging stage more than once if the variation matters, and for interactive use do so in separate sessions: within one session the earlier judgment stays in the context, and a second judgment of the same study came out the same.
- Not all records are read. Files are excluded before any file is opened, by folder and file name, according to the rules in `config.yaml` (in the authors' use, per-participant records and questionnaire answers), so evidence that exists only in excluded files is absent from the input. Only the file types listed in `config.yaml` are read, and the extracted text of a file is cut at 120,000 characters (20,000 cells per sheet); cuts are recorded in `work/extract_log.json`. Reading is done once, and each file contributes at most 12 notes, so facts in long files can be left out.
- The records of the PLR studies are in Japanese and the procedure, definitions and instructions are in English. Quotes are copied verbatim, so the evidence can be checked against the records, but the agent's facts and reasons are its own English rendering.
- The organization's current level, used to mark lower-level capabilities as premises for a new study, is declared by the organization on the overview sheet and is not verified from the records.

## Citing

The tool accompanies the PLR-CMM paper, which is under review. [The citation of the paper and the permanent location of this repository will be added here.]

## Use of generative AI

- The code, the instructions in `agents/prompts/` and the documents in this repository were written with the assistance of Claude Code (Anthropic). The authors reviewed them, ran the tests and are responsible for their content. The definitions in `resources/levels.md` and `resources/capabilities.md` are the paper's own wording, written by the authors.
- What the tool produces is generated by a large language model: the notes of the reading stage (facts in the model's words; quotes copied verbatim from the records) and the judgments (status, evidence and reason for each capability). In batch runs, the orchestrator records the backend, the model and the token usage of every call in `runs/<run>/calls.jsonl`. In interactive use through Claude Code, the model is the one the Claude Code session uses, and this tool does not record it.

## License

This repository is released under the MIT License. See `LICENSE`.

---

© 2026 The University of Osaka
