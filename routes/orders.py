from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db
from models.models import Order, MenuItem, User
from services.email import send_email, format_order_body
import json
import requests
import os
import io
from xhtml2pdf import pisa
from flask import send_file, current_app
from datetime import datetime
from bkash_config import BKASH

orders_bp = Blueprint('orders', __name__)

# BKash Mock Config (should ideally be in config)
BKASH_CONFIG = {
    'base_url': 'https://checkout.sandbox.bka.sh/v1.2.0-beta',
    'app_key': 'mock_key',
    'app_secret': 'mock_secret',
    'username': 'mock_user',
    'password': 'mock_password'
}

@orders_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Please login to place order.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(session['user_id'])

    # Check profile completion using model property
    if not user.is_complete:
        flash("Please complete your profile before placing an order.", 'warning')
        return redirect(url_for('user.profile')) # Assuming user blueprint
        
    cart_data = session.get('cart', {})
    if not cart_data:
        flash("Your cart is empty.", 'warning')
        return redirect(url_for('cart.view_cart'))

    if request.method == 'POST':
        payment_method = request.form.get("payment_method") 
        phone = request.form.get('phone')
        district = request.form.get('district')
        city = request.form.get('city')
        street = request.form.get('street')
        
        # Verify items are in stock before proceeding
        for item_id, qty in cart_data.items():
            mi = MenuItem.query.get(item_id)
            if not mi or mi.stock_quantity < qty:
                flash(f"Item '{mi.name}' is out of stock or low on stock. Please update cart.", 'danger')
                return redirect(url_for('cart.view_cart'))

        # If Pay Now selected → go to payment gateway page
        if payment_method == "paynow":
            session["checkout_data"] = {
                "phone": phone,
                "district": district,
                "city": city,
                "street": street
            }
            return redirect(url_for("orders.pay_now"))

        # Cash on Delivery / Standard Order
        items_list = []
        total_price = 0

        for item_id, qty in cart_data.items():
            item = MenuItem.query.get(int(item_id))
            if item:
                items_list.append({
                    'name': item.name,
                    'price': item.price,
                    'qty': qty
                })
                total_price += item.price * qty
                
                # SRS: Decrease stock quantity
                item.stock_quantity -= qty
                if item.stock_quantity < 0: 
                     item.stock_quantity = 0 # Prevent negative

        # Create order
        new_order = Order(
            user_id=user.id,
            items=json.dumps(items_list),
            total=total_price,
            phone=phone,
            address_district=district,
            address_city=city,
            address_street=street,
            status="Pending",
            payment_status="pending",
            order_type="dine_in" # Default for now, can extend to takeaway
        )
        
        if payment_method == "cash":
             new_order.payment_method = "cash"
        
        db.session.add(new_order)
        db.session.commit()

        # Clear cart
        session['cart'] = {}

        # Send Email Receipt
        if user.email:
             details = format_order_body(new_order)
             send_email(f"Order #{new_order.unique_order_number} Received", user.email,
                        f"Hello {user.full_name},\n\nThank you for your order!\n\n{details}\n\nWe will start preparing it shortly.\n\nRegards,\nRestaurant Team")

        flash("Order placed successfully!", 'success')
        return redirect(url_for('user.orders')) # Assuming user blueprint for order history

    return render_template("checkout.html")


@orders_bp.route('/pay-now')
def pay_now():
    if "checkout_data" not in session:
        return redirect(url_for("orders.checkout"))

    # Calculate total from cart
    cart = session.get('cart', {})
    total = 0
    for item_id, qty in cart.items():
        item = MenuItem.query.get(int(item_id))
        if item:
            total += item.price * qty

    return render_template("pay_now.html", total=total)


@orders_bp.route('/payment/success')
def payment_success():
    if "checkout_data" not in session:
        return redirect(url_for("orders.checkout"))

    checkout_data = session["checkout_data"]
    cart_data = session.get("cart", {})
    user = User.query.get(session['user_id'])

    items_list = []
    total_price = 0

    for item_id, qty in cart_data.items():
        item = MenuItem.query.get(int(item_id))
        if item:
            items_list.append({
                'name': item.name,
                'price': item.price,
                'qty': qty
            })
            total_price += item.price * qty
            
            # SRS: Update Stock
            item.stock_quantity -= qty
            if item.stock_quantity < 0: item.stock_quantity = 0

    new_order = Order(
        user_id=user.id,
        items=json.dumps(items_list),
        total=total_price,
        phone=checkout_data["phone"],
        address_district=checkout_data["district"],
        address_city=checkout_data["city"],
        address_street=checkout_data["street"],
        status="Paid",          # Confirmed essentially
        payment_status="paid",  # SRS requirement
        payment_method="online_bkash" # simplified
    )

    db.session.add(new_order)
    db.session.commit()

    session.pop("checkout_data", None)
    session['cart'] = {}
    
    # Email Receipt
    if user.email:
         details = format_order_body(new_order)
         send_email(f"Payment Received - Order #{new_order.unique_order_number}", user.email,
                    f"Hello {user.full_name},\n\nPayment successful! Your order has been placed.\n\n{details}\n\nRegards,\nRestaurant Team")

    flash("Payment successful! Order placed.", 'success')
    return redirect(url_for('user.orders'))

