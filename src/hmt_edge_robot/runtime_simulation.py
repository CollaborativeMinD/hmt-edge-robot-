"""RobotCell: simulation responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .contracts import PositionPacket, SensorSample

if TYPE_CHECKING:
    from hmt_edge_robot.runtime import RobotCell

def observe_simulation(
    self: RobotCell,
    seq: int,
    voltage_v: float = 4.1,
    temp_c: float = 45.0,
    human_mm: tuple[float, float, float] = (3000.0, 0.0, 0.0),
) -> None:
    """Explicit SIL acquisition; production observations require qualified adapters."""
    with self.lock:
        now = self.clock()
        self.edge.process(
            SensorSample(
                monotonic_seq=seq,
                observed_at=now,
                voltage_v=voltage_v,
                temp_c=temp_c,
                signal_dbm=-50.0,
            ),
            now,
        )
        robot = PositionPacket(
            position_mm=self.driver.position, monotonic_seq=seq, observed_at=now
        )
        human = PositionPacket(position_mm=human_mm, monotonic_seq=seq, observed_at=now)
        self.safety.update(robot, human, now)
        self.ledger.append(
            "safety",
            str(seq),
            "spatial_observation",
            {"robot": robot.model_dump(mode="json"), "human": human.model_dump(mode="json")},
        )
