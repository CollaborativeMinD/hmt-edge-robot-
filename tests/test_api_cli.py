"""Compatibility facade for the decomposed test_api_cli interfaces."""

import argparse
import json

import pytest
from conftest import TOKEN
from test_api_cli_base import API_TOKEN as API_TOKEN
from test_api_cli_base import HEADERS as HEADERS

from hmt_edge_robot.cli import demonstrate, dispatch, parser
from hmt_edge_robot.runtime import RobotCell


def test_cli_demo_and_commands(cell, tmp_path, capsys):
    result = demonstrate(cell, TOKEN)
    assert result["outcome"]["state"] == "SUCCEEDED"
    assert result["resident"]["decision"] == "ADMIT"
    assert result["health_model"]["decision"] == "HOLD"
    for command in ("replay", "analytics", "export", "resident"):
        args = argparse.Namespace(
            command=command, output=tmp_path / "out.parquet", question="inspect"
        )
        dispatch(args, cell, TOKEN)
        assert json.loads(capsys.readouterr().out)
    assert (tmp_path / "out.parquet").exists()
    assert parser().parse_args(["demo"]).command == "demo"

def test_operator_token_minimum(tmp_path):
    with pytest.raises(ValueError):
        RobotCell(tmp_path / "db", "short")
