"""
Automatic Door Open System
--------------------------
Simulates an automatic door with:
  - Motion sensor detection
  - Obstacle detection (keeps door open if blocked)
  - Auto-close timeout
  - Door state machine (CLOSED -> OPENING -> OPEN -> CLOSING -> CLOSED)
  - Event logging
"""

import time
import threading
import logging
from enum import Enum, auto
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class DoorState(Enum):
    CLOSED = auto()
    OPENING = auto()
    OPEN = auto()
    CLOSING = auto()


class AutomaticDoor:
    """
    Automatic sliding/swing door controller.

    Parameters
    ----------
    open_duration   : seconds to keep door open after motion detected
    open_time       : seconds it takes for the door to fully open
    close_time      : seconds it takes for the door to fully close
    """

    def __init__(self, open_duration: float = 5.0, open_time: float = 1.5, close_time: float = 1.5):
        self.open_duration = open_duration
        self.open_time = open_time
        self.close_time = close_time

        self.state = DoorState.CLOSED
        self._obstacle_present = False
        self._lock = threading.Lock()
        self._close_timer: threading.Timer | None = None

    # ------------------------------------------------------------------
    # Sensor callbacks  (call these from hardware interrupts / GPIO)
    # ------------------------------------------------------------------

    def on_motion_detected(self):
        """Called when the motion/PIR sensor fires."""
        logger.info("Motion detected.")
        with self._lock:
            self._cancel_close_timer()
            if self.state in (DoorState.CLOSED, DoorState.CLOSING):
                self._open_door()
            elif self.state == DoorState.OPEN:
                self._schedule_close()

    def on_obstacle_detected(self):
        """Called when the safety beam / pressure mat detects an obstacle."""
        logger.warning("Obstacle detected — keeping door open.")
        with self._lock:
            self._obstacle_present = True
            self._cancel_close_timer()
            if self.state == DoorState.CLOSING:
                self._open_door()

    def on_obstacle_cleared(self):
        """Called when the obstacle is no longer detected."""
        logger.info("Obstacle cleared.")
        with self._lock:
            self._obstacle_present = False
            if self.state == DoorState.OPEN:
                self._schedule_close()

    # ------------------------------------------------------------------
    # Internal door mechanics
    # ------------------------------------------------------------------

    def _open_door(self):
        """Begin opening sequence (must be called with lock held)."""
        if self.state == DoorState.OPEN:
            self._schedule_close()
            return

        self.state = DoorState.OPENING
        logger.info("Door OPENING...")
        threading.Thread(target=self._finish_opening, daemon=True).start()

    def _finish_opening(self):
        time.sleep(self.open_time)
        with self._lock:
            if self.state == DoorState.OPENING:
                self.state = DoorState.OPEN
                logger.info("Door is now OPEN.")
                self._schedule_close()

    def _schedule_close(self):
        """Schedule auto-close after open_duration (lock must be held)."""
        if self._obstacle_present:
            return
        self._cancel_close_timer()
        self._close_timer = threading.Timer(self.open_duration, self._begin_closing)
        self._close_timer.daemon = True
        self._close_timer.start()
        logger.info("Door will auto-close in %.1f seconds.", self.open_duration)

    def _begin_closing(self):
        with self._lock:
            if self._obstacle_present or self.state != DoorState.OPEN:
                return
            self.state = DoorState.CLOSING
            logger.info("Door CLOSING...")
        threading.Thread(target=self._finish_closing, daemon=True).start()

    def _finish_closing(self):
        time.sleep(self.close_time)
        with self._lock:
            if self.state == DoorState.CLOSING:
                self.state = DoorState.CLOSED
                logger.info("Door is now CLOSED.")

    def _cancel_close_timer(self):
        if self._close_timer is not None:
            self._close_timer.cancel()
            self._close_timer = None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> str:
        return f"Door state: {self.state.name}"


# ---------------------------------------------------------------------------
# Demo / simulation
# ---------------------------------------------------------------------------

def simulate():
    door = AutomaticDoor(open_duration=3.0, open_time=1.0, close_time=1.0)
    logger.info("=== Automatic Door System Started ===")
    logger.info(door.status())

    # Scenario 1: Person approaches
    time.sleep(1)
    logger.info("--- Scenario 1: Person approaches ---")
    door.on_motion_detected()
    time.sleep(1.5)
    logger.info(door.status())

    # Door should auto-close after open_duration; wait for that
    time.sleep(4)
    logger.info(door.status())

    # Scenario 2: Person approaches but stands in doorway
    time.sleep(1)
    logger.info("--- Scenario 2: Person blocks door while closing ---")
    door.on_motion_detected()
    time.sleep(1.2)
    door.on_obstacle_detected()      # blocks auto-close
    time.sleep(3)
    logger.info(door.status())       # still open due to obstacle
    door.on_obstacle_cleared()       # person steps away
    time.sleep(4.5)
    logger.info(door.status())       # should be closed

    # Scenario 3: Rapid repeated motion triggers
    time.sleep(1)
    logger.info("--- Scenario 3: Rapid triggers (debounce check) ---")
    for _ in range(3):
        door.on_motion_detected()
        time.sleep(0.3)
    time.sleep(5)
    logger.info(door.status())

    logger.info("=== Simulation complete ===")


if __name__ == "__main__":
    simulate()
