"""Shared fixtures for the Risk & Fraud Copilot validation suite.

Run from the project root:
    .venv\\Scripts\\python.exe -m pytest tests -v

`owner` connects with the named connection in connections.toml (the deploying
user). `public` connects as the read-only COPILOT_PUBLIC_SVC key-pair user from
.streamlit/secrets.toml, and those tests skip when that file is absent.
"""
import pathlib
import tomllib
import warnings

import pytest
import snowflake.connector

warnings.filterwarnings("ignore")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SECRETS = ROOT / ".streamlit" / "secrets.toml"
CONNECTION_NAME = "qbgiwtu-dk32675"

# `?` placeholders, matching the app's run_query binding.
snowflake.connector.paramstyle = "qmark"


class Sql:
    """Thin wrapper: run a statement and get rows back as dicts."""

    def __init__(self, con):
        self.con = con

    def rows(self, sql, params=None):
        cur = self.con.cursor(snowflake.connector.DictCursor)
        cur.execute(sql, params)
        return cur.fetchall()

    def one(self, sql, params=None):
        rows = self.rows(sql, params)
        assert rows, f"no rows returned for: {sql}"
        return rows[0]

    def scalar(self, sql, params=None):
        return next(iter(self.one(sql, params).values()))


def public_config():
    """[snowflake] secrets with the PEM key converted to DER bytes, or None."""
    if not SECRETS.exists():
        return None
    from cryptography.hazmat.primitives import serialization

    cfg = tomllib.loads(SECRETS.read_text(encoding="utf-8"))["snowflake"]
    key = serialization.load_pem_private_key(cfg["private_key"].encode(), password=None)
    cfg = dict(cfg)
    cfg["private_key"] = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cfg


@pytest.fixture(scope="session")
def owner():
    con = snowflake.connector.connect(
        connection_name=CONNECTION_NAME, client_store_temporary_credential=True
    )
    yield Sql(con)
    con.close()


@pytest.fixture(scope="session")
def public():
    cfg = public_config()
    if cfg is None:
        pytest.skip("no .streamlit/secrets.toml - public service user not configured locally")
    con = snowflake.connector.connect(**cfg)
    yield Sql(con)
    con.close()
