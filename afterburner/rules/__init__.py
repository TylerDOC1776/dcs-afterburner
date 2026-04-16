"""Rule registry — import all modules to trigger @register decorators."""

from afterburner.rules import (
    maintainability as maintainability,
)  # noqa: F401, I001
from afterburner.rules import (
    mission_size as mission_size,
)
from afterburner.rules import (
    performance as performance,
)
from afterburner.rules import (
    scripting as scripting,
)
from afterburner.rules import (
    triggers as triggers,
)
