# ... routes.py ...


from flask import render_template, jsonify, url_for, flash, session, redirect, request, abort
from app import app, db
from app.models import User, Panel, Data, PostRequest
from flask_login import current_user, login_user, logout_user, login_required
import uuid
import random
import string
import json
from datetime import datetime, timedelta
from .extensions import bcrypt
from .serializers import JsonOrderSerializer
from rest_framework.response import Response
from rest_framework import status
from apscheduler.schedulers.background import BackgroundScheduler

def remove_old_panels():
    threshold_date = datetime.utcnow() - timedelta(days=7)
    old_panels = Panel.query.filter(Panel.expires_on < threshold_date).all()
    for panel in old_panels:
        db.session.delete(panel)
    db.session.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(func=remove_old_panels, trigger="interval", days=1)
scheduler.start()


SECRET_ADMIN_PASSWORD = "n2kbverb"  # замените на ваш пароль


@app.route('/recharge')
@login_required
def recharge():
    return render_template('recharge.html')


@app.route('/extend_panel/<int:panel_id>', methods=['GET', 'POST'])
@login_required
def extend_panel(panel_id):
    panel = Panel.query.get(panel_id)
    if not panel:
        flash('Panel not found', 'danger')
        return redirect(url_for('dashboard'))

    prices = {
        "30 дней": 15,
        "60 дней": 29,
        "90 дней": 41,
        "180 дней": 77,
        "365 дней": 144,
        "Пожизненно": 450
    }

    if request.method == 'POST':
        selected_duration = request.form.get('duration')
        if selected_duration in prices:
            cost = prices[selected_duration]
            if current_user.balance >= cost:
                current_user.balance -= cost
                if selected_duration == "Пожизненно":
                    panel.expires_on = None
                else:
                    days = int(selected_duration.split()[0])
                    panel.expires_on += timedelta(days=days)
                db.session.commit()
                flash('Panel extended successfully', 'success')
            else:
                flash('Insufficient balance', 'danger')
        else:
            flash('Invalid selection', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('extend.html', panel=panel, prices=prices)




@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == SECRET_ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Неверный пароль', 'danger')
    return render_template('admin_login.html')


@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))


@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('is_admin'):
        abort(403)  # Отказ в доступе
    users = User.query.all()
    return render_template('admin_dashboard.html', users=users)


@app.route('/add_balance/<int:user_id>', methods=['POST'])
def add_balance(user_id):
    if not session.get('is_admin'):
        abort(403)  # Отказ в доступе

    user = User.query.get(user_id)
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('admin_dashboard'))

    amount = float(request.form.get('amount'))
    user.balance += amount
    db.session.commit()

    flash(f'Баланс пользователя {user.username} успешно пополнен на {amount} евро', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    panels = Panel.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', user=current_user, panels=panels, timedelta=timedelta)


@app.route('/create_panel', methods=['GET', 'POST'])
@login_required
def create_panel():
    if request.method == 'POST':
        unique_url = generate_unique_url()  # создаем уникальный URL для панели

        # Установите expires_on на 3 дня позже от текущей даты
        expiration_date = datetime.utcnow() + timedelta(days=3)

        new_panel = Panel(user_id=current_user.id, unique_url=unique_url, expires_on=expiration_date)
        db.session.add(new_panel)
        db.session.commit()
        flash('Панель успешно создана!')
        session['panel_unique_url'] = unique_url  # сохраняем уникальный URL панели в сеансе
        return redirect(url_for('dashboard'))
    return render_template('create_panel.html')


# Функция для генерации случайной строки из больших букв
def generate_unique_url(length=12):
    letters = string.ascii_uppercase
    return ''.join(random.choice(letters) for _ in range(length))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, password_hash=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now registered!')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user is None or not bcrypt.check_password_hash(user.password_hash, password):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/api/post/<panel_id>', methods=['POST'])
def api_post(panel_id):
    panel = Panel.query.filter_by(unique_url=panel_id).first()
    if not panel:
        return jsonify({"error": "Panel not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid data"}), 400

    # Сериализуем данные с использованием JsonOrderSerializer
    serializer = JsonOrderSerializer(data=data)

    if serializer.is_valid():
        # Если данные прошли валидацию, вы можете сохранить их в базе данных
        new_data = Data(content=str(data), panel=panel)
        db.session.add(new_data)
        db.session.commit()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




