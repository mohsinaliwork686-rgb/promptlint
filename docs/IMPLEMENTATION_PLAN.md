# Implementation plan — promptlint

> Written before the build, kept as the record of what was decided and why.
> Week 1 of the 10-week programme.

## 1. Problem

Prompt templates are strings, so nothing checks them. The bugs they carry are real:

- A JSON example pasted into a template makes `.format()` raise `KeyError: '"category"'`
  the first time that code path runs, which is usually in production.
- A variable renamed at the call site leaves the template referencing the old name, so the
  model silently receives the literal text `{tone}`.
- An API key dropped into a system prompt gets logged by every service the prompt passes through.
- Trailing whitespace before the generation point changes tokenization and degrades output.

Type checkers do not see inside strings. Tests only cover the paths they exercise. Reviewers
skim prompts. A static analyser that reads the template the way `.format()` does closes the gap.

## 2. Non-goals

Stated up front so scope cannot creep:

- **No model calls.** No API keys, no network, no cost. Static analysis only.
- **No prompt quality scoring.** "Is this a good prompt" is not a linting problem.
- **Not a template engine.** We read `str.format` syntax, which Jinja and most prompt files
  are close enough to for these rules to hold.
- **No IDE plugins** in v0.1.

## 3. Surface

The thing a user actually touches. Designed first, because if this is awkward the rest does not matter.

```bash
promptlint                     # lint the current directory
promptlint prompts/ src/       # lint specific paths
promptlint --fix               # apply the safe fixes
promptlint --format github     # annotations for CI
promptlint --format json       # for other tooling
promptlint --list-rules        # rule reference
```

Exit `1` when anything at or above `--fail-on` (default `error`) is found, so it drops into CI
with no wrapper script. Config is optional and lives in `[tool.promptlint]` in `pyproject.toml`.

## 4. Architecture

Four layers, each independently testable. The key decision is that **extraction is separate from
rules**: rules never parse files, they only see a `PromptSource`. That is what lets one rule set
cover Markdown, YAML and Python.

```
  files on disk
        |
        v
  sources.py        discovery + extraction -> PromptSource
        |                 (text / yaml / python AST)
        v
  placeholders.py   one brace scanner shared by three rules
        |
        v
  rules/*.py        PL001..PL007, each yields Diagnostic
        |
        +--> fixer.py       applies Diagnostic.fix, position-verified
        |
        v
  reporters.py      text / json / github
        |
        v
  cli.py            argparse, config merge, exit codes
```

| Module | Responsibility |
|--------|----------------|
| `sources.py` | Find files, pull prompts out of them, keep exact positions |
| `placeholders.py` | Scan `{...}` spans once; PL001/PL002/PL003/PL006 all reuse it |
| `config.py` | Read `[tool.promptlint]`, merge with CLI flags |
| `tokens.py` | Token count: tiktoken if installed, heuristic otherwise |
| `diagnostics.py` | `Diagnostic` and `Fix` records |
| `rules/` | One file per concern, self-registering |
| `linter.py` | Run enabled rules over every extracted prompt |
| `fixer.py` | Apply fixes, right to left, verifying the anchor text |
| `reporters.py` | Render diagnostics in three formats |
| `cli.py` | Entry point |

### The position problem

The hard part. A diagnostic is worthless if it points at the wrong line. A prompt's text does not
start at the top of its file — it sits after front matter, or inside a YAML block scalar with its
own indentation, or inside a Python triple-quoted string.

So `PromptSource` carries `line_offset`, `col_offset` and `body_indent`, and exposes
`position(offset) -> (line, column)` that maps any offset in the prompt back to the file. Rules
report offsets; they never think about files. When a source cannot map reliably — a single-line
Python string containing `\n` escapes — it sets `maps_lines = False` and every diagnostic anchors
to the literal's own line rather than lying about a position.

### Why no dependencies

A linter that is annoying to install does not get installed. Everything needed is in the standard
library: `ast` for Python, `tomllib` for config, a hand-rolled line scanner for YAML. That scanner
is actually *better* than a real YAML parser here, because parsers throw away line numbers and line
numbers are the whole point. tiktoken stays an optional extra for exact token counts.

## 5. Rules

