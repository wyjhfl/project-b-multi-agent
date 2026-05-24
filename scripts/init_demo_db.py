import sqlite3
import os
from datetime import date, timedelta
import random

random.seed(42)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "ops_demo.sqlite")


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            registered_date TEXT NOT NULL,
            channel TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_date TEXT NOT NULL UNIQUE,
            gmv REAL NOT NULL,
            order_count INTEGER NOT NULL,
            active_users INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE refund_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            refund_amount REAL NOT NULL,
            refund_date TEXT NOT NULL,
            reason TEXT NOT NULL
        )
    """)

    categories = ["电子产品", "服装", "食品", "家居", "美妆"]
    product_names = {
        "电子产品": ["蓝牙耳机", "充电宝", "数据线", "手机壳", "智能手环"],
        "服装": ["T恤", "牛仔裤", "运动鞋", "羽绒服", "连衣裙"],
        "食品": ["坚果礼盒", "咖啡豆", "巧克力", "蜂蜜", "茶叶"],
        "家居": ["台灯", "收纳盒", "抱枕", "地毯", "花瓶"],
        "美妆": ["面膜", "防晒霜", "口红", "洗面奶", "精华液"],
    }

    products = []
    pid = 1
    for cat in categories:
        for name in product_names[cat]:
            price = round(random.uniform(29.9, 599.9), 2)
            products.append((pid, name, cat, price))
            pid += 1

    cur.executemany("INSERT INTO products (id, name, category, price) VALUES (?, ?, ?, ?)", products)

    channels = ["微信", "APP", "官网", "抖音", "小红书"]
    users = []
    base_date = date.today()
    for i in range(1, 51):
        reg_date = base_date - timedelta(days=random.randint(0, 60))
        users.append((i, f"user_{i:03d}", reg_date.isoformat(), random.choice(channels)))

    cur.executemany("INSERT INTO users (id, username, registered_date, channel) VALUES (?, ?, ?, ?)", users)

    statuses = ["completed", "completed", "completed", "completed", "pending", "shipped"]
    orders = []
    oid = 1
    for i in range(120):
        user_id = random.randint(1, 50)
        product_id = random.randint(1, len(products))
        quantity = random.randint(1, 3)
        price = products[product_id - 1][3]
        total = round(price * quantity, 2)
        order_date = base_date - timedelta(days=random.randint(0, 30))
        status = random.choice(statuses)
        orders.append((oid, user_id, product_id, quantity, total, order_date.isoformat(), status))
        oid += 1

    cur.executemany("INSERT INTO orders (id, user_id, product_id, quantity, total_amount, order_date, status) VALUES (?, ?, ?, ?, ?, ?, ?)", orders)

    daily_metrics = []
    base_gmv = 100000.0
    for d in range(30):
        metric_date = base_date - timedelta(days=29 - d)
        trend = 1.0 + d * 0.02
        noise = random.uniform(0.9, 1.1)
        gmv = round(base_gmv * trend * noise, 2)
        order_count = int(gmv / random.uniform(120, 180))
        active_users = int(order_count * random.uniform(2.5, 4.0))
        daily_metrics.append((d + 1, metric_date.isoformat(), gmv, order_count, active_users))

    cur.executemany("INSERT INTO daily_metrics (id, metric_date, gmv, order_count, active_users) VALUES (?, ?, ?, ?, ?)", daily_metrics)

    refund_reasons = ["质量问题", "尺寸不符", "不喜欢", "物流损坏", "发错货"]
    refund_orders = []
    for i in range(1, 13):
        order_id = random.randint(1, 120)
        order_data = orders[order_id - 1]
        refund_amount = round(order_data[4] * random.uniform(0.5, 1.0), 2)
        refund_date = base_date - timedelta(days=random.randint(0, 20))
        reason = random.choice(refund_reasons)
        refund_orders.append((i, order_id, refund_amount, refund_date.isoformat(), reason))

    cur.executemany("INSERT INTO refund_orders (id, order_id, refund_amount, refund_date, reason) VALUES (?, ?, ?, ?, ?)", refund_orders)

    conn.commit()
    conn.close()
    print(f"Demo database created at: {os.path.abspath(DB_PATH)}")
    print(f"  products: {len(products)} rows")
    print(f"  users: {len(users)} rows")
    print(f"  orders: {len(orders)} rows")
    print(f"  daily_metrics: {len(daily_metrics)} rows")
    print(f"  refund_orders: {len(refund_orders)} rows")


if __name__ == "__main__":
    init_db()