@app.route('/panel/<panel_id>')
@login_required
def panel(panel_id):
    # Fetch panel and associated post_requests in a single query
    panel = Panel.query.filter_by(id=panel_id, user_id=current_user.id).first_or_404()
    post_requests = PostRequest.query.filter_by(panel_id=panel_id).all()

    # Define a dictionary of field labels
    field_labels = {
    'customer_name': 'Customer Name',
    'product': 'Product',
    'created_at': 'Created At',
    'updated_at': 'Updated At',
    'dmn': 'Domain',
    'oid': 'Order ID',
    'uid': 'User ID',
    'dt': 'Order Date',
    'ip': 'IP Address',
    'itm': 'Items in Order',
    'pmt': 'Payment Method',
    'amt': 'Order Amount',
    'shp': 'Shipping Info',
    'disc': 'Discounts/Coupons',
    'eml': 'Email',
    'tel': 'Phone',
    'addr': 'Delivery Address',
    'note': 'Order Notes',
    'cur': 'Currency',
    'sts': 'Order Status',
    'rfid': 'Referrer ID',
    'tax': 'Taxes Applied',
    'geo': 'Geolocation',
    'brw': 'Browser',
    'os': 'Operating System',
    'aff': 'Affiliate ID',
    'crt': 'Cart Content',
    'src': 'Traffic Source',
    'loy': 'Loyalty Data',
    'rev': 'Reviews',
    'sub': 'Subscriptions',
    'gdr': 'Gender',
    'age': 'Age',
    'prfl': 'Profile Data',
    'hist': 'Purchase History',
    'fav': 'Favorites',
    'size': 'Item Size',
    'col': 'Item Color',
    'wgt': 'Item Weight',
    'brand': 'Item Brand',
    'cat': 'Item Category',
    'dur': 'Service Duration/Guarantee',
    'rat': 'Item Rating',
    'view': 'Item Views Before Purchase',
    'lstv': 'Last Visit Date',
    'wishlist': 'Wishlist Items',
    'cartab': 'Cart Abandonment Count',
    'refurl': 'Referral URL',
    'churn': 'Churn Probability',
    'camp': 'Campaign Source',
    'coupon': 'Coupon Code',
    'pltf': 'Platform (Mobile/Desktop)',
    'mems': 'Membership/Subscription Status',
    'srchq': 'Search Query Before Purchase',
    'shipm': 'Shipping Method',
    'ret': 'Return Information',
    'lang': 'Language',
    'nviews': 'Total Site Views by User',
    'feedb': 'Feedback/Comments',
    'lgnmth': 'Login Method',
    'dev': 'Device Type',
    'pricetg': 'Item Price Category',
    'recprod': 'Recommended Product',
    'fit': 'Item Fit',
    'stk': 'Item Stock Status',
    'adgrp': 'Ad Campaign Group',
    'vchat': 'Virtual Chat/Assistant Usage',
    'vtry': 'Virtual Try-On/Demo',
    'abtest': 'A/B Test Participant',
    'vidrev': 'Viewed Video Reviews/Demos',
    'pback': 'Requested Product Back in Stock',
    'mktseg': 'Marketing Segment',
    'intnt': 'User Intent Assessment',
    'push': 'Push Notification Subscription',
    'app': 'Mobile App Purchase',
    'loytier': 'Loyalty Tier',
    'smshare': 'Social Media Sharing',
    'repbuy': 'Repeat Purchase of Same Item',
    'gtway': 'Payment Gateway',
    'savwl': 'Saved Items in Wishlist',
    'hlpdesk': 'Contacted Helpdesk',
    'custseg': 'User Segmentation',
    'dlvryex': 'Delivery Expectations',
    'prodsrc': 'Product Source',
    'paylatr': 'Buy Now, Pay Later Option',
    'charity': 'Donation from Order Amount',

    }

    # Batch-parse JSON data outside the loop
    for request in post_requests:
        if isinstance(request.data, str):
            try:
                request.data = json.loads(request.data)
            except json.JSONDecodeError:
                # Handle parsing error, if any
                pass

    return render_template('panel.html', panel=panel, post_requests=post_requests, field_labels=field_labels)



@app.route('/panel/<unique_url>', methods=['POST'])
def handle_post(unique_url):
    panel = Panel.query.filter_by(unique_url=unique_url).first()
    if not panel:
        return {"error": "Panel not found"}, 404

    data = request.json  # Parse JSON data
    new_data = Data(content=json.dumps(data), panel=panel)  # Serialize data to a JSON string
    db.session.add(new_data)
    db.session.commit()
    return {"success": "Data received"}

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')