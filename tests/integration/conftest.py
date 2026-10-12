import os

import pytest


@pytest.fixture(autouse=True)
def require_compose_postgres() -> None:
    if os.getenv("TICKETING_SKIP_INTEGRATION"):
        pytest.skip("integration disabled")
