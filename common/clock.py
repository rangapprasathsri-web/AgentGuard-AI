from datetime import datetime, timezone, time
from zoneinfo import ZoneInfo
from typing import Optional
import os


class GuardClock:
    """
    GuardClock provides authoritative time for AgentGuard.
    All time-dependent decisions must derive from this clock.
    Agents can never supply time (Invariant I3).
    Supports test freezing / overriding and DEMO_MODE time offsets.
    """

    def __init__(self, timezone_name: str = "Asia/Kolkata"):
        self.tz = ZoneInfo(timezone_name)
        self._freeze_time: Optional[datetime] = None
        self._offset_seconds: float = 0.0

    def set_time(self, dt: datetime) -> None:
        """Freeze the clock to a specific datetime (for tests and scenario runner)."""
        if dt.tzinfo is None:
            self._freeze_time = dt.replace(tzinfo=self.tz)
        else:
            self._freeze_time = dt.astimezone(self.tz)

    def set_offset(self, seconds: float) -> None:
        """Add an offset in seconds (DEMO_MODE only)."""
        if os.getenv("DEMO_MODE", "false").lower() != "true":
            raise PermissionError("Clock offsets can only be applied when DEMO_MODE is true")
        self._offset_seconds = seconds

    def reset(self) -> None:
        """Reset frozen time and offsets."""
        self._freeze_time = None
        self._offset_seconds = 0.0

    def now_utc(self) -> datetime:
        """Returns the current UTC time as an offset-aware datetime."""
        if self._freeze_time is not None:
            return self._freeze_time.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if self._offset_seconds:
            from datetime import timedelta
            now = now + timedelta(seconds=self._offset_seconds)
        return now

    def now_local(self) -> datetime:
        """Returns current time in the configured local timezone."""
        return self.now_utc().astimezone(self.tz)

    def now_iso(self) -> str:
        """Returns UTC ISO-8601 string."""
        return self.now_utc().isoformat()

    def is_off_hours(self, start_hour: int = 9, end_hour: int = 18) -> bool:
        """
        Returns True if the current local time is outside business hours [start_hour:00, end_hour:00).
        Default business hours: 09:00 - 18:00 Asia/Kolkata.
        """
        local_time = self.now_local().time()
        start = time(start_hour, 0)
        end = time(end_hour, 0)
        return not (start <= local_time < end)


# Global singleton instance for the process
clock = GuardClock()
