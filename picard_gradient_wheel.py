#!/bin/python3

# Claude Opus 4.6 on behalf of brp-optics, 2026.03.18
# Based on sample code from Picard.

"""
picard_gradient_wheel.py — Wrapper for the Picard Industries USB Gradient Wheel.

Requires:
    - pythonnet (pip install pythonnet)
    - PiUsb.dll, PiUsbNet.dll, and PiUsbNet.xml in the working directory
      (or on sys.path / the .NET assembly search path).

Usage:
    from picard_gradient_wheel import PicardGradientWheel

    wheel = PicardGradientWheel(serial_number=68)
    actual_pos = wheel.move_to(400)   # returns the actual settled position
    print(f"Wheel is at position {actual_pos}")
    wheel.close()

    # Or as a context manager:
    with PicardGradientWheel(serial_number=68) as wheel:
        pos = wheel.move_to(400)
"""

from __future__ import annotations

import logging
import threading
import time

import clr

clr.AddReference("PiUsbNet")
import PiUsbNet  # noqa: E402  (must follow clr.AddReference)

logger = logging.getLogger(__name__)


class GradientWheelError(Exception):
    """Raised when the gradient wheel cannot complete an operation."""


class PicardGradientWheel:
    """Controls a Picard Industries USB Gradient Wheel via PiUsbNet.

    Parameters
    ----------
    serial_number : int
        The USB serial number of the gradient wheel (printed on the device,
        also shown in Picard's own GUI software).
    tolerance : int
        Acceptable deviation from the target position (default ±2 increments).
    move_timeout : float
        Seconds to wait for the initial move before attempting jitter
        correction (default 10 s).
    jitter_timeout : float
        Seconds to wait for each jitter correction attempt (default 4 s).
    max_jitter_attempts : int
        How many small correction moves to try before giving up (default 3).
    jitter_step : int
        Size of the nudge applied during jitter correction (default 5
        increments past the target, then back).
    """

    # Gradient wheel valid range per Picard spec
    POS_MIN = 1
    POS_MAX = 800

    def __init__(
        self,
        serial_number: int,
        tolerance: int = 2,
        move_timeout: float = 10.0,
        jitter_timeout: float = 4.0,
        max_jitter_attempts: int = 3,
        jitter_step: int = 10,
    ):
        self.serial_number = serial_number
        self.tolerance = tolerance
        self.move_timeout = move_timeout
        self.jitter_timeout = jitter_timeout
        self.max_jitter_attempts = max_jitter_attempts
        self.jitter_step = jitter_step

        self._rotator: PiUsbNet.Rotator = PiUsbNet.Rotator()

        # Threading event that fires whenever the position callback is invoked,
        # so we can wake up from sleep early when the wheel settles.
        self._position_event = threading.Event()
        self._last_callback_position: int | None = None

        self._rotator.PositionChanged += self._on_position_changed
        self._rotator.Open(serial_number)

        if not self._rotator.IsConnected:
            raise GradientWheelError(
                f"Gradient wheel with serial {serial_number} not found. "
                "Check USB connection and serial number."
            )
        logger.info(
            "Connected to Picard gradient wheel serial=%d at position=%d",
            serial_number,
            self.position,
        )

    # -- Public API -----------------------------------------------------------

    @property
    def position(self) -> int:
        """Current wheel position (1–800)."""
        return int(self._rotator.Position)

    @property
    def is_connected(self) -> bool:
        return bool(self._rotator.IsConnected)

    def move_to(self, target: int) -> int:
        """Move toward *target* and return the actual settled position.

        The method blocks until the wheel is within ±tolerance of the target
        or all retry attempts are exhausted.  In either case it returns the
        actual position — the caller should use this value (not the requested
        target) for the calibration data point.

        Parameters
        ----------
        target : int
            Desired position (clamped to 1–800).

        Returns
        -------
        int
            The actual position the wheel settled at.

        Raises
        ------
        GradientWheelError
            If the device is disconnected.
        """
        if not self.is_connected:
            raise GradientWheelError("Gradient wheel is not connected.")

        target = self._clamp(target)

        # --- Primary move ----------------------------------------------------
        logger.debug("Moving to %d (current=%d)", target, self.position)
        self._position_event.clear()
        self._rotator.MoveTo(target)
        actual = self._wait_for_settle(target, self.move_timeout)

        if self._within_tolerance(actual, target):
            logger.debug("Settled at %d (target=%d)", actual, target)
            return actual

        # --- Jitter correction ------------------------------------------------
        for attempt in range(1, self.max_jitter_attempts + 1):
            logger.debug(
                "Jitter attempt %d/%d: at %d, target %d",
                attempt,
                self.max_jitter_attempts,
                actual,
                target,
            )
            overshoot = self._pick_jitter_target(target, actual)
            self._position_event.clear()
            self._rotator.MoveTo(overshoot)
            self._wait_for_settle(overshoot, self.jitter_timeout / 2)

            # Now come back to the real target
            self._position_event.clear()
            self._rotator.MoveTo(target)
            actual = self._wait_for_settle(target, self.jitter_timeout / 2)

            if self._within_tolerance(actual, target):
                logger.debug(
                    "Jitter correction succeeded on attempt %d: at %d",
                    attempt,
                    actual,
                )
                return actual

        logger.warning(
            "Gave up reaching target %d after %d jitter attempts; "
            "actual position is %d",
            target,
            self.max_jitter_attempts,
            actual,
        )
        return actual

    def close(self) -> None:
        """Disconnect from the gradient wheel."""
        try:
            self._rotator.PositionChanged -= self._on_position_changed
        except Exception:
            pass
        try:
            self._rotator.Close()
        except Exception:
            pass
        logger.info("Gradient wheel serial=%d closed.", self.serial_number)

    # -- Context manager ------------------------------------------------------

    def __enter__(self) -> PicardGradientWheel:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- Internal helpers -----------------------------------------------------

    def _on_position_changed(
        self,
        sender: PiUsbNet.Rotator,
        args: PiUsbNet.RotatorPositionChangedEventArgs,
    ) -> None:
        """Callback invoked by PiUsbNet on a worker thread."""
        self._last_callback_position = int(args.Position)
        self._position_event.set()

    def _wait_for_settle(self, target: int, timeout: float) -> int:
        """Poll position until within tolerance or timeout expires.

        Uses the threading.Event from the position-changed callback so we
        wake up promptly when the wheel stops, rather than sleeping through
        fixed intervals.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            actual = self.position
            if self._within_tolerance(actual, target):
                return actual
            # Wait for the next position callback, but wake up periodically
            # to re-check in case we missed a callback.
            remaining = deadline - time.monotonic()
            self._position_event.wait(timeout=min(0.2, max(remaining, 0)))
            self._position_event.clear()
        return self.position

    def _within_tolerance(self, actual: int, target: int) -> bool:
        return abs(actual - target) <= self.tolerance

    def _pick_jitter_target(self, target: int, actual: int) -> int:
        """Choose a nudge position on the *opposite* side of the target from
        where we currently are, so the wheel approaches from a fresh direction.
        """
        if actual >= target:
            overshoot = target - self.jitter_step
        else:
            overshoot = target + self.jitter_step
        return self._clamp(overshoot)

    def _clamp(self, pos: int) -> int:
        return max(self.POS_MIN, min(self.POS_MAX, int(pos)))


# ---------------------------------------------------------------------------
# Quick self-test when run directly
# Example: python picard_gradient_wheel.py 68 # 68 being the serial number of our wheel
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    serial = int(sys.argv[1]) if len(sys.argv) > 1 else 68
    test_positions = [1, 200, 400, 600, 800, 400]

    with PicardGradientWheel(serial_number=serial) as wheel:
        for target in test_positions:
            actual = wheel.move_to(target)
            status = "OK" if abs(actual - target) <= wheel.tolerance else "MISS"
            print(f"  target={target:>4d}  actual={actual:>4d}  [{status}]")
