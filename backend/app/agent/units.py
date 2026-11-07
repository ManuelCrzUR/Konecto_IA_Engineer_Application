"""Units of the D-51 field binding. Pure code.

Input:  the text right after a figure.
Output: unit_key(text) -> predicate over actuator field keys, or None when no unit of
        the map follows (Hz, V, degrees and no unit are not in it).

Map (one optional space or non-breaking space between figure and unit; case matters
for Nm, A and W):
  Nm, N·m, N.m -> keys ending _nm            in-lbs, in-lb, in lbs, lb-in, in·lbs -> _in_lbs
  A, amp(s), amperes, amperios -> fla_*, lra_*   W, watts, vatios -> motor_power_w
  % -> keys with "duty"                      s, sec(s), seconds, segundos, seg -> "speed"
  cycles/h, cycles per hour, ciclos/h, ciclos por hora -> "cycles"
  starts/h, starts per hour, arranques/h, arranques por hora -> "starts"
"""

from __future__ import annotations

import re
from collections.abc import Callable

Key = Callable[[str], bool]
_SP = r"[ \u00a0]?"
# (regex right after the figure, which field keys carry that unit). First match wins.
_UNITS: list[tuple[re.Pattern[str], Key]] = [
    (re.compile(_SP + p), k)
    for p, k in [
        (r"(?:Nm|N·m|N\.m)(?![A-Za-z])", lambda s: s.endswith("_nm")),
        (r"(?i:in[-\s·]?lbs?|lb-in)(?![A-Za-z])", lambda s: s.endswith("_in_lbs")),
        (
            r"(?:A|(?i:amps?|amperes|amperios))(?![A-Za-z0-9])",
            lambda s: s.startswith(("fla_", "lra_")),
        ),
        (r"(?:W|(?i:watts|vatios))(?![A-Za-z0-9])", lambda s: s == "motor_power_w"),
        (r"%", lambda s: "duty" in s),
        (r"(?:s|(?i:secs?|seconds|segundos|seg))(?![A-Za-z0-9])", lambda s: "speed" in s),
        (r"(?i:cycles/h|cycles per hour|ciclos/h|ciclos por hora)", lambda s: "cycles" in s),
        (r"(?i:starts/h|starts per hour|arranques/h|arranques por hora)", lambda s: "starts" in s),
    ]
]


def unit_key(text: str) -> Key | None:
    return next((k for rx, k in _UNITS if rx.match(text)), None)