@orders_bp.route('/invoice/<int:order_id>')
def download_invoice(order_id):
    if 'user_id' not in session:
        flash("Please login to download invoice.", 'danger')
        return redirect(url_for('auth.login'))

    order = Order.query.get_or_404(order_id)

    # Prevent users from downloading others’ invoices
    if order.user_id != session['user_id'] and session.get('role') != 'admin':
        flash("You don't have permission to access this invoice.", 'danger')
        return redirect(url_for('user.orders'))

    # Parse items JSON
    try:
        order.items_parsed = json.loads(order.items)
    except:
        order.items_parsed = []

    # Render invoice HTML
    html_out = render_template('invoice.html', order=order)

    # PDF generation
    pdf_stream = io.BytesIO()
    pisa.CreatePDF(html_out, dest=pdf_stream)
    pdf_stream.seek(0)

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Invoice_{order.unique_order_number}.pdf"
    )

def bkash_get_token():
    url = f"{BKASH['base_url']}/token/grant"
    headers = {"Content-Type": "application/json"}
    body = {
        "app_key": BKASH["app_key"],
        "app_secret": BKASH["app_secret"]
    }

    res = requests.post(url, json=body, auth=(BKASH["username"], BKASH["password"]), headers=headers)
    data = res.json()

    return data.get("id_token")

@orders_bp.route('/pay/bkash', methods=['POST'])
def bkash_pay():
    if "checkout_data" not in session:
        return redirect(url_for("orders.checkout"))

    token = bkash_get_token()
    if not token:
        flash("bKash authentication failed!", 'danger')
        return redirect(url_for("orders.checkout"))

    # Calculate Total Amount
    cart = session.get("cart", {})
    total = 0
    for item_id, qty in cart.items():
        item = MenuItem.query.get(int(item_id))
        if item:
            total += item.price * qty

    # Store transaction amount for verification
    session["bkash_amount"] = total

    # Create payment request
    create_url = f"{BKASH['base_url']}/checkout/payment/create"
    headers = {
        "Content-Type": "application/json",
        "authorization": token,
        "x-app-key": BKASH["app_key"]
    }

    payload = {
        "amount": str(total),
        "currency": "BDT",
        "intent": "sale",
        "merchantInvoiceNumber": "INV" + str(int(datetime.utcnow().timestamp())),
    }

    res = requests.post(create_url, json=payload, headers=headers)
    data = res.json()

    if "bkashURL" in data:
        return redirect(data["bkashURL"])

    flash("bKash payment initiation failed.", 'danger')
    return redirect(url_for("orders.checkout"))

@orders_bp.route('/bkash/callback', methods=['GET'])
def bkash_callback():
    payment_id = request.args.get("paymentID")
    status = request.args.get("status")

    if status != "success":
        flash("bKash Payment Failed or Canceled.", 'danger')
        return redirect(url_for("orders.checkout"))

    token = bkash_get_token()

    execute_url = f"{BKASH['base_url']}/checkout/payment/execute/{payment_id}"
    headers = {
        "Content-Type": "application/json",
        "authorization": token,
        "x-app-key": BKASH["app_key"]
    }

    res = requests.post(execute_url, json={}, headers=headers)
    data = res.json()

    if data.get("transactionStatus") != "Completed":
        flash("bKash Payment Execution Failed.", 'danger')
        return redirect(url_for("orders.checkout"))

    return finalize_bkash_order()

def finalize_bkash_order():
    checkout_data = session.get("checkout_data")
    cart = session.get("cart", {})
    user = User.query.get(session['user_id'])

    items_list = []
    total_price = 0
    for item_id, qty in cart.items():
        item = MenuItem.query.get(int(item_id))
        if item:
            items_list.append({
                "name": item.name,
                "price": item.price,
                "qty": qty
            })
            total_price += item.price * qty
            
            # Decrease Stock
            item.stock_quantity -= qty
            if item.stock_quantity < 0: item.stock_quantity = 0

    new_order = Order(
        user_id=user.id,
        items=json.dumps(items_list),
        total=total_price,
        phone=checkout_data["phone"],
        address_district=checkout_data["district"],
        address_city=checkout_data["city"],
        address_street=checkout_data["street"],
        status="Paid",
        payment_status="paid",
        payment_method="bkash"
    )

    db.session.add(new_order)
    db.session.commit()

    if user.email:
         details = format_order_body(new_order)
         send_email(f"Payment Received - Order #{new_order.unique_order_number}", user.email,
                    f"Hello {user.full_name},\n\nPayment successful! Your order has been placed.\n\n{details}\n\nRegards,\nRestaurant Team")

    # Earn Loyalty Points
    add_loyalty_points(user.id, total_price)

    session.pop("checkout_data", None)
    session["cart"] = {}

    flash("Payment Successful! Order placed.", "success")

