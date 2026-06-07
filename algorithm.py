"""
Ядро бизнес-логики: автоматический подбор поставщика и расчёт финансов.

Модуль намеренно сделан "чистым" (без обращений к БД / Flask), чтобы:
  * его было легко покрыть тестами (см. test_algorithm.py);
  * ровно та же логика использовалась и при первичном засеве заказов,
    и при создании нового заказа через веб-интерфейс.

Бизнес-правила (из ТЗ):
  1. Минимальная наценка — 25% от цены закупки.
  2. Логистикой пренебрегаем.
  3. Срок поставки клиенту критичен: поставщик должен успеть привезти товар
     ДО даты поставки клиенту. Доступное нам время = (срок поставки клиенту − дата заказа).
     Подходит поставщик, у которого срок поставки (дней) <= доступного времени.
  4. После закрытия заказа остаток на складе выбранного поставщика уменьшается.
  5. Если ни один поставщик не подходит — заказ "Требует ручного разбора".
"""

from datetime import date

# Минимальная наценка к цене закупки.
MIN_MARKUP = 0.25

STATUS_MATCHED = "Подобран поставщик"
STATUS_MANUAL = "Требует ручного разбора"


def available_days(order_date: date, client_due_date: date) -> int:
    """Сколько дней у нас есть, чтобы товар оказался у нас ДО поставки клиенту.

    Пример из ТЗ: заказ 01.05, поставка клиенту 03.05 -> 2 дня.
    """
    return (client_due_date - order_date).days


def select_supplier(order, suppliers):
    """Подобрать поставщика для одного заказа.

    Параметры
    ---------
    order : dict
        Ожидаются ключи: 'fruit', 'quantity', 'order_date', 'client_due_date'
        (даты — объекты datetime.date).
    suppliers : list[dict]
        Каждый поставщик: 'id', 'fruit', 'purchase_price', 'stock', 'delivery_days'.

    Возвращает
    ----------
    dict с полями:
        status        : STATUS_MATCHED | STATUS_MANUAL
        supplier_id   : id выбранного поставщика или None
        sale_price    : цена продажи (₸/кг) или None
        order_sum     : сумма заказа (₸) или None
        reason        : пояснение, почему заказ ушёл в ручной разбор (или None)
    """
    days = available_days(order["order_date"], order["client_due_date"])

    # 1. Все поставщики нужного фрукта.
    candidates = [s for s in suppliers if s["fruit"] == order["fruit"]]
    if not candidates:
        return _manual("нет поставщиков этого фрукта")

    # 2. У кого хватает остатка на складе.
    enough_stock = [s for s in candidates if s["stock"] >= order["quantity"]]
    if not enough_stock:
        return _manual("ни у кого не хватает остатка на складе")

    # 3. Кто успевает по сроку (срок поставщика <= доступного времени).
    in_time = [s for s in enough_stock if s["delivery_days"] <= days]
    if not in_time:
        return _manual("ни один поставщик не успевает по сроку")

    # 4. Из оставшихся — с самой низкой ценой закупки.
    #    При равной цене берём того, кто быстрее (детерминированный выбор).
    best = min(in_time, key=lambda s: (s["purchase_price"], s["delivery_days"], s["id"]))

    sale_price = round(best["purchase_price"] * (1 + MIN_MARKUP), 2)
    order_sum = round(sale_price * order["quantity"], 2)

    return {
        "status": STATUS_MATCHED,
        "supplier_id": best["id"],
        "purchase_price": best["purchase_price"],
        "sale_price": sale_price,
        "order_sum": order_sum,
        "reason": None,
    }


def _manual(reason: str) -> dict:
    return {
        "status": STATUS_MANUAL,
        "supplier_id": None,
        "purchase_price": None,
        "sale_price": None,
        "order_sum": None,
        "reason": reason,
    }
