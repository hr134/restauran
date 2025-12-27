from app import app
from models.models import db, EmployeeRequest

def migrate():
    with app.app_context():
        try:
            print("Creating all tables (including EmployeeRequest)...")
            db.create_all()
            
            # Check if hire_date column exists in employee_request
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('employee_request')]
            
            if 'hire_date' not in columns:
                print("Adding 'hire_date' column to 'employee_request'...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE employee_request ADD COLUMN hire_date DATE'))
                    conn.commit()
                print("Successfully added 'hire_date' column.")
            else:
                print("'hire_date' column already exists.")
                
            print("Successfully migrated database.")
        except Exception as e:
            print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
