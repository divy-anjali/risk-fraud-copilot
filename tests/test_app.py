"""Headless app tests (streamlit.testing.v1.AppTest) of all four pages.

Runs cloud/app.py - the public Community Cloud entrypoint - with the key-pair
secrets when they exist, otherwise streamlit_app.py on the named connection.
"""
import tomllib

import pytest
from streamlit.testing.v1 import AppTest

from conftest import ROOT, SECRETS

HOSTED = SECRETS.exists()
ENTRYPOINT = ROOT / ("cloud/app.py" if HOSTED else "streamlit_app.py")
PAGES = ["overview", "copilot", "customer360", "report"]


def launch(page=None):
    at = AppTest.from_file(str(ENTRYPOINT), default_timeout=900)
    if HOSTED:
        at.secrets["snowflake"] = tomllib.loads(SECRETS.read_text(encoding="utf-8"))["snowflake"]
    at.run()
    if page:
        at.button(key=f"open_{page}").click().run()
        assert at.session_state["page"] == page
    return at


def assert_clean(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_landing_page_offers_every_page():
    at = launch()
    assert_clean(at)
    keys = {b.key for b in at.button}
    assert {f"open_{p}" for p in PAGES} <= keys


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_errors(page):
    assert_clean(launch(page))


def test_customer360_handles_customer_with_no_transactions():
    """Regression: SUM over zero rows returned NULL and int(None) crashed the page."""
    at = launch("customer360")
    box = next(sb for sb in at.selectbox if sb.key == "c360_customer")
    box.select(next(o for o in box.options if o.startswith("CUST-0002"))).run()
    assert_clean(at)


def test_report_builder_handles_customer_with_no_flags():
    at = launch("report")
    box = next(sb for sb in at.selectbox if sb.key == "report_customer")
    zero = [o for o in box.options if "(0 flagged)" in o]
    assert zero, "expected at least one customer with no flagged transactions"
    box.select(zero[0]).run()
    assert_clean(at)


def test_copilot_answers_a_question_with_data():
    at = launch("copilot")
    at.text_input[0].set_value("How many flagged transactions are there?")
    at.button(key="FormSubmitter:copilot_form-Ask").click().run()
    entry = at.session_state["copilot_history"][0]
    assert entry["error"] is None, entry["error"]
    assert entry["sql"], "no SQL generated"
    assert entry["df"] is not None and len(entry["df"]) > 0


@pytest.mark.skipif(not HOSTED, reason="usage cap only applies to the hosted (secrets) deployment")
def test_public_usage_cap_blocks_extra_ai_calls():
    at = launch("copilot")
    at.session_state["cortex_calls"] = 20
    at.text_input[0].set_value("How many customers are there?")
    at.button(key="FormSubmitter:copilot_form-Ask").click().run()
    assert any("limit has been reached" in w.value for w in at.warning)
    assert not at.session_state["copilot_history"], "a capped request still reached Cortex"


def test_report_builder_generates_finding_narrative():
    at = launch("report")
    assert any("Most relevant policy" in m.value for m in at.markdown), "no policy citation shown"
    at.button(key="report_generate").click().run()
    assert_clean(at)
    narrative = next(iter(at.session_state["findings"].values()), "")
    assert len(narrative) > 100, f"narrative too short: {narrative!r}"
