import os, json, uuid, hashlib, hmac, io, zipfile, subprocess, sys
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///devstudio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:5000')
LICENSE_SECRET = "DsAc2024S3cur3K3y!@#"

LICENSE_TYPES = {
    'monthly':   {'days': 30,  'price': 19.99},
    'quarterly': {'days': 90,  'price': 49.99},
    'yearly':    {'days': 365, 'price': 119.99},
    'lifetime':  {'days': None,'price': 199.99},
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AC_RESOURCE_PATH = os.path.join(BASE_DIR, 'build')
AC_BUILD_PATH = os.path.join(BASE_DIR, 'build')

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    discord = db.Column(db.String(120), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    licenses = db.relationship('License', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class License(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    order_id = db.Column(db.String(64), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_email = db.Column(db.String(120), default='')
    customer_discord = db.Column(db.String(120), default='')
    note = db.Column(db.String(256), default='')
    download_token = db.Column(db.String(64), unique=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(64), unique=True, nullable=False)
    license_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='EUR')
    payment_method = db.Column(db.String(20))
    status = db.Column(db.String(20), default='pending')
    customer_email = db.Column(db.String(120))
    customer_discord = db.Column(db.String(120))
    license_key = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin access required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def generate_license_key():
    raw = str(uuid.uuid4()).replace("-", "").upper()[:20]
    return "DSAC-" + "-".join([raw[i:i+5] for i in range(0, 20, 5)])

def sign_license_data(data):
    fields = ["created", "expires", "key", "note", "server_ip", "status", "type"]
    msg = ";".join(f"{f}={data.get(f, '')}" for f in fields)
    return hmac.new(LICENSE_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()

def create_license(license_type, email='', discord='', note='', user_id=None):
    key = generate_license_key()
    now = datetime.utcnow()
    expires = now + timedelta(days=LICENSE_TYPES[license_type]['days']) if LICENSE_TYPES[license_type]['days'] else None

    lic = License(
        key=key, type=license_type, status='active', expires_at=expires,
        order_id=uuid.uuid4().hex[:16], user_id=user_id,
        customer_email=email, customer_discord=discord, note=note,
        download_token=uuid.uuid4().hex[:32]
    )
    db.session.add(lic)
    db.session.commit()

    lic_db_path = os.path.join(AC_RESOURCE_PATH, 'licenses.json')
    os.makedirs(AC_RESOURCE_PATH, exist_ok=True)
    try:
        with open(lic_db_path, 'r') as f:
            lic_db = json.load(f)
    except:
        lic_db = {}

    entry = {
        "key": key, "type": license_type,
        "created": now.isoformat() + "Z",
        "expires": expires.isoformat() + "Z" if expires else None,
        "status": "active", "note": f"{email} - {note}" if note else email, "server_ip": "",
    }
    entry["signature"] = sign_license_data(entry)
    lic_db[key] = entry
    with open(lic_db_path, 'w') as f:
        json.dump(lic_db, f, indent=2)

    return lic

# ---------- PUBLIC ROUTES ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html', types=LICENSE_TYPES)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        pw = request.form.get('password')
        disc = request.form.get('discord', '')
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        user = User(email=email, discord=disc)
        user.set_password(pw)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Account created!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        pw = request.form.get('password')
        if (email == 'admin' or email == 'admin@admin.com') and pw == ADMIN_PASSWORD:
            session['is_admin'] = True
            session['admin_email'] = email
            return redirect(url_for('admin_panel'))
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(pw):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', licenses=License.query.filter_by(user_id=current_user.id).all())

@app.route('/checkout/<license_type>')
def checkout(license_type):
    if license_type not in LICENSE_TYPES:
        flash('Invalid license type', 'danger')
        return redirect(url_for('pricing'))
    return render_template('checkout.html', license_type=license_type, info=LICENSE_TYPES[license_type], paypal_client_id=PAYPAL_CLIENT_ID)

@app.route('/create-payment', methods=['POST'])
def create_payment():
    lt = request.form.get('license_type')
    method = request.form.get('payment_method')
    email = request.form.get('email')
    discord = request.form.get('discord', '')
    if lt not in LICENSE_TYPES:
        return jsonify({'error': 'Invalid type'}), 400

    oid = uuid.uuid4().hex[:16]
    order = Order(order_id=oid, license_type=lt, amount=LICENSE_TYPES[lt]['price'],
                  currency='EUR', payment_method=method, status='pending',
                  customer_email=email, customer_discord=discord)
    db.session.add(order)
    db.session.commit()

    if method == 'paypal':
        return jsonify({'order_id': oid, 'amount': LICENSE_TYPES[lt]['price'], 'currency': 'EUR'})

    if method == 'bank_transfer':
        return jsonify({
            'order_id': oid, 'amount': LICENSE_TYPES[lt]['price'],
            'bank': {
                'bank': 'Intesa Sanpaolo', 'holder': 'Dev Studio',
                'iban': 'IT60 X054 2811 1010 0000 0123 456',
                'bic': 'BCITITMM', 'reference': f'DSAC-{oid}'
            }
        })

    return jsonify({'error': 'Invalid method'}), 400

@app.route('/paypal-capture', methods=['POST'])
def paypal_capture():
    data = request.get_json()
    order = Order.query.filter_by(order_id=data.get('order_id')).first()
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    if order.status == 'completed':
        return jsonify({'success': True, 'redirect': url_for('payment_success', order_id=order.order_id)})

    lic = create_license(order.license_type, order.customer_email, order.customer_discord, f'PayPal {order.order_id}')
    order.status = 'completed'
    order.license_key = lic.key
    order.paid_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'redirect': url_for('payment_success', order_id=order.order_id, _external=True)
    })

@app.route('/payment-success/<order_id>')
def payment_success(order_id):
    order = Order.query.filter_by(order_id=order_id).first()
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('pricing'))
    lic = License.query.filter_by(order_id=order.order_id).first()
    return render_template('payment_success.html', order=order, license=lic)

@app.route('/bank-confirm/<order_id>')
def bank_confirm(order_id):
    order = Order.query.filter_by(order_id=order_id).first()
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('pricing'))
    return render_template('bank_confirm.html', order=order)

@app.route('/api/verify-key', methods=['GET'])
def api_verify_key():
    key = request.args.get('key', '').strip().upper()
    if not key:
        return jsonify({'valid': False, 'error': 'No key provided'}), 400
    lic = License.query.filter_by(key=key, status='active').first()
    if not lic:
        return jsonify({'valid': False, 'error': 'Invalid or expired key'}), 404
    return jsonify({
        'valid': True,
        'type': lic.type,
        'expires': lic.expires_at.isoformat() if lic.expires_at else None,
        'download_url': url_for('download_resource', token=lic.download_token, _external=True)
    })

@app.route('/download/<token>')
def download_resource(token):
    lic = License.query.filter_by(download_token=token, status='active').first()
    if not lic:
        flash('Invalid or expired download link', 'danger')
        return redirect(url_for('pricing'))

    source = AC_BUILD_PATH
    if not os.path.exists(source):
        flash('Resource not available', 'danger')
        return redirect(url_for('dashboard'))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source):
            for f in files:
                if f.endswith('.py') or f.startswith('.') or f == 'integrity.json':
                    continue
                path = os.path.join(root, f)
                zf.write(path, os.path.relpath(path, source))
    buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True,
                     download_name=f'devstudio-ac-{lic.type}.zip')

