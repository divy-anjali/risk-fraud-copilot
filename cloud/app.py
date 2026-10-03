"""Streamlit Community Cloud entrypoint.

Runs the repo-root streamlit_app.py unchanged, so there is one source of truth for
the app. It lives in its own folder so Community Cloud uses cloud/requirements.txt
rather than the root environment.yml meant for Streamlit-in-Snowflake.

Credentials come from the app's Secrets setting ([snowflake] section, key-pair
auth) - see .streamlit/secrets.toml.example.
"""
import pathlib
import runpy

runpy.run_path(
    str(pathlib.Path(__file__).resolve().parent.parent / "streamlit_app.py"),
    run_name="__main__",
)
