"""REQ-NFR-11: a genuine type mismatch must fail the configured checker."""
import asyncio
from pathlib import Path


def test_pyrefly_rejects_invalid_return(tmp_path):
    async def check(source):
        path = tmp_path / "typing_probe.py"
        path.write_text(source)
        config = Path(__file__).resolve().parents[1] / "pyproject.toml"
        process = await asyncio.create_subprocess_exec(
            "pyrefly", "check", "--config", str(config), "--min-severity", "warn", str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise
        return process.returncode, output.decode()
    valid, _ = asyncio.run(check('def result() -> int:\n    return 1\n'))
    invalid, diagnostic = asyncio.run(check('def result() -> int:\n    return "wrong"\n'))
    assert valid == 0
    assert invalid != 0 and "bad-return" in diagnostic