# ---------- ADMIN ----------
@app.route('/admin')
@admin_required
def admin_panel():
    stats = {
        'orders': Order.query.count(),
        'revenue': db.session.query(db.func.sum(Order.amount)).filter_by(status='completed').scalar() or 0,
        'active_licenses': License.query.filter_by(status='active').count(),
        'users': User.query.count(),
    }
    return render_template('admin.html', orders=Order.query.order_by(Order.created_at.desc()).all(),
                          licenses=License.query.order_by(License.created_at.desc()).all(),
                          users=User.query.order_by(User.created_at.desc()).all(), stats=stats)

@app.route('/admin/create-license', methods=['POST'])
@admin_required
def admin_create():
    lt = request.form.get('license_type')
    email = request.form.get('email')
    discord = request.form.get('discord', '')
    note = request.form.get('note', '')
    if lt not in LICENSE_TYPES:
        flash('Invalid type', 'danger')
        return redirect(url_for('admin_panel'))
    lic = create_license(lt, email, discord, note)
    regen_licenses_json()
    flash(f'License {lic.key} created for {email}', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/revoke/<int:lid>', methods=['POST'])
@admin_required
def admin_revoke(lid):
    lic = License.query.get_or_404(lid)
    lic.status = 'revoked'
    db.session.commit()
    p = os.path.join(AC_RESOURCE_PATH, 'licenses.json')
    try:
        os.makedirs(AC_RESOURCE_PATH, exist_ok=True)
        with open(p, 'r') as f:
            d = json.load(f)
        if lic.key in d:
            d[lic.key]['status'] = 'revoked'
            d[lic.key]['signature'] = sign_license_data(d[lic.key])
            with open(p, 'w') as f:
                json.dump(d, f, indent=2)
    except:
        pass
    flash(f'License {lic.key} revoked', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/activate-order/<order_id>', methods=['POST'])
@admin_required
def admin_activate_order(order_id):
    order = Order.query.filter_by(order_id=order_id).first()
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('admin_panel'))
    if order.status == 'completed':
        flash('Order already completed', 'warning')
        return redirect(url_for('admin_panel'))

    lic = create_license(order.license_type, order.customer_email, order.customer_discord, f'Bank {order.order_id}')
    order.status = 'completed'
    order.license_key = lic.key
    order.paid_at = datetime.utcnow()
    db.session.commit()
    flash(f'Order activated! License: {lic.key}', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/regen', methods=['POST'])
@admin_required
def admin_regen():
    regen_licenses_json()
    flash('licenses.json regenerated', 'success')
    return redirect(url_for('admin_panel'))

def regen_licenses_json():
    active = License.query.filter_by(status='active').all()
    db_data = {}
    for lic in active:
        e = {"key": lic.key, "type": lic.type, "created": lic.created_at.isoformat() + "Z",
             "expires": lic.expires_at.isoformat() + "Z" if lic.expires_at else None,
             "status": "active", "note": lic.customer_email, "server_ip": ""}
        e["signature"] = sign_license_data(e)
        db_data[lic.key] = e
    os.makedirs(AC_RESOURCE_PATH, exist_ok=True)
    with open(os.path.join(AC_RESOURCE_PATH, 'licenses.json'), 'w') as f:
        json.dump(db_data, f, indent=2)

@app.route('/admin/build', methods=['POST'])
@admin_required
def admin_build():
    try:
        protect_path = os.path.join(BASE_DIR, 'protect.py')
        result = subprocess.run([sys.executable, protect_path], capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            flash(f'Build completed successfully', 'success')
        else:
            flash(f'Build failed: {result.stderr[:200]}', 'danger')
    except Exception as e:
        flash(f'Build error: {str(e)[:200]}', 'danger')
    return redirect(url_for('admin_panel'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
