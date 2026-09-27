import runpy
from unittest.mock import Mock

import pytest

from app.llm import LLMUnavailable, MoneyAnswer
from app.llm_router import Routed


@pytest.mark.parametrize("success", [True, False])
def test_smoke_is_synthetic_and_prints_no_payload(monkeypatch, capsys, success):
    router = Mock()
    if success:
        router.generate.return_value = Routed(MoneyAnswer(source_id="demo", amount_cents=4200), ())
    else:
        router.generate.side_effect = LLMUnavailable("private response")
    monkeypatch.setattr("app.llm_service.runtime_router", lambda: router)
    if success:
        runpy.run_path("scripts/smoke_llm.py", run_name="__main__")
    else:
        with pytest.raises(SystemExit):
            runpy.run_path("scripts/smoke_llm.py", run_name="__main__")
    assert router.generate.call_args.args[0].classification == "synthetic"
    output = capsys.readouterr().out
    assert "4200" not in output and "private" not in output
