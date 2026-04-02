# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

104 resume automation system for HR talent screening at EPC engineering companies (e.g. CTCI/中鼎集團). The system filters MEP/facilities/construction engineering candidates from 104 job portal data, converts PDF resumes to structured CSV, and iteratively refines screening rules based on HR feedback.

## Business Flow

```
ANALYSIS.md (104 candidate summaries, hundreds of people)
    ↓
/filter → Three-stage cleaning + M/N/E rule scoring → Candidate shortlist
    ↓
HR downloads selected candidates' PDF resumes from 104
    ↓
/merge → PDF → Markdown → HR_Data_Summary.csv (8 structured fields)
    ↓
/improve → Refine screening rules using confirmed selections + HR feedback
    ↓
Next /filter is more accurate
```

## Critical Gotchas

1. **Windows cp950 encoding**: All Python scripts that print Chinese must set `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` or crash with `UnicodeEncodeError`.
2. **MarkItDown Kangxi radicals**: PDF→MD produces variant characters (e.g. `⼯` vs `工`) and `\x0c` page breaks. Scripts use `unicodedata.normalize('NFKC')` — never skip.
3. **File rename idempotency**: `extract_hr_data.py` adds `{seq}_` prefix. Re-running detects existing prefix and skips. But `convert_pdfs.py` may regenerate .md under old names — always re-run both together.
4. **CSV white-list filter**: Only processes .md with matching .pdf. Auto-excludes CLAUDE.md, GEMINI.md etc.
5. **screening_rules.md vs screen_candidates.py**: Both must stay in sync. Changing rules doc alone won't affect scoring — must also update the Python keyword arrays.

## Commands

All scripts must use the embedded Python (forward slashes for bash):
```
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe"
```

### /filter (hr-talent-screener)
```bash
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/pipeline_clean.py ANALYSIS.md
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-talent-screener/scripts/screen_candidates.py ANALYSIS.md
```

### /merge (hr-resume-parser)
```bash
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-resume-parser/scripts/convert_pdfs.py
"c:/Users/01102088/Desktop/python-3.14.2-embed-amd64/python.exe" .agent/skills/hr-resume-parser/scripts/extract_hr_data.py
```

### /improve
Manual process: analyze HR feedback (missed/wrong selections), update `screening_rules.md` + `screen_candidates.py`, append to `iteration_log.md` + `historical_selections.csv`.

## Architecture

### Skill 1: hr-talent-screener
- **SKILL.md**: `.agent/skills/hr-talent-screener/SKILL.md`
- **Scripts**:
  - `pipeline_clean.py` — Stage 1: noise removal, Stage 2: dedup by candidate code, Stage 3: education-based classification (Civil/MEP/Other)
  - `screen_candidates.py` — Scoring engine with two-tier M1 keywords, M2 industry match, M3 experience count, N1-N16 bonus, E1-E3 exclusion. Threshold = 20.
  - `pick_candidates_util.py` — Utility helper
- **References** (in `references/`):
  - `screening_rules.md` — Cross-batch rule corpus (M/N/E conditions, keywords, heuristics). Only file for rules.
  - `iteration_log.md` — Append-only batch history. Never delete entries.
  - `historical_selections.csv` — Cumulative selection records across batches. Only append.
  - `clear_RULE.md` — Three-stage cleaning specification.

### Skill 2: hr-resume-parser
- **SKILL.md**: `.agent/skills/hr-resume-parser/SKILL.md`
- **Scripts**:
  - `convert_pdfs.py` — PDF to Markdown via MarkItDown library
  - `extract_hr_data.py` — Markdown field extraction with NFKC Unicode normalization (handles Kangxi radicals, `\x0c` page breaks). White-list filter (only processes .md with matching .pdf). Adds 3-digit serial numbers. Renames PDF/MD files with sequence prefix. Auto-QA 15 samples + rename verification.
- **8 CSV fields**: 序號, 姓名, 年紀, 語文能力, 學歷, 近期工作, 近期工作內容, 總年資, 前二次任職公司
- **QAQC**: Script auto-checks 15 samples, then Agent must manually verify 15 more against original PDFs (not .md).

## Screening Rule Structure

M1 uses **two-tier keywords** (core +10 pts vs generic +3 pts). Score threshold = 20. Candidates need meaningful domain evidence, not just a generic title like "工程師". Full keyword lists and M/N/E conditions are defined in `screening_rules.md` and `screen_candidates.py` — always refer to those as the single source of truth.

## Authoritative Documents

**GEMINI.md is the execution rulebook** — it supersedes any conflicting guidance. When in doubt, defer to GEMINI.md for execution discipline and SKILL.md files for skill-specific SOP.

## Execution Discipline (from GEMINI.md)

1. **Anti-Improvisation**: Only use scripts defined in SKILL.md. Never create temporary scripts.
2. **Halt on Error**: Any Traceback → stop immediately, report raw error to user, await instruction.
3. **Strict Python Path**: Only the embedded Python above. Never use system Python.
4. **File Ecosystem**:
   - `HR_Data_Summary.csv` in root = current batch only (overwritten each run)
   - `references/historical_selections.csv` = cumulative history (append only)
   - `references/iteration_log.md` = batch log (append only, never delete)
   - Keep project root clean — no temp files
5. **Single Source of Scripts**: Modify official scripts in `scripts/` if logic changes needed. Never create new scripts elsewhere.
6. **Three-stage cleaning is mandatory**: Even if user says "skip cleaning", always run pipeline_clean.py first.
7. **Candidate code is unique ID**: Never deduplicate by name — same name may be different people.

## Key Screening Heuristics (from 3 batches of learning)

- **Ability > Education**: 33%+ of selected candidates have non-matching degrees. A junior-high graduate with 15 years as MEP supervisor qualifies.
- **No age limit**: Historical selections range 20-70 years old. 40-49 is the largest group (36%).
- **Experience sweet spot**: 6-20 years covers 68% of selections.
- **Construction vs Manufacturing**: Being an "engineer" at a semiconductor fab (manufacturing/process role) is different from construction MEP. The system distinguishes these.
- **Construction site management**: Site supervisors (監工/主任/襄理) from construction companies are a key talent pool regardless of education level.
- **Quality/Procurement/Energy roles** are in scope — not just pure technical positions.

