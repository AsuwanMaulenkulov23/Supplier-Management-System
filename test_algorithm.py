"""
Тесты ядра алгоритма. Запуск:  python -m pytest test_algorithm.py -q
(или просто  python test_algorithm.py  — внизу есть ручной прогон без pytest).
"""

from datetime import date

from algorithm import select_supplier, available_days, STATUS_MATCHED, STATUS_MANUAL

# Поставщики яблок из приложенной таблицы.
APPLE_SUPPLIERS = [
    {"id": 1, "fruit": "Яблоки", "purchase_price": 850, "stock": 1200, "delivery_days": 2},
    {"id": 2, "fruit": "Яблоки", "purchase_price": 820, "stock": 800, "delivery_days": 3},
    {"id": 3, "fruit": "Яблоки", "purchase_price": 880, "stock": 1500, "delivery_days": 4},
]


def test_available_days_example_from_spec():
    # Пример из ТЗ: заказ 01.05, поставка клиенту 03.05 -> 2 дня.
    assert available_days(date(2026, 5, 1), date(2026, 5, 3)) == 2


def test_picks_cheapest_in_time():
    # Заказ 1: 150кг яблок, 01.05 -> 03.05 (2 дня).
    # Поставщик №2 (820₸) успевает за 3 дня? Нет, 3 > 2. Остаётся №1 (850₸, 2 дня).
    order = {"fruit": "Яблоки", "quantity": 150,
             "order_date": date(2026, 5, 1), "client_due_date": date(2026, 5, 3)}
    res = select_supplier(order, APPLE_SUPPLIERS)
    assert res["status"] == STATUS_MATCHED
    assert res["supplier_id"] == 1
    assert res["sale_price"] == 1062.5          # 850 * 1.25
    assert res["order_sum"] == 159375.0         # 1062.5 * 150


def test_picks_truly_cheapest_when_all_in_time():
    # Больше времени (5 дней) -> успевают все, берём самого дешёвого (№2, 820₸).
    order = {"fruit": "Яблоки", "quantity": 150,
             "order_date": date(2026, 5, 1), "client_due_date": date(2026, 5, 6)}
    res = select_supplier(order, APPLE_SUPPLIERS)
    assert res["supplier_id"] == 2
    assert res["sale_price"] == 1025.0          # 820 * 1.25


def test_manual_when_no_stock():
    order = {"fruit": "Яблоки", "quantity": 99999,
             "order_date": date(2026, 5, 1), "client_due_date": date(2026, 5, 30)}
    res = select_supplier(order, APPLE_SUPPLIERS)
    assert res["status"] == STATUS_MANUAL
    assert "остатк" in res["reason"]


def test_manual_when_too_late():
    # 1 день на всё — никто не успевает (минимальный срок 2 дня).
    order = {"fruit": "Яблоки", "quantity": 100,
             "order_date": date(2026, 5, 1), "client_due_date": date(2026, 5, 2)}
    res = select_supplier(order, APPLE_SUPPLIERS)
    assert res["status"] == STATUS_MANUAL
    assert "сро" in res["reason"]


def test_manual_when_fruit_unknown():
    order = {"fruit": "Манго", "quantity": 10,
             "order_date": date(2026, 5, 1), "client_due_date": date(2026, 5, 20)}
    res = select_supplier(order, APPLE_SUPPLIERS)
    assert res["status"] == STATUS_MANUAL


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} тестов прошли")
