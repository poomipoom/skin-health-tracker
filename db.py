import sqlite3

conn = sqlite3.connect('user_data.db')
c = conn.cursor()

# สร้างตารางสำหรับเก็บข้อมูล
c.execute('''
CREATE TABLE IF NOT EXISTS userdata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT,
    last_name TEXT,
    gender TEXT,
    product TEXT,
    acne_count INTEGER,
    wrinkle_count INTEGER,
    darkcircle_count INTEGER,
    blackhead_count INTEGER,
    whitehead_count INTEGER,
    skin_type TEXT,
    timestamp DATETIME
);

''')

conn.commit()
conn.close()
