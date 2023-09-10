import requests
import random
import json

# Генерация случайного числа для заказов
def generate_order_id():
    return ''.join(random.choice('1234567890') for _ in range(6))

# Генерация случайной даты для заказов
def generate_order_date():
    year = random.randint(2020, 2023)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"

# Список данных для 5 не похожих заказов
orders = [
    {
        "customer_name": "Ivan Ivanov",
        "product": "Chandelier",
        "created_at": "2023-01-15T10:30:00Z",
        "dmn": "example.com",
        "oid": 12345,
        "uid": 567,
        "dt": "2023-01-15T10:30:00Z",
        "ip": "192.168.1.1",
        "itm": ["Chandelier", "Carpet"],
        "pmt": "Credit Card",
        "amt": 200.50,
        "shp": {
            "street": "Pushkin St.",
            "house_number": "10",
            "city": "Moscow"
        },
        "eml": "ivan@example.com",
        "tel": "+1234567890",
        "addr": "Pushkin St., Moscow",
        "note": "Special instructions",
        "cur": "USD",
        "sts": "Pending",
    },
    {
        "customer_name": "Anna Smirnova",
        "product": "Table",
        "created_at": "2023-02-20T14:15:00Z",
        "dmn": "example.com",
        "oid": 67890,
        "uid": 789,
        "dt": "2023-02-20T14:15:00Z",
        "ip": "192.168.2.2",
        "itm": ["Table", "Chairs"],
        "pmt": "PayPal",
        "amt": 350.75,
        "shp": {
            "street": "Lenin Ave.",
            "house_number": "5",
            "city": "St. Petersburg"
        },
        "eml": "anna@example.com",
        "tel": "+9876543210",
        "addr": "Lenin Ave., St. Petersburg",
        "note": "No rush",
        "cur": "EUR",
        "sts": "Shipped",
    },
]

# Отправка заказов
for order in orders:
    url = "http://127.0.0.1:5000/api/post/UGUPCDUBAFZW"
    response = requests.post(url, json=order, headers={"Content-Type": "application/json; charset=utf-8"})
    print(f"Response Code: {response.status_code}")
    print(response.text)
    print("\n")
