import psycopg2
import os

POSTGRES_DB = "alisa"
POSTGRES_USER = "str"
POSTGRES_PASSWORD = "str"
POSTGRES_HOST = "localhost"

def connect_db():
    return psycopg2.connect(
        dbname=POSTGRES_DB,   # Имя базы данных
        user=POSTGRES_USER,   # Имя пользователя
        password=POSTGRES_PASSWORD, # Пароль
        host=POSTGRES_HOST    # Хост
    )

def initialize():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS tokens (
        token TEXT PRIMARY KEY,
        username TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT,
        bot_token TEXT,
        FOREIGN KEY (bot_token) REFERENCES tokens(token)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        name TEXT PRIMARY KEY,
        text  TEXT
    )''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_details (
            type TEXT PRIMARY KEY,
            details TEXT,
            photo_path TEXT,
            status BOOLEAN DEFAULT FALSE,
            coefficient REAL DEFAULT 1.0
        )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_mailings (
        id SERIAL PRIMARY KEY,
        time TEXT,
        text TEXT,
        photo_path TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS cities (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name TEXT,
        city_id INTEGER,
        FOREIGN KEY (city_id) REFERENCES cities(id)
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS product_details (
        id SERIAL PRIMARY KEY,
        product_id INTEGER,
        klad_type TEXT,
        price REAL,
        districts TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')

    cursor.execute("INSERT INTO payment_details (type, details) VALUES ('card', 'Пока не установлено.') ON CONFLICT DO NOTHING")
    cursor.execute("INSERT INTO payment_details (type, details) VALUES ('sbp', 'Пока не установлено.') ON CONFLICT DO NOTHING")
    cursor.execute("INSERT INTO payment_details (type, details) VALUES ('btc', 'Пока не установлено.') ON CONFLICT DO NOTHING")
    cursor.execute("INSERT INTO payment_details (type, details) VALUES ('ltc', 'Пока не установлено.') ON CONFLICT DO NOTHING")

    cursor.execute("INSERT INTO settings (name, text) VALUES ('help', 'https://t.me/durov') ON CONFLICT DO NOTHING")
    cursor.execute("INSERT INTO settings (name, text) VALUES ('operator_link', 'https://t.me/durov') ON CONFLICT DO NOTHING")
    cursor.execute("INSERT INTO settings (name, text) VALUES ('work_link', 'https://t.me/durov') ON CONFLICT DO NOTHING")
    cursor.execute("INSERT INTO settings (name, text) VALUES ('out_site', 'https://telegram.org/') ON CONFLICT DO NOTHING")

    conn.commit()
    conn.close()

def add_city_if_not_exists(city_name):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM cities WHERE name = %s", (city_name,))
    result = cursor.fetchone()
    if result:
        city_id = result[0]
    else:
        cursor.execute("INSERT INTO cities (name) VALUES (%s) RETURNING id", (city_name,))
        city_id = cursor.fetchone()[0]
        conn.commit()
    cursor.close()
    conn.close()
    return city_id

def clear_database():
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS product_details, products, categories, cities, daily_mailings, payment_details, crypto_prices, settings, users, tokens CASCADE")
            conn.commit()

def get_products_by_city(city_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM products WHERE city_id = %s", (city_id,))
    return cursor.fetchall()

def add_product(product_name, city_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM products WHERE name = %s AND city_id = %s", (product_name, city_id))
    result = cursor.fetchone()
    if result:
        product_id = result[0]
    else:
        cursor.execute("INSERT INTO products (name, city_id) VALUES (%s, %s) RETURNING id", (product_name, city_id))
        product_id = cursor.fetchone()[0]
        conn.commit()
    cursor.close()
    conn.close()
    return product_id

def get_total_users_count():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]

def get_users_count_of_bot(bot_token):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE bot_token = %s", (bot_token,))
    return cursor.fetchone()[0]

def delete_city(city_id):
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM cities WHERE id = %s", (city_id,))
    conn.commit()

def delete_product(product_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM product_details WHERE product_id = %s", (product_id,))
    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
    conn.commit()

def get_payment_coefficient(payment_type):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT coefficient FROM payment_details WHERE type = %s", (payment_type,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else 1.0

def set_payment_coefficient(payment_type, new_coefficient):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE payment_details SET coefficient = %s WHERE type = %s", (new_coefficient, payment_type))
    conn.commit()
    cursor.close()
    conn.close()

def get_full_database_info():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cities")
    cities_info = cursor.fetchall()
    cities_output = ["Города:"] + [f"ID: {city[0]}, Название: {city[1]}" for city in cities_info]

    cursor.execute("SELECT * FROM products")
    products_info = cursor.fetchall()
    products_output = ["Товары:"] + [f"ID: {prod[0]}, Название: {prod[1]}, Город ID: {prod[2]}" for prod in products_info]

    cursor.execute('''
        SELECT p.id, p.name, pd.klad_type
        FROM products p
        JOIN product_details pd ON p.id = pd.product_id
    ''')
    product_details_info = cursor.fetchall()
    product_details_output = ["Детали товаров:"] + [f"ID товара: {detail[0]}, Название: {detail[1]}, Тип клада: {detail[2]}" for detail in product_details_info]

    full_info = "\n".join(cities_output + products_output + product_details_output)
    
    return full_info

def add_product_details(product_id, klad_type, price, districts):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, klad_type FROM product_details WHERE product_id = %s AND price = %s AND districts = %s", (product_id, price, districts))
    result = cursor.fetchone()
    if result:
        detail_id, existing_klad_type = result
        if klad_type not in existing_klad_type.split(','):
            new_klad_type = existing_klad_type + ',' + klad_type
            cursor.execute("UPDATE product_details SET klad_type = %s WHERE id = %s", (new_klad_type, detail_id))
    else:
        cursor.execute("INSERT INTO product_details (product_id, klad_type, price, districts) VALUES (%s, %s, %s, %s)", (product_id, klad_type, price, districts))
    conn.commit()

def get_product_details(product_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT klad_type, price, districts FROM product_details WHERE product_id = %s", (product_id,))
    return cursor.fetchall()

def get_cities():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cities")
    return cursor.fetchall()

def get_product_price(product_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT price FROM product_details WHERE product_id = %s", (product_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_operator_link():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM settings WHERE name = 'operator_link'")
    return cursor.fetchone()[0]

def set_operator_link(new_text):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET text = %s WHERE name = 'operator_link'", (new_text,))
    conn.commit()

def get_city_name(city_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM cities WHERE id = %s", (city_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_work_link():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM settings WHERE name = 'work_link'")
    return cursor.fetchone()[0]

def set_work_link(new_text):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET text = %s WHERE name = 'work_link'", (new_text,))
    conn.commit()

def get_site():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM settings WHERE name = 'out_site'")
    return cursor.fetchone()[0]

def set_site(new_text):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET text = %s WHERE name = 'out_site'", (new_text,))
    conn.commit()


def get_product_name(product_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM products WHERE id = %s", (product_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def add_daily_mailing(time, text, photo_path):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO daily_mailings (time, text, photo_path) VALUES (%s, %s, %s)",
                   (time, text, photo_path))
    conn.commit()

def delete_daily_mailing(id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM daily_mailings WHERE id = %s", (id,))
    conn.commit()

def get_daily_mailings():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_mailings")
    return cursor.fetchall()

def get_daily_mailing_by_id(id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_mailings WHERE id = %s", (id,))
    return cursor.fetchone()

def add_token(token, username):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tokens (token, username) VALUES (%s, %s)", (token, username))
    conn.commit()

def delete_token(token):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tokens WHERE token = %s", (token,))
    conn.commit()

def get_tokens():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT token, username FROM tokens")
    return cursor.fetchall()

def get_bot_data(token):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, token FROM tokens WHERE token = %s", (token,))
    return cursor.fetchone()

def add_user(user_id, bot_token):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id, bot_token) VALUES (%s, %s)", (user_id, bot_token))
    conn.commit()

def get_users_by_token(bot_token):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE bot_token = %s", (bot_token,))
    return cursor.fetchall()

def check_user_exists(user_id, bot_token):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = %s AND bot_token = %s", (user_id, bot_token))
    return cursor.fetchone() is not None

def get_help_text():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM settings WHERE name = 'help'")
    return cursor.fetchone()[0]

def set_help_text(new_text):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET text = %s WHERE name = 'help'", (new_text,))
    conn.commit()

def get_preorder_text():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM settings WHERE name = 'preorder'")
    return cursor.fetchone()[0]

def set_preorder_text(new_text):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET text = %s WHERE name = 'preorder'", (new_text,))
    conn.commit()

def get_payment_details(payment_type):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT details, photo_path FROM payment_details WHERE type = %s", (payment_type,))
    row = cursor.fetchone()
    return (row[0], row[1]) if row else ("Реквизиты не найдены.", None)

def set_payment_details(payment_type, new_text):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE payment_details SET details = %s WHERE type = %s", (new_text, payment_type))
    conn.commit()

def get_payment_methods():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT type, details, photo_path FROM payment_details")
    methods = cursor.fetchall()
    return methods

def get_enabled_payment_methods():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT type, details, photo_path FROM payment_details WHERE status = TRUE")
    methods = cursor.fetchall()
    return methods

def set_payment_method_status(payment_type, new_status):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE payment_details SET status = %s WHERE type = %s", (new_status, payment_type))
    conn.commit()

def set_payment_photo(payment_type, photo_path):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE payment_details SET photo_path = %s WHERE type = %s", (photo_path, payment_type))
    conn.commit()

def get_payment_method_status(payment_type):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM payment_details WHERE type = %s", (payment_type,))
    row = cursor.fetchone()
    return row[0] if row else False
