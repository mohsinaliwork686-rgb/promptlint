"""One test file per behaviour, grouped by rule."""

from __future__ import annotations

import pytest

from conftest import codes
from promptlint.config import Config
from promptlint.diagnostics import Severity


class TestPL001UnescapedBraces:
    def test_literal_json_is_flagged(self, check):
        found = check('Return {"category": "x"}')
        assert "PL001" in codes(found)
        assert found[0].severity is Severity.ERROR

    def test_fix_doubles_every_brace(self, check):
        (found,) = [d for d in check('Return {"a": 1}') if d.code == "PL001"]
        assert found.fix.new == '{{"a": 1}}'

    def test_unmatched_open_brace(self, check):
        assert "PL001" in codes(check("Hello {name"))

    def test_unmatched_close_brace(self, check):
        assert "PL001" in codes(check("Hello name}"))

    def test_escaped_braces_are_accepted(self, check):
        assert "PL001" not in codes(check('Return {{"a": 1}} for {name}'))

    def test_format_spec_is_not_a_violation(self, check):
        assert "PL001" not in codes(check("Score: {score:.2f} and {0!r}"))

    def test_fstring_skips_the_rule(self, check):
        assert "PL001" not in codes(check('Return {"a": 1}', kind="python-fstring"))


class TestPL002MissingVariable:
    def test_missing_variable_is_an_error(self, check):
        found = [d for d in check("Hi {name}", declared=[]) if d.code == "PL002"]
        assert found and found[0].severity is Severity.ERROR

    def test_supplied_variable_is_clean(self, check):
        assert "PL002" not in codes(check("Hi {name}", declared=["name"]))

    def test_attribute_access_uses_the_root_name(self, check):
        assert "PL002" not in codes(check("Hi {user.name}", declared=["user"]))

    def test_index_access_uses_the_root_name(self, check):
        assert "PL002" not in codes(check("Hi {items[0]}", declared=["items"]))

    def test_unknown_call_site_reports_nothing(self, check):
        assert "PL002" not in codes(check("Hi {name}", declared=None))

    def test_each_name_is_reported_once(self, check):
        found = [d for d in check("{a} {a} {a}", declared=[]) if d.code == "PL002"]
        assert len(found) == 1


class TestPL003UnusedVariable:
    def test_unused_variable_warns(self, check):
        found = [d for d in check("Hi {name}", declared=["name", "tone"]) if d.code == "PL003"]
        assert len(found) == 1
        assert "tone" in found[0].message

    def test_all_used_is_clean(self, check):
        assert "PL003" not in codes(check("Hi {name}", declared=["name"]))


class TestPL004HardcodedSecret:
    @pytest.mark.parametrize(
        "secret",
        [
            "sk-ant-api03-" + "a" * 40,
            "sk-proj-" + "b" * 40,
            "ghp_" + "c" * 36,
            "AKIA" + "D" * 16,
            "AIza" + "e" * 35,
            "xoxb-1234567890-abcdefghij",
        ],
    )
    def test_known_key_shapes_are_caught(self, check, secret):
        assert "PL004" in codes(check(f"Use the key {secret} when calling tools."))

    def test_generic_assignment_is_caught(self, check):
        assert "PL004" in codes(check("api_key = 9f8e7d6c5b4a39281706"))

    @pytest.mark.parametrize(
        "value", ["YOUR_API_KEY_HERE", "xxxxxxxxxxxxxxxxxx", "sk-test-aaaaaaaaaaaaaaaaaaaa"]
    )
    def test_obvious_placeholders_are_ignored(self, check, value):
        assert "PL004" not in codes(check(f"api_key = {value}"))

    def test_the_secret_is_redacted_in_the_message(self, check):
        (found,) = [d for d in check("access_token: " + "z" * 40) if d.code == "PL004"]
        assert "z" * 40 not in found.message
        assert "40 chars" in found.message

    def test_bare_token_word_is_not_flagged(self, check):
        """'token' alone is too common in prompts about token budgets."""
        assert "PL004" not in codes(check("Keep the response under the token limit of 4096"))


class TestPL005TokenBudget:
    def test_over_budget_warns(self, check):
        assert "PL005" in codes(check("word " * 200, cfg=Config(token_budget=10)))

    def test_under_budget_is_clean(self, check):
        assert "PL005" not in codes(check("short prompt", cfg=Config(token_budget=1000)))

    def test_zero_budget_disables_the_rule(self, check):
        assert "PL005" not in codes(check("word " * 200, cfg=Config(token_budget=0)))


class TestPL006UndelimitedUserInput:
    def test_bare_interpolation_warns(self, check):
        assert "PL006" in codes(check("Answer this: {user_input}"))

    def test_xml_tags_count_as_delimiters(self, check):
        assert "PL006" not in codes(check("<user_input>\n{user_input}\n</user_input>"))

    def test_fenced_block_counts_as_delimiter(self, check):
        assert "PL006" not in codes(check("```\n{document}\n```"))

    def test_quotes_count_as_delimiters(self, check):
        assert "PL006" not in codes(check('The question was "{question}" - answer it.'))

    def test_non_user_variables_are_ignored(self, check):
        assert "PL006" not in codes(check("Use tone {tone} and style {style}"))

    def test_suffix_convention_is_recognised(self, check):
        assert "PL006" in codes(check("Reply to {customer_message}"))

    def test_custom_variable_names_from_config(self, check):
        cfg = Config(user_input_variables=("payload",))
        assert "PL006" in codes(check("Handle {payload}", cfg=cfg))


class TestPL007TrailingWhitespace:
    def test_end_of_prompt_whitespace_warns(self, check):
        found = [d for d in check("Answer now: ") if d.code == "PL007"]
        assert found and "ends with" in found[0].message

    def test_mid_prompt_line_is_reported(self, check):
        found = [d for d in check("one  \ntwo") if d.code == "PL007"]
        assert len(found) == 1

    def test_clean_text_is_clean(self, check):
        assert "PL007" not in codes(check("one\ntwo"))

    def test_python_sources_are_not_auto_fixable(self, check):
        found = [d for d in check("one  \ntwo", kind="python-str") if d.code == "PL007"]
        assert found and not found[0].fixable


class TestSelection:
    def test_ignore_disables_a_rule(self, check):
        assert "PL001" not in codes(check("Hi {name", cfg=Config(ignore=("PL001",))))

    def test_select_restricts_to_listed_rules(self, check):
        found = check("Hi {name}  ", cfg=Config(select=("PL007",)))
        assert set(codes(found)) == {"PL007"}
