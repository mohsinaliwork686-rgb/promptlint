# promptlint

**A linter for LLM prompt templates.** It catches the class of bug that never shows up in
code review and always shows up in production.

[![ci](https://github.com/mohsinaliwork686-rgb/promptlint/actions/workflows/ci.yml/badge.svg)](https://github.com/mohsinaliwork686-rgb/promptlint/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)

---

## The problem

You paste a JSON example into a prompt template. Everything works, because nothing calls
`.format()` on that path yet. Three weeks later it does, and you get:

```
KeyError: '"category"'
```

Or subtler: you rename a variable at the call site and the template keeps the old name, so
one branch of your app silently ships `{tone}` to the model as literal text. Or someone drops
an API key into a system prompt that then gets logged by three different services.

None of this is caught by your type checker, your tests, or your reviewer. It is all caught
by reading the template with the same care `.format()` does — which is what this tool is.

## What it looks like

```console
$ promptlint examples
examples/agent.py:3:17: warning PL003 'tone' is supplied to this prompt but never appears in it
    hint: Either drop it at the call site, or you meant to reference it and forgot.
examples/agent.py:4:20: error PL004 OpenAI API key found in prompt text (sk-p...44 chars)
    hint: Prompts get logged, cached and sent to third parties. Read the credential from the
          environment and pass it as a header, never inside the prompt.
examples/agent.py:6:15: error PL002 template uses {max_words} but it is never supplied — KeyError at runtime
    hint: Supplied here: question, tone.
examples/classify.md:10:1: error PL001 '{"category": "<one of the above>", "c...' is not a valid placeholder
    hint: Literal braces (JSON examples, LaTeX, code blocks) must be doubled: '{{' and '}}'.
examples/classify.md:13:1: warning PL006 {user_input} holds untrusted input but is not delimited
    hint: Wrap it so the model can tell data from instructions, e.g.
          <untrusted_input>{user_input}</untrusted_input>.

Found 3 errors and 2 warnings in 3 files scanned. 1 fixable with --fix.
```

## Install

```bash
pip install promptlint          # zero runtime dependencies
pip install "promptlint[tokens]"  # optional: exact token counts via tiktoken
```

## Use

```bash
promptlint                        # lint the current directory
promptlint prompts/ src/agents/   # lint specific paths
promptlint --fix                  # apply the safe fixes
promptlint --format github        # annotations for GitHub Actions
promptlint --format json          # machine-readable, for your own tooling
promptlint --list-rules           # the rule reference
```

Exit code is `1` when anything at or above `--fail-on` (default `error`) is found, so it drops
straight into CI.

## Rules

| Code | Severity | Catches |
|------|----------|---------|
| `PL001` | error | Braces `.format()` will choke on — usually a literal JSON example |
| `PL002` | error | The template needs a variable the call site never supplies |
| `PL003` | warning | A variable is supplied but the template never uses it |
| `PL004` | error | A credential embedded in the prompt text |
| `PL005` | warning | The template is larger than the configured token budget |
| `PL006` | warning | Untrusted input concatenated straight into the instructions |
| `PL007` | warning | Trailing whitespace before the completion point |

A note on `PL006`: delimited interpolation is accepted — XML-ish tags, fenced blocks, quotes.
The rule fires on the bare concatenation that actually makes prompt injection easy, so it stays
quiet on prompts you have already thought about.

## Where it looks for prompts

| File type | What is treated as a prompt |
|-----------|-----------------------------|
| `.md` `.txt` `.jinja` `.j2` `.prompt` `.tmpl` | the whole file, minus optional front matter |
| `.yaml` `.yml` | string values under prompt-ish keys (`system`, `user`, `prompt`, `instructions`, …) |
| `.py` | string constants with prompt-ish names, plus every `.format()` call site |

In Python, the `.format()` call site is what makes `PL002`/`PL003` work — promptlint reads which
keyword arguments you actually pass and diffs them against the template:

```python
SYSTEM_PROMPT = """Answer {question} in under {max_words} words."""

SYSTEM_PROMPT.format(question=q, tone="formal")
#                                 ^^^^ PL003: supplied but unused
#                    PL002: {max_words} is never supplied
```

For standalone template files, declare the variables in front matter:

```markdown
---
name: ticket-classifier
variables: [categories, user_input, language]
---
Classify the ticket into one of: {categories}
```

## Configure

All optional. In your `pyproject.toml`:

```toml
[tool.promptlint]
token_budget = 4000
tokenizer = "cl100k_base"        # needs promptlint[tokens]; omit for the built-in estimate
ignore = ["PL003"]
fail_on = "error"                # error | warning | none
user_input_variables = ["payload", "ticket_body"]
```

## Pre-commit

```yaml
repos:
  - repo: https://github.com/mohsinaliwork686-rgb/promptlint
    rev: v0.1.0
    hooks:
      - id: promptlint
```

## GitHub Actions

```yaml
- run: pip install promptlint
- run: promptlint --format github
```

`--format github` emits workflow annotations, so problems appear inline on the diff.

## About `--fix`

`--fix` only applies changes that cannot change meaning: stripping trailing whitespace, and
doubling braces that `.format()` would reject anyway. Every fix re-checks that its original
text is still at the recorded position before writing, so a bad offset is skipped rather than
applied. Python sources are never rewritten.

## Non-goals

- **It does not call a model.** No API keys, no network, no cost. It is a static analyser.
- **It does not score prompt quality.** "Is this a good prompt" is not a linting problem.
- **It is not a template engine.** It reads `str.format` syntax, which is what Jinja and most
  prompt files look close enough to for these rules to hold.

## Development

```bash
git clone https://github.com/mohsinaliwork686-rgb/promptlint
cd promptlint
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

## License

MIT — see [LICENSE](LICENSE).
