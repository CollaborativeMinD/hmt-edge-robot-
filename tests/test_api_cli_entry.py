"""test_api_cli: entry interface."""

import argparse
import json
import sys

import pytest
from conftest import TOKEN
from test_api_cli_base import API_TOKEN

from hmt_edge_robot.cli import dispatch, main, serve
from hmt_edge_robot.contracts import Policy
from hmt_edge_robot.runtime import RobotCell


def test_cli_entry_and_serve_configuration(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["hmt-edge-robot", "demo", "--database", str(tmp_path / "demo.db")]
    )
    main()
    assert json.loads(capsys.readouterr().out)["mode"] == "SIL"
    monkeypatch.setattr(sys, "argv", ["hmt-edge-robot", "resident"])
    monkeypatch.delenv("HMT_OPERATOR_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        main()
    monkeypatch.setenv("HMT_OPERATOR_TOKEN", TOKEN)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hmt-edge-robot",
            "demo",
            "--model-id",
            "missing",
            "--database",
            str(tmp_path / "missing.db"),
        ],
    )
    with pytest.raises(SystemExit):
        main()
    import uvicorn

    called = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: called.append(options))
    cell = RobotCell(tmp_path / "serve.db", TOKEN)
    args = argparse.Namespace(port=8080, command="serve")
    monkeypatch.delenv("HMT_API_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        serve(args, cell)
    monkeypatch.setenv("HMT_API_TOKEN", API_TOKEN)
    dispatch(args, cell, TOKEN)
    assert called[0]["host"] == "127.0.0.1" and called[0]["workers"] == 1
    cell.close()

def test_cli_qualified_model_seam(tmp_path, monkeypatch, capsys):
    from hmt_edge_robot.resident import OpenAICompatibleProvider

    async def qualification(self, context):
        assert context["model_id"] == self.model_id
        self.qualified = True
        return "0" * 64

    async def proposal(self, context, question):
        return '{"action":"inspect","explanation":"ok","evidence_refs":[]}'

    monkeypatch.setattr(OpenAICompatibleProvider, "qualify", qualification)
    monkeypatch.setattr(OpenAICompatibleProvider, "propose", proposal)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(Policy().model_dump_json())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hmt-edge-robot",
            "demo",
            "--model-url",
            "http://localhost/v1",
            "--model-id",
            "fixture-v1",
            "--policy",
            str(policy_path),
            "--database",
            str(tmp_path / "model.db"),
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["resident"]["model_id"] == "fixture-v1"
