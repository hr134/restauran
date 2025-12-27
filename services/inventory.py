from models.models import MenuItem
from extensions import db
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def decrease_stock(item_id, quantity):
    """Decrease stock for a menu item after an order.
    Returns True on success, False if insufficient stock.
    """
    item = MenuItem.query.get(item_id)
    if not item:
        logger.error(f"MenuItem {item_id} not found for stock update.")
        return False
    if item.stock_quantity is None:
        # Treat None as unlimited stock
        return True
    if item.stock_quantity < quantity:
        logger.warning(f"Insufficient stock for item {item.name} (id={item.id}). Requested {quantity}, available {item.stock_quantity}.")
        return False
    item.stock_quantity -= quantity
    db.session.commit()
    # Check low stock threshold
    if item.stock_quantity <= (item.low_stock_threshold or 0):
        logger.info(f"Low stock alert for {item.name}: {item.stock_quantity} remaining.")
        # Here you could trigger email/notification; for now just log.
    return True

def increase_stock(item_id, quantity):
    """Increase stock, e.g., when an order is cancelled.
    """
    item = MenuItem.query.get(item_id)
    if not item:
        logger.error(f"MenuItem {item_id} not found for stock increase.")
        return False
    if item.stock_quantity is None:
        return True
    item.stock_quantity += quantity
    db.session.commit()
    return True
