from flask import Blueprint, render_template, request, session, jsonify, url_for
from models.models import MenuItem, Reservation, User
from extensions import db
import re
import difflib
from datetime import datetime, timedelta

chatbot_bp = Blueprint('chatbot', __name__)

def get_menu_tool():
    """Returns the full menu as a string."""
    items = MenuItem.query.all()
    if not items:
        return "The menu is currently empty."
    lines = []
    for item in items:
        status = "Available" if item.availability else "Sold Out"
        lines.append(f"- {item.name} ({item.category}): ${item.price} [{status}]")
    return "\n".join(lines)

def add_to_cart_tool(item_name, quantity=1):
    """Adds an item to the user's cart by fuzzy matching the name."""
    all_items = MenuItem.query.filter_by(availability=True).all()
    all_names = [i.name for i in all_items]
    matches = difflib.get_close_matches(item_name, all_names, n=1, cutoff=0.5)

    if not matches:
        return f"Sorry, I couldn't find '{item_name}' on the menu."
    
    matched_name = matches[0]
    matched_item = next(i for i in all_items if i.name == matched_name)
    
    cart = session.get('cart', {})
    cart[str(matched_item.id)] = cart.get(str(matched_item.id), 0) + quantity
    session['cart'] = cart
    
    return f"Added {quantity} x {matched_name} to your cart."

@chatbot_bp.route('/')
def chat():
    return render_template('chat.html')

@chatbot_bp.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    user_msg = data.get("message", "").strip().lower()
    
    if 'chat_history' not in session:
        session['chat_history'] = []
    
    response_text = ""
    redirect_url = None
    
    word_to_num = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'a': 1, 'an': 1
    }

    if any(x in user_msg for x in ['hi', 'hello', 'hey', 'greetings', 'good morning', 'good evening']):
        response_text = "Hello! I am your AI assistant. I can help you see the menu, place orders, or book a table. Try saying 'Show Menu' or '2 Pizza, one Burger'."

    elif any(x in user_msg for x in ['menu', 'list', 'what do you have', 'dishes']):
        response_text = "Here is our menu:\n" + get_menu_tool()

    elif any(x in user_msg for x in ['book', 'reservation', 'table', 'reserve']):
        response_text = "Sure, redirecting you to table reservation..."
        redirect_url = url_for('reservations.reserve')

    elif any(x in user_msg for x in ['cart', 'checkout', 'pay']):
        response_text = "Redirecting you to your shopping cart..."
        redirect_url = url_for('cart.view_cart')

    else:
        all_items = MenuItem.query.filter_by(availability=True).all()
        keyword_map = {}
        for item in all_items:
            name_lower = item.name.lower()
            keyword_map[name_lower] = item
            keyword_map[name_lower + 's'] = item
            for part in name_lower.split():
                if len(part) > 2 and part not in keyword_map:
                    keyword_map[part] = item

        sorted_keywords = sorted(keyword_map.keys(), key=len, reverse=True)
        found_items = []
        msg_scan = user_msg 
        
        for keyword in sorted_keywords:
            pattern = rf"(?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a|an)\s+)?\b{re.escape(keyword)}\b"
            matches = list(re.finditer(pattern, msg_scan))
            for match in matches:
                qty_str = match.group(1)
                qty = 1
                if qty_str:
                    if qty_str.isdigit(): qty = int(qty_str)
                    else: qty = word_to_num.get(qty_str, 1)
                
                item = keyword_map[keyword]
                found_items.append((item, qty))
                start, end = match.span()
                msg_scan = msg_scan[:start] + (" " * (end - start)) + msg_scan[end:]

        if found_items:
            total_added = {}
            for item, qty in found_items:
                add_to_cart_tool(item.name, qty)
                total_added[item.name] = total_added.get(item.name, 0) + qty

            results_str = ", ".join([f"{v} x {k}" for k, v in total_added.items()])
            response_text = f"Great! Added {results_str} to your cart."
        else:
            response_text = "I'm sorry, I didn't catch that. You can ask for the 'Menu', 'Book a table', or order items like '2 Burgers'."

    session['chat_history'].append({"role": "user", "content": user_msg})
    session['chat_history'].append({"role": "assistant", "content": response_text})
    
    return jsonify({
        "answer": response_text, 
        "options": ["View Menu", "View Cart", "Book a Table"],
        "redirect": redirect_url
    })
