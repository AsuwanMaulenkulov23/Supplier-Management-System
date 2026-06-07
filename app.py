"""
Бэкенд: Flask + SQLite.

Запуск:
    pip install -r requirements.txt
    python app.py
    -> http://127.0.0.1:5000

Авторизация — сессионная (cookie). Разграничение прав — декоратор @require_role.
Фронтенд (templates/index.html + static/*) опрашивает API каждые 15 секунд (polling),
поэтому данные у всех пользователей синхронизируются автоматически.
"""

import json
import os
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask,
    g,
    jsonify,
    render_template,
    request,
    session,
)
from werkzeug.security import check_password_hash

import algorithm
from database import DB_PATH, get_conn, init_db

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Права ролей: на какие страницы/действия есть доступ.
ROLE_PERMS = {
    "buyer": {
        "label": "Закупщик",
        "suppliers": "write",  # CRUD поставщиков
        "orders": "read",  # заказы только чтение
        "finance": "none",  # финансы не видит
    },
    "manager": {
        "label": "Менеджер продаж",
        "suppliers": "read",  # поставщики только чтение
        "orders": "write",  # CRUD заказов
        "finance": "orders",  # видит финансы по заказам, но не общую сводку компании
    },
    "director": {
        "label": "Руководитель",
        "suppliers": "write",
        "orders": "write",
        "finance": "full",  # полная финансовая сводка компании
    },
}


# ----------------------------------------------------------------------------
# Инфраструктура: соединение с БД на запрос, текущий пользователь, аудит.
# ----------------------------------------------------------------------------
def db():
    if "db" not in g:
        g.db = get_conn()
    return g.db


@app.teardown_appcontext
def close_db(exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def audit(entity, entity_id, action, details=""):
    db().execute(
        "INSERT INTO audit_log (ts, username, entity, entity_id, action, details) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(timespec="seconds"),
            session.get("username", "?"),
            entity,
            entity_id,
            action,
            details,
        ),
    )


# ----------------------------------------------------------------------------
# Декораторы доступа.
# ----------------------------------------------------------------------------
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "Требуется авторизация"}), 401
        return fn(*args, **kwargs)

    return wrapper


def require(resource, level):
    """level: 'read' | 'write'. Проверяет, что у роли достаточно прав на ресурс."""

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "Требуется авторизация"}), 401
            perm = ROLE_PERMS[user["role"]].get(resource, "none")
            ok = (level == "read" and perm in ("read", "write", "orders", "full")) or (
                level == "write" and perm == "write"
            )
            if not ok:
                return jsonify({"error": "Недостаточно прав"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return deco


# ----------------------------------------------------------------------------
# Подбор поставщика (использует чистый алгоритм + живые остатки из БД).
# ----------------------------------------------------------------------------
def run_algorithm_for_order(
    restaurant, fruit, quantity, order_date_iso, client_due_iso
):
    suppliers = [dict(s) for s in db().execute("SELECT * FROM suppliers").fetchall()]
    return algorithm.select_supplier(
        {
            "fruit": fruit,
            "quantity": float(quantity),
            "order_date": date.fromisoformat(order_date_iso),
            "client_due_date": date.fromisoformat(client_due_iso),
        },
        suppliers,
    )


# ----------------------------------------------------------------------------
# Аутентификация.
# ----------------------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    user = (
        db()
        .execute("SELECT * FROM users WHERE username = ?", (data.get("username", ""),))
        .fetchone()
    )
    if not user or not check_password_hash(
        user["password_hash"], data.get("password", "")
    ):
        return jsonify({"error": "Неверный логин или пароль"}), 401
    session["uid"] = user["id"]
    session["username"] = user["username"]
    return jsonify(_me(user))


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def me():
    user = current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401
    return jsonify(_me(user))


def _me(user):
    return {
        "username": user["username"],
        "role": user["role"],
        "role_label": ROLE_PERMS[user["role"]]["label"],
        "perms": {k: v for k, v in ROLE_PERMS[user["role"]].items() if k != "label"},
        "full_name": user["full_name"],
    }


# ----------------------------------------------------------------------------
# Поставщики (Таблица 1).
# ----------------------------------------------------------------------------
@app.route("/api/suppliers")
@require("suppliers", "read")
def list_suppliers():
    rows = (
        db()
        .execute("SELECT * FROM suppliers ORDER BY fruit, purchase_price")
        .fetchall()
    )
    return jsonify([dict(r) for r in rows])


@app.route("/api/suppliers", methods=["POST"])
@require("suppliers", "write")
def create_supplier():
    d = request.get_json(force=True)
    cur = db().execute(
        "INSERT INTO suppliers (fruit, purchase_price, stock, name, delivery_days) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            d["fruit"].strip(),
            float(d["purchase_price"]),
            float(d["stock"]),
            d["name"].strip(),
            int(d["delivery_days"]),
        ),
    )
    audit("supplier", cur.lastrowid, "create", f"{d['name']} / {d['fruit']}")
    db().commit()
    return jsonify({"id": cur.lastrowid}), 201


