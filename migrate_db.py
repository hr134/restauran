"""
Database Migration Script
Adds reset_token, reset_token_expiry, email_verified, and email_verification_code columns to User table
"""
import sqlite3
import os

# Path to database
db_path = os.path.join('instance', 'restaurant.db')

if not os.path.exists(db_path):
    print(f"[ERROR] Database not found at {db_path}")
    print("The database will be created automatically when you run app.py")
    exit(1)

try:
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(user)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Add reset_token column if it doesn't exist
    if 'reset_token' not in columns:
        print("Adding reset_token column...")
        cursor.execute("ALTER TABLE user ADD COLUMN reset_token VARCHAR(100)")
        print("[SUCCESS] reset_token column added")
    
    # Add reset_token_expiry column if it doesn't exist
    if 'reset_token_expiry' not in columns:
        print("Adding reset_token_expiry column...")
        cursor.execute("ALTER TABLE user ADD COLUMN reset_token_expiry DATETIME")
        print("[SUCCESS] reset_token_expiry column added")

    # Add email_verified column if it doesn't exist
    if 'email_verified' not in columns:
        print("Adding email_verified column...")
        cursor.execute("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0")
        print("[SUCCESS] email_verified column added")

    # Add email_verification_code column if it doesn't exist
    if 'email_verification_code' not in columns:
        print("Adding email_verification_code column...")
        cursor.execute("ALTER TABLE user ADD COLUMN email_verification_code VARCHAR(10)")
        print("[SUCCESS] email_verification_code column added")

    # Add created_at column if it doesn't exist
    if 'created_at' not in columns:
        print("Adding created_at column...")
        cursor.execute("ALTER TABLE user ADD COLUMN created_at DATETIME")
        
        # Set default value for existing rows (current time)
        from datetime import datetime
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(f"UPDATE user SET created_at = '{now}' WHERE created_at IS NULL")
        
        print("[SUCCESS] created_at column added")

    # Add member_id column if it doesn't exist
    if 'member_id' not in columns:
        print("Adding member_id column...")
        cursor.execute("ALTER TABLE user ADD COLUMN member_id VARCHAR(20)")
        
        # Generate member_id for existing users
        print("Generating member_ids for existing users...")
        cursor.execute("SELECT id FROM user")
        users = cursor.fetchall()
        import random
        for u in users:
            uid = u[0]
            # Format: 75 + 2 random digits + id
            mid = f"75{random.randint(10, 99)}{uid}"
            cursor.execute(f"UPDATE user SET member_id = '{mid}' WHERE id = {uid}")
            
        print("[SUCCESS] member_id column added and populated")

    # [SRS Update] Add role column to User
    if 'role' not in columns:
        print("Adding role column to User...")
        cursor.execute("ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'customer'")
        print("[SUCCESS] role column added")

    # Check MenuItem table
    cursor.execute("PRAGMA table_info(menu_item)")
    menu_columns = [col[1] for col in cursor.fetchall()]
    
    if 'stock_quantity' not in menu_columns:
        print("Adding stock_quantity to MenuItem...")
        cursor.execute("ALTER TABLE menu_item ADD COLUMN stock_quantity INTEGER DEFAULT 0")
        print("[SUCCESS] stock_quantity added")

    if 'low_stock_threshold' not in menu_columns:
        print("Adding low_stock_threshold to MenuItem...")
        cursor.execute("ALTER TABLE menu_item ADD COLUMN low_stock_threshold INTEGER DEFAULT 5")
        print("[SUCCESS] low_stock_threshold added")

    # Rename 'order' to 'orders' if necessary
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
    orders_exists = cursor.fetchone()
    
    if not orders_exists:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order'")
        order_exists = cursor.fetchone()
        if order_exists:
            print("Renaming table 'order' to 'orders'...")
            # Use quoted "order" just in case
            cursor.execute('ALTER TABLE "order" RENAME TO orders')
            print("[SUCCESS] Table renamed to 'orders'")
        else:
            # Neither exists? logic for creating new table belongs to db.create_all(), but we are migrating.
            pass

    # Check Orders table (now normalized to 'orders')
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
    orders_exists = cursor.fetchone()
    
    if orders_exists:
        cursor.execute("PRAGMA table_info(orders)") 
        order_columns = [col[1] for col in cursor.fetchall()]

        if 'payment_status' not in order_columns:
            print("Adding payment_status to orders...")
            cursor.execute("ALTER TABLE orders ADD COLUMN payment_status VARCHAR(20) DEFAULT 'pending'")
            print("[SUCCESS] payment_status added")
        
        if 'payment_method' not in order_columns:
             print("Adding payment_method to orders...")
             cursor.execute("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(20)")
             print("[SUCCESS] payment_method added")

        if 'discount' not in order_columns:
             print("Adding discount to orders...")
             cursor.execute("ALTER TABLE orders ADD COLUMN discount FLOAT DEFAULT 0.0")
             print("[SUCCESS] discount added")

        if 'order_type' not in order_columns:
             print("Adding order_type to orders...")
             cursor.execute("ALTER TABLE orders ADD COLUMN order_type VARCHAR(20) DEFAULT 'dine_in'")
             print("[SUCCESS] order_type added")

    # [SRS Update] Create Missing Tables
    print("Checking for missing SRS tables...")
    

    # StaffShift Table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff_shift'")
    if not cursor.fetchone():
        print("Creating 'staff_shift' table...")
        cursor.execute("""
            CREATE TABLE staff_shift (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                shift_start DATETIME NOT NULL,
                shift_end DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        """)
        print("[SUCCESS] 'staff_shift' table created")

    # ReportLog Table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='report_log'")
    if not cursor.fetchone():
        print("Creating 'report_log' table...")
        cursor.execute("""
            CREATE TABLE report_log (
                id INTEGER PRIMARY KEY,
                report_type VARCHAR(50) NOT NULL,
                generated_at DATETIME,
                report_metadata TEXT
            )
        """)
        print("[SUCCESS] 'report_log' table created")
    else:
        # Check if metadata column needs renaming (we used report_metadata in model)
        cursor.execute("PRAGMA table_info(report_log)")
        report_cols = [col[1] for col in cursor.fetchall()]
        if 'metadata' in report_cols and 'report_metadata' not in report_cols:
             print("Renaming 'metadata' to 'report_metadata' in report_log...")
             # SQLite doesn't support RENAME COLUMN in older versions easily, but 3.25.0+ does
             try:
                 cursor.execute("ALTER TABLE report_log RENAME COLUMN metadata TO report_metadata")
                 print("[SUCCESS] Column renamed")
             except:
                 print("[WARNING] Could not rename column, might be older SQLite version. Skipping.")

    # Commit changes
    conn.commit()
    print("\n[SUCCESS] Database migration completed successfully!")
    print("You can now run the application with: python app.py")
    
    # Close connection
    conn.close()
    
except sqlite3.Error as e:
    print(f"[ERROR] Database error: {e}")
    exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    exit(1)
