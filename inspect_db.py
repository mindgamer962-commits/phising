from logic.database import get_db_connection


def inspect_db():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return
        
    cursor = conn.cursor(dictionary=True)
    
    print("\n--- USERS ---")
    cursor.execute("SELECT id, username, email FROM users")
    users = cursor.fetchall()
    for u in users:
        print(u)
        
    print("\n--- EMAILS ---")
    cursor.execute("SELECT id, user_id, subject, verdict FROM emails LIMIT 10")
    emails = cursor.fetchall()
    for e in emails:
        print(e)
        
    print("\n--- SCAN LOGS ---")
    cursor.execute("SELECT id, user_id, scan_type, identifier, verdict FROM scan_logs LIMIT 10")
    logs = cursor.fetchall()
    for l in logs:
        print(l)
        
    cursor.close()
    conn.close()

if __name__ == "__main__":
    inspect_db()
