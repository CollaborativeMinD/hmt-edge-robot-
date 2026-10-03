"""Executable evidence view. Uses the composed runtime, with explicit SIL inputs."""

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def imports():
    import asyncio
    import secrets
    import tempfile
    from pathlib import Path

    import marimo as mo

    from hmt_edge_robot.cli import demonstrate
    from hmt_edge_robot.runtime import RobotCell

    return Path, RobotCell, asyncio, demonstrate, mo, secrets, tempfile


@app.cell
async def mission(Path, RobotCell, asyncio, demonstrate, secrets, tempfile):
    with tempfile.TemporaryDirectory() as directory:
        token = secrets.token_hex(24)
        cell = RobotCell(Path(directory) / "cell.db", token)
        try:
            outcome = await asyncio.to_thread(demonstrate, cell, token)
            events = cell.analytics.frame()
            summary = cell.analytics.summary()
            trends = cell.analytics.sensor_trends()
        finally:
            cell.close()
    return events, outcome, summary, trends


@app.cell
def evidence(mo, outcome, summary, trends):
    mo.vstack(
        [
            mo.md("# Resident HMT cell — executable SIL evidence"),
            mo.md(
                "Synthetic acquisition; simulated actuation. All values below come from the runtime."
            ),
            mo.ui.table(
                [
                    {
                        "task_state": outcome["outcome"]["state"],
                        "resident": outcome["resident"]["decision"],
                        "ml_envelope": outcome["health_model"]["decision"],
                        "verified_events": outcome["verified_events"],
                    }
                ]
            ),
            mo.ui.table(summary),
            mo.ui.table([trends]),
        ]
    )
    return


@app.cell
def chain(events, mo):
    mo.ui.table(events)
    return


if __name__ == "__main__":
    app.run()
