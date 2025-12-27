from models.models import Order, MenuItem, ReportLog
from extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta
import json

def generate_daily_sales_report(date_str=None):
    """Generate sales report for a specific day (YYYY-MM-DD).
    Default is today.
    """
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    # query orders for that day
    # Assuming created_at is datetime
    start_of_day = datetime.strptime(date_str, '%Y-%m-%d')
    end_of_day = start_of_day + timedelta(days=1)
    
    orders = Order.query.filter(Order.created_at >= start_of_day, Order.created_at < end_of_day).all()
    
    total_sales = sum(o.total for o in orders)
    order_count = len(orders)
    
    report_data = {
        'date': date_str,
        'total_sales': total_sales,
        'order_count': order_count,
        'orders': [o.unique_order_number for o in orders]
    }
    
    # Log report generation
    log = ReportLog(
        report_type='daily_sales',
        metadata=json.dumps(report_data)
    )
    db.session.add(log)
    db.session.commit()
    
    return report_data

def generate_best_selling_items(limit=5):
    """Return top N best selling items based on order history."""
    # This acts on the 'items' JSON text in Order, which is hard to query purely via SQL if stored as text.
    # However, for a proper implementation, we'd ideally have an OrderItem table. 
    # Since we are sticking to the SRS plan which didn't strictly mandate normalized OrderItem table (though it's better),
    # we might have to parse python side or rely on 'items_parsed' if populated.
    # For performance/SRS compliance, let's stick to a simpler approach or suggest normalization later.
    # We will compute in Python for now if dataset is small, or use a simplified heuristic.
    
    all_orders = Order.query.all()
    item_counts = {}
    
    for o in all_orders:
        try:
            items = json.loads(o.items)
            for i in items:
                # name or id
                name = i.get('name')
                qty = i.get('qty', 0)
                if name:
                    item_counts[name] = item_counts.get(name, 0) + qty
        except:
            continue
            
    sorted_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_items[:limit]