| Code | Severity | Catches | Fixable |
|------|----------|---------|---------|
| `PL001` | error | Braces `.format()` will reject — usually a literal JSON example | yes |
| `PL002` | error | Template needs a variable the call site never supplies | no |
| `PL003` | warning | Variable supplied but never used | no |
| `PL004` | error | Credential embedded in prompt text | no |
| `PL005` | warning | Template over the token budget | no |
| `PL006` | warning | Untrusted input concatenated into instructions | no |
| `PL007` | warning | Trailing whitespace before the completion point | yes |

PL002 and PL003 need to know what the call site supplies. In Python that comes free from the AST:
read the keyword arguments of `.format()` and diff them against the template. If the call uses
`**kwargs` we cannot know, so both rules stay silent rather than guess. In standalone template
files the variables come from front matter.

PL006 accepts delimited interpolation — XML-ish tags, fenced blocks, quotes. It fires only on bare
concatenation, which is the pattern that actually makes injection easy. A rule that fires on
prompts you already thought about gets switched off, and then it catches nothing.

## 6. Autofix safety

`--fix` may only apply changes that cannot change meaning: stripping trailing whitespace, and
doubling braces that `.format()` would reject anyway.

Every `Fix` records `(line, column, old, new)`. Before writing, the fixer re-reads that position
and compares against `old`. If it does not match, the fix is skipped, not forced. Fixes apply right
to left and bottom to top so earlier offsets stay valid. Python sources are never rewritten —
the position mapping there is good enough to report on, not good enough to edit.

## 7. Build order

| Day | Work |
|-----|------|
| Mon | This plan. Decide the rule set and the CLI surface. Write the README pitch. |
| Tue | `diagnostics.py`, `sources.py`, `config.py`, `tokens.py`. Extraction is the foundation. |
| Wed | `placeholders.py` and all seven rules. |
| Thu | `linter.py`, `fixer.py`, `reporters.py`, `cli.py`. Then the test suite. |
| Fri | CI, README, examples, publish. |

## 8. Test plan

Tests are grouped by behaviour, not by file. The cases that matter for a linter are the ones where
it must stay *quiet* — a noisy linter gets disabled.

| Area | Must catch | Must stay quiet on |
|------|------------|--------------------|
| Extraction | front matter, YAML block scalars, `.format()` call sites, f-strings | vendor dirs, non-prompt strings, unparseable files |
| PL001 | literal JSON, unmatched `{`, unmatched `}` | `{{escaped}}`, format specs `{x:.2f}`, conversions `{0!r}`, f-strings |
| PL002/003 | missing name, unused name | `{user.name}` and `{items[0]}` roots, `**kwargs` call sites, repeats reported once |
| PL004 | six real key shapes, generic assignments | `YOUR_API_KEY_HERE`, `xxxx…`, the bare word "token" |
| PL005 | over budget | under budget, budget of 0 disables |
| PL006 | bare `{user_input}`, `_message` suffix convention, configured names | XML tags, fences, quotes, non-user variables |
| PL007 | end-of-prompt, mid-prompt | clean text; Python sources not marked fixable |
| Fixer | strips whitespace, escapes braces, right-to-left on one line | skips when the anchor moved, never touches `.py`, idempotent |
| CLI | exit codes, all three formats, `--fix`, `--select`/`--ignore`, config | — |

Target: every rule has at least one positive and one negative case, and the fixer has an explicit
test proving a stale position is skipped rather than applied.

## 9. Risks

| Risk | Mitigation |
|------|------------|
| False positives make people disable it | Every rule has explicit "stays quiet" tests; PL004 has a placeholder denylist |
| Position mapping is wrong and diagnostics lie | `maps_lines = False` when we cannot map; fixes verify their anchor before writing |
| The YAML line scanner mishandles real files | Restricted to prompt-ish keys and block scalars; anything unrecognised is skipped, not guessed |
| Heuristic token count misleads | Output marks estimates with `~` and points at `promptlint[tokens]` |

## 10. Definition of done

- [x] Public repo, README with problem, usage, rule reference, configuration, non-goals
- [x] MIT licence, repo description and topics
- [x] Zero runtime dependencies, installs and runs on a clean machine
- [x] Test suite covering every rule both ways
- [x] CI green: tests on 3 OSes x 3 Python versions, ruff, and a dogfood run
- [x] Commits tell the build story, one logical change each
