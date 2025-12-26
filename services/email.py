from flask import current_app
from flask_mail import Message
from extensions import mail
import threading
import json
from datetime import datetime

def send_email(subject, recipient, body):
    """Helper to send emails with a timed wait to prevent request timeouts."""
    if not recipient or '@' not in recipient:
        print(f"Skipping email to invalid recipient: {recipient}")
        return False
        
    result = {"status": "failed"}

    def _do_send(app_context):
        with app_context:
            try:
                msg = Message(subject, recipients=[recipient])
                msg.body = body
                mail.send(msg)
                result["status"] = "success"
                print(f"Email sent to {recipient}")
            except Exception as e:
                with open("email_errors.log", "a") as f:
                    f.write(f"[{datetime.now()}] Email error to {recipient}: {str(e)}\n")
                print(f"Email error: {e}")
                result["status"] = "failed"
                
    # Capture app context explicitly for the thread
    # Note: access current_app._get_current_object() to get true app object
    app = current_app._get_current_object()
    ctx = app.app_context()
    thread = threading.Thread(target=_do_send, args=(ctx,))
    thread.start()
    
    # Wait for up to 5 seconds. Fast enough for Render's request cycle.
    thread.join(timeout=5)
    
    if thread.is_alive():
        print(f"Email to {recipient} timed out locally, continuing in background.")
        return "pending"
    
    return True if result["status"] == "success" else False

def format_order_body(order):
    """Helper to format order items for email."""
    try:
        items = json.loads(order.items)
        item_lines = []
        for i in items:
            # Handle potential missing keys if schema changed
            name = i.get('name', 'Unknown Item')
            qty = i.get('qty', 1)
            price = i.get('price', 0)
            item_lines.append(f"- {name} x {qty} : ${price * qty:.2f}")
        
        details = "\n".join(item_lines)
        return f"""Order #{order.unique_order_number} Details:
Placed on: {order.created_at.strftime('%Y-%m-%d %H:%M')}
{details}

Total: ${order.total:.2f}
Address: {order.address_street}, {order.address_city}
Phone: {order.phone}
"""
    except Exception as e:
        return f"Order Details: (Error parsing items: {str(e)})"