@app.route("/api/suppliers/<int:sid>", methods=["PUT"])
@require("suppliers", "write")
def update_supplier(sid):
    d = request.get_json(force=True)
    db().execute(
        "UPDATE suppliers SET fruit=?, purchase_price=?, stock=?, name=?, delivery_days=? "
        "WHERE id=?",
        (
            d["fruit"].strip(),
            float(d["purchase_price"]),
            float(d["stock"]),
            d["name"].strip(),
            int(d["delivery_days"]),
            sid,
        ),
    )
    audit("supplier", sid, "update", f"{d['name']} / {d['fruit']}")
    db().commit()
    return jsonify({"ok": True})


@app.route("/api/suppliers/<int:sid>", methods=["DELETE"])
@require("suppliers", "write")
def delete_supplier(sid):
    db().execute("DELETE FROM suppliers WHERE id=?", (sid,))
    audit("supplier", sid, "delete")
    db().commit()
    return jsonify({"ok": True})


# ----------------------------------------------------------------------------
# Заказы (Таблица 2). Создание/изменение прогоняет алгоритм подбора.
# ----------------------------------------------------------------------------
def _order_to_dict(row):
    o = dict(row)
    if o.get("supplier_id"):
        s = (
            db()
            .execute("SELECT name FROM suppliers WHERE id=?", (o["supplier_id"],))
            .fetchone()
        )
        o["supplier_name"] = s["name"] if s else None
    else:
        o["supplier_name"] = None
    return o


@app.route("/api/orders")
@require("orders", "read")
def list_orders():
    rows = db().execute("SELECT * FROM orders ORDER BY id").fetchall()
    return jsonify([_order_to_dict(r) for r in rows])


@app.route("/api/orders", methods=["POST"])
@require("orders", "write")
def create_order():
    d = request.get_json(force=True)
    restaurant = d["restaurant"].strip()
    fruit = d["fruit"].strip()
    quantity = float(d["quantity"])
    order_date = d["order_date"]
    client_due = d["client_due_date"]

    res = run_algorithm_for_order(restaurant, fruit, quantity, order_date, client_due)

    cur = db().execute(
        "INSERT INTO orders (restaurant, fruit, quantity, sale_price, order_sum, "
        "order_date, client_due_date, status, supplier_id, purchase_price, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            restaurant,
            fruit,
            quantity,
            res["sale_price"],
            res["order_sum"],
            order_date,
            client_due,
            res["status"],
            res["supplier_id"],
            res["purchase_price"],
            res["reason"],
        ),
    )
    oid = cur.lastrowid

    # Правило 4: списываем склад выбранного поставщика.
    if res["status"] == algorithm.STATUS_MATCHED:
        db().execute(
            "UPDATE suppliers SET stock = stock - ? WHERE id = ?",
            (quantity, res["supplier_id"]),
        )

    audit(
        "order",
        oid,
        "create",
        f"{restaurant} / {fruit} / {quantity}кг -> {res['status']}",
    )
    db().commit()
    return jsonify({"id": oid, "result": res}), 201


@app.route("/api/orders/<int:oid>", methods=["PUT"])
@require("orders", "write")
def update_order(oid):
    """Редактирование заказа: возвращаем ранее списанный склад и пересчитываем заново."""
    d = request.get_json(force=True)
    old = db().execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not old:
        return jsonify({"error": "Заказ не найден"}), 404

    # Вернуть склад прежнему поставщику, если он был выбран.
    if old["supplier_id"] and old["status"] == algorithm.STATUS_MATCHED:
        db().execute(
            "UPDATE suppliers SET stock = stock + ? WHERE id = ?",
            (old["quantity"], old["supplier_id"]),
        )

    restaurant = d["restaurant"].strip()
    fruit = d["fruit"].strip()
    quantity = float(d["quantity"])
    order_date = d["order_date"]
    client_due = d["client_due_date"]

    res = run_algorithm_for_order(restaurant, fruit, quantity, order_date, client_due)

    db().execute(
        "UPDATE orders SET restaurant=?, fruit=?, quantity=?, sale_price=?, order_sum=?, "
        "order_date=?, client_due_date=?, status=?, supplier_id=?, purchase_price=?, reason=? "
        "WHERE id=?",
        (
            restaurant,
            fruit,
            quantity,
            res["sale_price"],
            res["order_sum"],
            order_date,
            client_due,
            res["status"],
            res["supplier_id"],
            res["purchase_price"],
            res["reason"],
            oid,
        ),
    )
    if res["status"] == algorithm.STATUS_MATCHED:
        db().execute(
            "UPDATE suppliers SET stock = stock - ? WHERE id = ?",
            (quantity, res["supplier_id"]),
        )

    audit("order", oid, "update", f"{restaurant} / {fruit} -> {res['status']}")
    db().commit()
    return jsonify({"ok": True, "result": res})


