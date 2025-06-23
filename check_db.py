import sqlite3

def check_database():
    try:
        conn = sqlite3.connect('user.db')
        cursor = conn.cursor()
        
        print("=== Users in Database ===")
        cursor.execute("SELECT id, email, name, role FROM users")
        users = cursor.fetchall()
        if users:
            for user in users:
                print(f"ID: {user[0]}, Email: {user[1]}, Name: {user[2]}, Role: {user[3]}")
        else:
            print("No users found in database")
            
        print("\n=== Database Tables ===")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for table in tables:
            print(f"Table: {table[0]}")
            cursor.execute(f"PRAGMA table_info({table[0]})")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  Column: {col[1]} ({col[2]})")
                
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_database() 