import pytest

from app.main import readiness

pytestmark = pytest.mark.integration


def test_readiness_requires_runtime_role(runtime_engine, admin_engine):
    assert readiness(runtime_engine).status == "ok"
    with pytest.raises(PermissionError):
        readiness(admin_engine)
