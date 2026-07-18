# database.py
import sqlite3
import json

DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT,
            description TEXT,
            price REAL,
            image_id TEXT,
            is_available INTEGER DEFAULT 1,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart (
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            PRIMARY KEY (user_id, product_id)
        )
    ''')

    # Инициализация категорий со стильными эмодзи для меню кондитера
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ("🧁 Трайфлы",), 
            ("🍰 Пирожные",), 
            ("🎂 Торты",), 
            ("🧺 Корзинки",)
        ]
        cursor.executemany("INSERT INTO categories (name) VALUES (?)", default_categories)
        
    conn.commit()
    conn.close()

def get_categories():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_products_by_category(category_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, price, image_id FROM products WHERE category_id = ? AND is_available = 1", (category_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_product_by_id(product_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, price, image_id FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def add_product(category_id, name, description, price, image_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (category_id, name, description, price, image_id) VALUES (?, ?, ?, ?, ?)",
        (category_id, name, description, price, image_id)
    )
    conn.commit()
    conn.close()
    
    # Сразу обновляем JSON витрины
    export_products_to_json()

def add_to_cart(user_id, product_id, quantity=1):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
    row = cursor.fetchone()
    if row:
        new_qty = row[0] + quantity
        cursor.execute("UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?", (new_qty, user_id, product_id))
    else:
        cursor.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)", (user_id, product_id, quantity))
    conn.commit()
    conn.close()

def get_cart(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.name, p.price, c.quantity 
        FROM cart c 
        JOIN products p ON c.product_id = p.id 
        WHERE c.user_id = ?
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def clear_cart(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

import os  # Убедитесь, что эта строчка есть в самом верху файла database.py

def export_products_to_json():
    """Выгружает все доступные товары из БД в файл products.json и автоматически отправляет на Vercel"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.id, p.name, p.description, p.price, p.image_id, c.name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_available = 1
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    products_list = []
    for row in rows:
        products_list.append({
            "id": row[0],
            "name": row[1],
            "description": row[2] if row[2] else "",
            "price": row[3],
            "image_url": row[4],  
            "category": row[5] if row[5] else "✨ Разное"
        })
        
    # Записываем обновленный список в файл
    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(products_list, f, ensure_ascii=False, indent=4)
        
    # 🔥 АВТОМАТИЧЕСКИЙ СИНХРОН С ВЕРСЕЛ ПРЯМО ИЗ БОТА
    print("✨ Обнаружено изменение меню! Отправляем на Vercel...")
    try:
        os.system("git add products.json")
        os.system('git commit -m "Auto-update menu from Telegram Bot"')
        os.system("git push origin main")
        print("🚀 Витрина успешно и мгновенно обновлена в интернете!")
    except Exception as e:
        print(f"❌ Ошибка авто-пуша: {e}")
    
def delete_product_by_id(product_id):
    """Удаляет товар из базы данных по ID и сразу обновляет витрину на Vercel"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    
    # Синхронизируем изменения с сайтом
    export_products_to_json()

def update_product_field(product_id, field_name, new_value):
    """
    Обновляет любое выбранное поле товара (name, price, description, image_id)
    и автоматически отправляет актуальное меню на Vercel.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # field_name подставляется из нашего строгого списка в боте (name, price, description, image_id)
    cursor.execute(f'UPDATE products SET {field_name} = ? WHERE id = ?', (new_value, product_id))
    conn.commit()
    conn.close()
    
    # Синхронизируем изменения с сайтом
    export_products_to_json()


def add_new_category(category_name):
    """Добавляет новую категорию в базу данных, если такой еще нет"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        # Если категория с таким именем уже существует (так как у нас UNIQUE)
        success = False
    conn.close()
    return success

def add_new_category(category_name):
    """Добавляет новую категорию в базу данных, если такой еще нет"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        # Если категория с таким именем уже существует (так как поле UNIQUE)
        success = False
    conn.close()
    return success