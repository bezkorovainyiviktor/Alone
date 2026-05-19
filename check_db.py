import sqlite3
import sys

# Force UTF-8 for output
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('instance/petfamily.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

for table_name_tuple in tables:
    table_name = table_name_tuple[0]
    cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
    count = cursor.fetchone()[0]
    print(f"Table {table_name}: {count} rows")
    
    if count > 0:
        print(f"  Sample row from {table_name}:")
        cursor.execute(f"SELECT * FROM [{table_name}] LIMIT 1")
        print(f"  {cursor.fetchone()}")

conn.close()
