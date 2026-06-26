from logic.database import create_user, verify_user_login, store_scan_log, get_user_scan_history, init_db
import os


def debug_isolation():
    init_db()
    
    # 1. Create two test users
    u1_email = "user1_test@example.com"
    u2_email = "user2_test@example.com"
    
    print(f"Creating/Checking {u1_email}...")
    create_user("user1", u1_email, "pass")
    print(f"Creating/Checking {u2_email}...")
    create_user("user2", u2_email, "pass")
    
    # 2. Get their IDs
    s1, user1 = verify_user_login(u1_email, "pass")
    s2, user2 = verify_user_login(u2_email, "pass")
    
    if not user1 or not user2:
        print("Failed to get users.")
        return
        
    id1, id2 = user1['id'], user2['id']
    print(f"User 1 ID: {id1}, User 2 ID: {id2}")
    
    # 3. Store history for User 1
    print(f"Storing history for User 1 (ID: {id1})...")
    store_scan_log("url", 0.5, "warning", identifier="user1-private-site.com", user_id=id1)
    
    # 4. Check if User 2 can see it
    print(f"Checking history for User 2 (ID: {id2})...")
    history2 = get_user_scan_history(id2)
    leaked = [h for h in history2 if h['identifier'] == "user1-private-site.com"]
    
    if leaked:
        print("!!! BUG DETECTED: User 2 sees User 1's history!")
        print(f"Leaked data: {leaked}")
    else:
        print("Isolation test 1 passed: User 2 cannot see User 1's specific history item.")

    # 5. Check if search for NULL leaks any
    print("Checking if passing None (NULL) leaks history...")
    history_null = get_user_scan_history(None)
    if any(h['identifier'] == "user1-private-site.com" for h in history_null):
        print("!!! BUG DETECTED: Passing None leaks User 1's history!")
    else:
        print("Isolation test 2 passed: Passing None does not leak specific history.")

if __name__ == "__main__":
    debug_isolation()
