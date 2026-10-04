from datetime import date
from uuid import uuid4

from app.agent_rules import Movement, Snapshot, evaluate, month_start


def snapshot(movements=(), balance=10000, today=date(2026, 10, 15), opening=date(2026, 1, 1)):
    return Snapshot(uuid4(), today, opening, balance, list(movements))


def test_month_boundary_and_goal_use_exact_integers():
    assert month_start(date(2026, 1, 15), -3) == date(2025, 10, 1)
    amount = 2**53 + 1
    result = evaluate("goal", snapshot(balance=amount), amount)
    assert result[0].facts == {"balance_cents": amount, "target_cents": amount}
    assert evaluate("goal", snapshot(balance=amount - 1), amount) == []
    assert evaluate("goal", snapshot(), None) == []


def test_projection_uses_calendar_days_and_ignores_future_income():
    rows = [
        Movement(date(2026, 2, 1), -2800, "expense"),
        Movement(date(2026, 3, 1), -9900, "expense"),
        Movement(date(2026, 2, 1), 20000, "income"),
    ]
    result = evaluate("runway", snapshot(rows, 100, date(2026, 2, 14)))
    assert result[0].facts["projected_expense_cents"] == 2800
    assert result[0].facts["remaining_days"] == 14
    assert not evaluate("runway", snapshot(rows, 10000, date(2026, 2, 14)))
    assert not evaluate("runway", snapshot(rows, 0, opening=date(2026, 10, 2)))


def test_anomaly_requires_history_and_compares_variance_without_floats():
    category = uuid4()
    rows = [Movement(date(2026, month, 1), -10000, "expense", category) for month in (7, 8, 9)]
    assert not evaluate("anomaly", snapshot(rows))
    rows.append(Movement(date(2026, 10, 2), -10001, "expense", category))
    signal = evaluate("anomaly", snapshot(rows))[0]
    assert signal.facts["mean_cents_floor"] == 10000
    assert not evaluate("anomaly", snapshot(rows, opening=date(2026, 8, 1)))
    variable = [
        Movement(date(2026, m, 1), -v, "expense", category)
        for m, v in [(7, 100), (8, 50000), (9, 100), (10, 20000)]
    ]
    assert not evaluate("anomaly", snapshot(variable))


def test_subscription_is_only_a_pattern_not_proof_of_unused_service():
    rows = [
        Movement(date(2026, m, 4), -v, "expense", description="Streaming Sintético")
        for m, v in [(8, 2000), (9, 2000), (10, 2500)]
    ]
    signal = evaluate("subscription_watch", snapshot(rows))[0]
    assert signal.facts == {"previous_cents": 2000, "current_cents": 2500}
    assert "possível" in signal.message and "aumentou" in signal.message
    assert not evaluate("subscription_watch", snapshot(rows[:2]))
    assert not evaluate("subscription_watch", snapshot(rows + [rows[-1]]))
