from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db
from models.models import MenuItem, User

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/')
def view_cart():
    # Check profile completion
    user = None
    complete = False

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        complete = user.is_complete if user else False

    # Build cart item list
    raw_cart = session.get('cart', {})  # {item_id: qty}
    items = []
    total = 0.0

    for item_id, qty in raw_cart.items():
        menu_item = MenuItem.query.get(int(item_id))
        if not menu_item:
            continue

        subtotal = menu_item.price * qty
        items.append({
            'id': menu_item.id,
            'name': menu_item.name,
            'price': menu_item.price,
            'qty': qty,
            'subtotal': subtotal,
            'image': menu_item.image,
            'stock': menu_item.stock_quantity
        })
        total += subtotal

    return render_template(
        'cart.html',
        items=items,
        total=total,
        is_profile_complete=complete
    )


@cart_bp.route('/add/<int:item_id>')
def add_to_cart(item_id):
    mi = MenuItem.query.get_or_404(item_id)
    
    # Check availability
    if not mi.availability:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Item is not available.'}), 400
        flash('Item is not available.', 'danger')
        return redirect(url_for('main.menu')) # Assuming main blueprint for menu

    # SRS: Check Stock
    cart = session.get('cart', {})
    current_qty = cart.get(str(item_id), 0)
    
    if current_qty + 1 > mi.stock_quantity:
        msg = f'Sorry, only {mi.stock_quantity} items left in stock.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('main.menu'))

    cart[str(item_id)] = current_qty + 1
    session['cart'] = cart
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        count = sum(cart.values())
        item_count = cart.get(str(item_id), 0)
        return jsonify({
            'success': True, 
            'message': f'Added {mi.name} to cart.', 
            'cart_count': count,
            'item_count': item_count
        })
    
    flash(f'Added {mi.name} to cart.', 'success')
    return redirect(request.referrer or url_for('main.menu'))


@cart_bp.route('/remove/<int:item_id>')
def remove_from_cart(item_id):
    cart = session.get('cart', {})
    cart.pop(str(item_id), None)
    session['cart'] = cart
    flash('Item removed from cart.', 'info')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/decrease/<int:item_id>')
def decrease_cart_item(item_id):
    cart = session.get('cart', {})
    str_id = str(item_id)
    
    if str_id in cart:
        cart[str_id] = cart[str_id] - 1
        if cart[str_id] <= 0:
            cart.pop(str_id, None)
            flash('Item removed from cart.', 'info')
        else:
            flash('Quantity updated.', 'success')
            
    session['cart'] = cart
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/update', methods=['POST'])
def update_cart():
    cart = {}
    for k, v in request.form.items():
        if k.startswith('qty_'):
            item_id = k.split('_', 1)[1]
            try:
                qty = int(v)
            except:
                qty = 0
            
            # Verify stock limit for update
            mi = MenuItem.query.get(item_id)
            if mi and qty > mi.stock_quantity:
                flash(f'Cannot order {qty} of {mi.name}. Only {mi.stock_quantity} in stock.', 'warning')
                qty = mi.stock_quantity
                
            if qty > 0:
                cart[item_id] = qty
    session['cart'] = cart
    flash('Cart updated.', 'success')
    return redirect(url_for('cart.view_cart'))
