from __future__ import annotations

import subprocess
import unittest

from adapters.contract_adapter import invoke


def _request(**updates: object) -> dict[str, object]:
    request: dict[str, object] = {
        "capability_id": "scaffoldctl.authority",
        "admission_epoch": 7,
        "current_epoch": 7,
        "lease_id": "lease-1",
        "authority_tier": "verification",
        "agent_role": "boundary-auditor",
        "arguments": [],
    }
    request.update(updates)
    return request


class McpContractAdapterTests(unittest.TestCase):
    def test_invocation_is_bounded_subprocess_only(self) -> None:
        observed: dict[str, object] = {}

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            observed.update({"command": command, **kwargs})
            return subprocess.CompletedProcess(command, 0, "{}\n", "")

        result = invoke(_request(), runner=runner)
        self.assertEqual(observed["command"], ["scaffoldctl", "authority"])
        self.assertFalse(observed["check"])
        self.assertEqual(observed["timeout"], 30)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(
            result["authority_ceiling"],
            ["NO_DIRECT_ACTUATION", "NO_ARCHITECTURE_MUTATION", "NO_PROMOTION"],
        )

    def test_exact_outer_schema_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "MCP_ADAPTER_SCHEMA_INVALID"):
            invoke({**_request(), "unexpected": True})

    def test_stale_epoch_is_denied(self) -> None:
        with self.assertRaisesRegex(PermissionError, "MCP_STALE_REMEMBERED_AFFORDANCE"):
            invoke(_request(current_epoch=8))

    def test_epoch_must_be_a_nonnegative_integer(self) -> None:
        for invalid in (-1, True, "7"):
            with (
                self.subTest(invalid=invalid),
                self.assertRaisesRegex(ValueError, "MCP_EPOCH_INVALID"),
            ):
                invoke(_request(admission_epoch=invalid))

    def test_present_authority_is_required(self) -> None:
        with self.assertRaisesRegex(PermissionError, "MCP_PRESENT_AUTHORITY_REQUIRED"):
            invoke(_request(lease_id=""))

    def test_unadmitted_capability_is_denied(self) -> None:
        for invalid in ("scaffoldctl.scaffold", "", ["scaffoldctl.authority"]):
            with (
                self.subTest(invalid=invalid),
                self.assertRaisesRegex(PermissionError, "MCP_CAPABILITY_NOT_ADMITTED"),
            ):
                invoke(_request(capability_id=invalid))

    def test_argument_bounds_are_enforced(self) -> None:
        with self.assertRaisesRegex(ValueError, "MCP_ARGUMENT_BOUND_EXCEEDED"):
            invoke(_request(capability_id="scaffoldctl.schema", arguments=["x"] * 25))
        with self.assertRaisesRegex(ValueError, "MCP_ARGUMENT_INVALID"):
            invoke(_request(capability_id="scaffoldctl.schema", arguments=["x\x00y"]))


if __name__ == "__main__":
    unittest.main()
