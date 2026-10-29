# Judging procedure

This procedure is for judging, from the operational records of one study or operational trial (called "study" below; the files use the Japanese word 実験), whether that study demonstrated each of the 16 PLR-CMM capabilities. The judgment is based only on what is written in the records. Do not infer what the records do not say.

Two decisions from the Method section of the PLR-CMM paper (Section IV-A) are part of this procedure; see the end of this file.

## Input

- The study identifier (the name of its records folder) and name
- The organization's current level (from the overview sheet of the records, if there is one; L1 to L5, or none)
- The notes extracted from the records: for each file, facts, each with a verbatim quote
- The capability definitions (capabilities.md, 16 capabilities)
- The level definitions (levels.md)

## Steps

1. Read all the notes and write out, with the file names: the purpose of the study, what was done, the roles that took part (data subjects, primary users, secondary users, intermediaries), the data handled, how consent was obtained, whether a review took place, and the results.
2. Go through the 16 capabilities in order, C1-1 to C5-4. For each capability, look for whether the core practice of its definition is demonstrated as the purpose or the result of this study. Count only practices that the study set out to verify, or that it newly demonstrated as a result. Prerequisite steps carried out for the study (for example, a data catalog registered in an earlier study for another purpose, accounts already opened, a review already passed) are not counted as capabilities this study demonstrated. If the organization's current level is known, every capability at or below that level (for L3, C1-1 to C3-3) is a premise: do not judge it from the records, mark it premise, and do so even if the study verified it again, saying so in the reason. If the level is none, judge all 16 from the records.
3. When you find the core practice, give as evidence the file name and one or two quotes copied verbatim from the notes. Do not replace a quote with a summary.
4. From the evidence, choose one status for each capability:
   - achieved: the core practice of the definition was carried out in this study. Strict fulfillment of every element of the definition is not required (decision 2).
   - partial: the core practice was carried out only under specific conditions (for example, a fictitious application, members of the project only, dummy data), or only in part.
   - none: no passage in the records shows the core practice.
   - premise: the capability is at or below the organization's current level. No evidence is needed.
   Whether the capability was subsequently used in routine operation cannot be determined from the records of one study and is not judged here (decision 3). Do not lower achieved to partial because the records do not show routine use.
5. When in doubt, write which part of the definition the records meet and which part they do not, and then choose. If the practice is only a prerequisite of the study rather than its purpose or result, choose none. Between none and partial, choose none. Between partial and achieved, ask whether the core practice was carried out under the ordinary conditions of the study: if it was, choose achieved; if it was carried out only under specific conditions or only in part, choose partial. A single study usually demonstrates one to three capabilities, and at most about six.
6. From the capability judgments, name the Purpose-Driven Trust variables (Trustee, Purpose, Trust) that the study mainly supported, using the table in levels.md and the primary variable given with each capability.
7. Output in the fixed shape (the schema of judge.py). Do not attach achieved or partial to a capability without evidence. Attach premise only to capabilities at or below the organization's level.

Write the summary and the reasons in English. When a term of the records is used in the summary or a reason, translate it into English; the original may follow in parentheses. Copy quotes exactly as they appear in the notes, in their original language (the records are in Japanese).

## Do not

- Infer a capability from the name of the study or of its folder. Evidence is limited to the text of the records.
- Use the records of other studies. Each study is judged on its own.
- Copy personal names, contact details or individual responses into the output. If a quote contains them, replace that part with "(omitted)".

## Decisions taken from the Method section of the PLR-CMM paper (Section IV-A)

The paper states two decisions that are rules of this procedure.

1. (Step 4) "A capability is recognized if its core practice is documented in the operational records, without requiring strict fulfillment of each element in its definition."
2. (Step 4) "As the operational records of individual studies do not indicate whether the capabilities were subsequently used in routine operation, the determination of routine use relied on the firsthand operational knowledge of the co-authors overseeing each study." Routine use is therefore outside what this procedure judges.