@app.route("/api/orders/<int:oid>", methods=["DELETE"])
@require("orders", "write")
def delete_order(oid):
    old = db().execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if old and old["supplier_id"] and old["status"] == algorithm.STATUS_MATCHED:
        # Вернуть склад при удалении заказа.
        db().execute(
            "UPDATE suppliers SET stock = stock + ? WHERE id = ?",
            (old["quantity"], old["supplier_id"]),
        )
    db().execute("DELETE FROM orders WHERE id=?", (oid,))
    audit("order", oid, "delete")
    db().commit()
    return jsonify({"ok": True})


# ----------------------------------------------------------------------------
# Финансы. Доступ зависит от роли.
#   manager -> 'orders': только финансы по заказам (без общих итогов компании).
#   director -> 'full':  полная сводка (итоги + по фруктам + по клиентам).
# ----------------------------------------------------------------------------
@app.route("/api/finance")
@login_required
def finance():
    user = current_user()
    perm = ROLE_PERMS[user["role"]]["finance"]
    if perm == "none":
        return jsonify({"error": "Недостаточно прав"}), 403

    matched = (
        db()
        .execute("SELECT * FROM orders WHERE status = ?", (algorithm.STATUS_MATCHED,))
        .fetchall()
    )

    per_order = []
    for o in matched:
        revenue = o["order_sum"] or 0
        cost = (o["purchase_price"] or 0) * o["quantity"]
        per_order.append(
            {
                "id": o["id"],
                "restaurant": o["restaurant"],
                "fruit": o["fruit"],
                "quantity": o["quantity"],
                "revenue": round(revenue, 2),
                "profit": round(revenue - cost, 2),
            }
        )

    payload = {"scope": perm, "per_order": per_order}

    # Полная сводка компании — только руководителю.
    if perm == "full":
        total_revenue = sum(po["revenue"] for po in per_order)
        total_profit = sum(po["profit"] for po in per_order)

        by_fruit = _aggregate(per_order, "fruit")
        by_client = _aggregate(per_order, "restaurant")

        payload.update(
            {
                "total_revenue": round(total_revenue, 2),
                "total_profit": round(total_profit, 2),
                "orders_count": len(per_order),
                "by_fruit": by_fruit,
                "by_client": by_client,
            }
        )

    return jsonify(payload)


def _aggregate(per_order, key):
    acc = {}
    for po in per_order:
        k = po[key]
        a = acc.setdefault(k, {"key": k, "revenue": 0.0, "profit": 0.0, "count": 0})
        a["revenue"] += po["revenue"]
        a["profit"] += po["profit"]
        a["count"] += 1
    for a in acc.values():
        a["revenue"] = round(a["revenue"], 2)
        a["profit"] = round(a["profit"], 2)
    return sorted(acc.values(), key=lambda x: x["profit"], reverse=True)


# ----------------------------------------------------------------------------
# История изменений (бонус). Видит руководитель.
# ----------------------------------------------------------------------------
@app.route("/api/audit")
@login_required
def audit_list():
    user = current_user()
    if user["role"] != "director":
        return jsonify({"error": "Недостаточно прав"}), 403
    rows = db().execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200").fetchall()
    return jsonify([dict(r) for r in rows])


# ----------------------------------------------------------------------------
# Справочник фруктов (для выпадающих списков на фронте).
# ----------------------------------------------------------------------------
@app.route("/api/fruits")
@login_required
def fruits():
    rows = (
        db().execute("SELECT DISTINCT fruit FROM suppliers ORDER BY fruit").fetchall()
    )
    return jsonify([r["fruit"] for r in rows])


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
