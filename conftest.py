"""The hypothesis `deep` profile of spec 9.1, registered before `--hypothesis-profile` is read.

At the repository root so that every test path (`tests/`, `tds/tests/`) loads it.
`ci`, the default run's, is the profile hypothesis ships (derandomized, no
deadline, no example database); `deep`, the `engine / property-deep` job's,
is that profile with 9.1's "e.g. 500 cases".
"""

from __future__ import annotations

from hypothesis import settings

settings.register_profile("deep", parent=settings.get_profile("ci"), max_examples=500)
