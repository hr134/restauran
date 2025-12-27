"""
Database Migration Script for ERP Integration
This script creates the new ERP tables and migrates existing data
"""

from app import app, db
from models.models import User, MenuItem, Order, SaleItem, Employee, Attendance
from datetime import datetime, date
import json

def migrate_database():
    """Create new tables and migrate existing data"""
    with app.app_context():
        print("Starting ERP database migration...")
        
        # Create all tables (will only create new ones)
        db.create_all()
        print("[OK] Database tables created/verified")
        
        # Migrate existing orders to create SaleItem records
        print("\nMigrating existing orders to SaleItem records...")
        orders = Order.query.all()
        migrated_count = 0
        
        for order in orders:
            # Check if this order already has sale_items
            existing_items = SaleItem.query.filter_by(order_id=order.id).first()
            if existing_items:
                continue  # Skip if already migrated
            
            try:
                # Parse items from order
                if order.items_parsed:
                    items_data = order.items_parsed
                elif order.items:
                    items_data = json.loads(order.items)
                else:
                    continue
                
                # Create SaleItem for each item in the order
                for item_name, quantity in items_data.items():
                    # Find the menu item
                    menu_item = MenuItem.query.filter_by(name=item_name).first()
                    if menu_item:
                        sale_item = SaleItem(
                            order_id=order.id,
                            menu_item_id=menu_item.id,
                            quantity=quantity,
                            price_at_sale=menu_item.price
                        )
                        db.session.add(sale_item)
                        migrated_count += 1
                
            except Exception as e:
                print(f"  Warning: Could not migrate order {order.id}: {str(e)}")
                continue
        
        db.session.commit()
        print(f"[OK] Migrated {migrated_count} order items to SaleItem records")
        
        # Create sample employee records for existing staff
        print("\nCreating sample employee records...")
        staff_users = User.query.filter(User.role.in_(['chef', 'waiter', 'cashier', 'admin'])).all()
        employee_count = 0
        
        for user in staff_users:
            # Check if employee record already exists
            if hasattr(user, 'employee_record') and user.employee_record:
                continue
            
            # Create employee record
            position_map = {
                'chef': 'Head Chef',
                'waiter': 'Server',
                'cashier': 'Cashier',
                'admin': 'Manager'
            }
            
            employee = Employee(
                user_id=user.id,
                position=position_map.get(user.role, 'Staff'),
                department='Kitchen' if user.role == 'chef' else 'Service',
                salary=30000.00,  # Default salary
                hire_date=user.created_at.date() if user.created_at else date.today(),
                status='active'
            )
            db.session.add(employee)
            employee_count += 1
        
        db.session.commit()
        print(f"[OK] Created {employee_count} employee records")
        
        # Verify migration
        print("\n=== Migration Summary ===")
        print(f"Total Users: {User.query.count()}")
        print(f"Total Menu Items: {MenuItem.query.count()}")
        print(f"Total Orders: {Order.query.count()}")
        print(f"Total Sale Items: {SaleItem.query.count()}")
        print(f"Total Employees: {Employee.query.count()}")
        print(f"Total Attendance Records: {Attendance.query.count()}")
        
        print("\n[OK] Migration completed successfully!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Run the application: python app.py")
        print("3. Login as admin and test the new ERP features")

if __name__ == '__main__':
    try:
        migrate_database()
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
