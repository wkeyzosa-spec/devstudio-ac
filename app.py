import os, json, uuid, hashlib, hmac, io, zipfile, subprocess, sys, time, base64
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET', os.urandom(64).hex())
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///devstudio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Vitanuova20@')
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:5000')
LICENSE_SECRET = os.getenv('HMAC_SECRET', 'DsAcHmac!7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f')

RATE_LIMIT_STORE = {}

def rate_limit(requests=5, window=60):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            ip = request.remote_addr or '127.0.0.1'
            now = time.time()
            key = f"{f.__name__}:{ip}"
            entry = RATE_LIMIT_STORE.get(key)
            if entry:
                if now - entry['reset'] > window:
                    entry['count'] = 1
                    entry['reset'] = now
                else:
                    entry['count'] += 1
                    if entry['count'] > requests:
                        return jsonify({'error': 'Too many requests'}), 429
            else:
                RATE_LIMIT_STORE[key] = {'count': 1, 'reset': now}
            return f(*args, **kwargs)
        return decorated
    return decorator

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

class Ban(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ban_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(256), nullable=False)
    player_name = db.Column(db.String(128), default='')
    steam = db.Column(db.String(128), default='')
    ip = db.Column(db.String(64), default='')
    license = db.Column(db.String(128), default='')
    xbl = db.Column(db.String(128), default='')
    live = db.Column(db.String(128), default='')
    discord = db.Column(db.String(128), default='')
    category = db.Column(db.String(32), default='silent')
    server_id = db.Column(db.String(64), default='')
    banned_at = db.Column(db.DateTime, default=datetime.utcnow)

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

class ServerInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(64), unique=True, nullable=False)
    server_name = db.Column(db.String(128), default='')
    online = db.Column(db.Boolean, default=False)
    player_count = db.Column(db.Integer, default=0)
    staff_count = db.Column(db.Integer, default=0)
    uptime = db.Column(db.String(32), default='0h')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ServerBan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ban_id = db.Column(db.Integer, nullable=False)
    server_id = db.Column(db.String(64), default='')
    player_name = db.Column(db.String(128), default='')
    reason = db.Column(db.String(256), default='')
    category = db.Column(db.String(32), default='ban')
    steam = db.Column(db.String(128), default='')
    ip = db.Column(db.String(64), default='')
    license = db.Column(db.String(128), default='')
    discord = db.Column(db.String(128), default='')
    xbl = db.Column(db.String(128), default='')
    live = db.Column(db.String(128), default='')
    fivem = db.Column(db.String(128), default='')
    banned_at = db.Column(db.DateTime, default=datetime.utcnow)

class ServerKick(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(64), default='')
    player_id = db.Column(db.Integer, default=0)
    player_name = db.Column(db.String(128), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed = db.Column(db.Boolean, default=False)

class ServerLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(64), default='')
    player_name = db.Column(db.String(128), default='')
    action = db.Column(db.String(16), default='warn')
    reason = db.Column(db.String(256), default='')
    detections = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ServerPlayer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(64), default='')
    player_id = db.Column(db.Integer, default=0)
    name = db.Column(db.String(128), default='')
    steam = db.Column(db.String(128), default='')
    ip = db.Column(db.String(64), default='')
    license = db.Column(db.String(128), default='')
    discord = db.Column(db.String(128), default='')
    xbl = db.Column(db.String(128), default='')
    live = db.Column(db.String(128), default='')
    fivem = db.Column(db.String(128), default='')
    playtime = db.Column(db.Integer, default=0)
    pos_x = db.Column(db.Float, default=0.0)
    pos_y = db.Column(db.Float, default=0.0)
    pos_z = db.Column(db.Float, default=0.0)
    country = db.Column(db.String(4), default='')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

class ServerCommand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(64), default='')
    action = db.Column(db.String(32), default='')  # spectate, teleport, wipe
    target_id = db.Column(db.Integer, default=0)
    target_name = db.Column(db.String(128), default='')
    admin_id = db.Column(db.Integer, default=0)
    admin_name = db.Column(db.String(128), default='')
    executed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ServerAdmin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(64), default='')
    player_id = db.Column(db.Integer, default=0)
    name = db.Column(db.String(128), default='')
    ace = db.Column(db.String(64), default='')
    online = db.Column(db.Boolean, default=False)

class ServerConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(64), default='')
    config_data = db.Column(db.Text, default='{}')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    salt = hashlib.sha256((LICENSE_SECRET + data.get('key', '')).encode()).hexdigest()[:16]
    return hmac.new((LICENSE_SECRET + salt).encode(), msg.encode(), hashlib.sha256).hexdigest()

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

# ---------- PUBLIC ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html', types=LICENSE_TYPES)

@app.route('/dashboard/demo')
def dashboard_demo():
    return render_template('dashboard_demo.html')

@app.route('/register', methods=['GET', 'POST'])
@rate_limit(3, 300)
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        pw = request.form.get('password')
        disc = request.form.get('discord', '')
        if len(pw) < 6:
            flash('Password too short (min 6 chars)', 'danger')
            return redirect(url_for('register'))
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
@rate_limit(5, 120)
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
@rate_limit(10, 60)
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

@app.route('/api/ban', methods=['POST'])
@rate_limit(60, 60)
def api_ban():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    auth = request.headers.get('Authorization', '')
    if data.get('unban'):
        ban_id = data.get('ban_id')
        ban_obj = Ban.query.filter_by(ban_id=ban_id).first()
        if ban_obj: db.session.delete(ban_obj)
        srv = data.get('server_id', '')
        if srv:
            srv_ban = ServerBan.query.filter_by(server_id=srv, ban_id=ban_id).first()
            if srv_ban: db.session.delete(srv_ban)
        db.session.commit()
        return jsonify({'success': True})
    if not data.get('reason'):
        return jsonify({'error': 'Missing data'}), 400
    sid = data.get('server_id', 'devstudio')
    ban = ServerBan(
        ban_id=data.get('ban_id', int(time.time() * 1000) % 1000000),
        server_id=sid, player_name=data.get('player_name', data.get('name', '')),
        reason=data['reason'], category=data.get('category', 'ban'),
        steam=data.get('steam', ''), ip=data.get('ip', ''),
        license=data.get('license', ''), discord=data.get('discord', ''),
        xbl=data.get('xbl', ''), live=data.get('live', ''), fivem=data.get('fivem', ''))
    db.session.add(ban)
    log = ServerLog(server_id=sid, player_name=data.get('player_name', data.get('name', '')),
        action='ban', reason=data['reason'], detections=1)
    db.session.add(log)
    if data.get('ban_id'):
        legacy = Ban(ban_id=data['ban_id'], reason=data['reason'],
            player_name=data.get('player_name', data.get('name', '')),
            steam=data.get('steam', ''), ip=data.get('ip', ''),
            license=data.get('license', ''), discord=data.get('discord', ''),
            category=data.get('category', 'silent'), server_id=sid)
        db.session.add(legacy)
    db.session.commit()
    return jsonify({'success': True, 'ban_id': ban.ban_id})

@app.route('/api/check-ban', methods=['GET'])
@rate_limit(60, 60)
def api_check_ban():
    identifiers = {k: request.args.get(k, '') for k in ['steam', 'ip', 'license', 'xbl', 'live', 'discord']}
    for key, val in identifiers.items():
        if val:
            ban = Ban.query.filter_by(**{key: val}).first()
            if ban:
                return jsonify({'banned': True, 'ban_id': ban.ban_id, 'reason': ban.reason, 'date': ban.banned_at.isoformat()})
    return jsonify({'banned': False})

@app.route('/api/lookup', methods=['GET'])
@rate_limit(60, 60)
def api_lookup():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'No query'}), 400
    results = []
    # Search ServerBan table
    srv_bans = ServerBan.query.filter(
        (ServerBan.player_name.ilike(f'%{q}%')) |
        (ServerBan.steam.ilike(f'%{q}%')) |
        (ServerBan.ip.ilike(f'%{q}%')) |
        (ServerBan.license.ilike(f'%{q}%')) |
        (ServerBan.discord.ilike(f'%{q}%'))
    ).order_by(ServerBan.banned_at.desc()).limit(20).all()
    for b in srv_bans:
        results.append({
            'source': 'server_ban',
            'ban_id': b.ban_id,
            'server_id': b.server_id,
            'player_name': b.player_name,
            'reason': b.reason,
            'category': b.category,
            'steam': b.steam,
            'ip': b.ip,
            'license': b.license,
            'discord': b.discord,
            'date': b.banned_at.isoformat() if b.banned_at else None,
        })
    # Search legacy Ban table
    legacy_bans = Ban.query.filter(
        (Ban.player_name.ilike(f'%{q}%')) |
        (Ban.steam.ilike(f'%{q}%')) |
        (Ban.ip.ilike(f'%{q}%')) |
        (Ban.license.ilike(f'%{q}%')) |
        (Ban.discord.ilike(f'%{q}%'))
    ).order_by(Ban.banned_at.desc()).limit(20).all()
    for b in legacy_bans:
        results.append({
            'source': 'legacy',
            'ban_id': b.ban_id,
            'server_id': b.server_id,
            'player_name': b.player_name,
            'reason': b.reason,
            'category': b.category,
            'steam': b.steam,
            'ip': b.ip,
            'license': b.license,
            'discord': b.discord,
            'date': b.banned_at.isoformat() if b.banned_at else None,
        })
    # Search current online players
    players = ServerPlayer.query.filter(
        (ServerPlayer.name.ilike(f'%{q}%')) |
        (ServerPlayer.steam.ilike(f'%{q}%')) |
        (ServerPlayer.ip.ilike(f'%{q}%')) |
        (ServerPlayer.license.ilike(f'%{q}%')) |
        (ServerPlayer.discord.ilike(f'%{q}%'))
    ).all()
    for p in players:
        results.append({
            'source': 'online',
            'server_id': p.server_id,
            'player_name': p.name,
            'steam': p.steam,
            'ip': p.ip,
            'license': p.license,
            'discord': p.discord,
            'xbl': p.xbl,
            'live': p.live,
            'country': p.country,
            'playtime': p.playtime,
        })
    return jsonify({'results': results, 'count': len(results)})

@app.route('/api/sync-bans', methods=['GET'])
@rate_limit(5, 60)
def api_sync_bans():
    auth = request.headers.get('Authorization', '')
    if auth != f'Bearer {hashlib.sha256(LICENSE_SECRET.encode()).hexdigest()}':
        return jsonify({'error': 'Unauthorized'}), 401
    after = request.args.get('after', '0')
    try:
        after_id = int(after)
    except:
        after_id = 0
    bans = Ban.query.filter(Ban.ban_id > after_id).all()
    return jsonify({'bans': [{
        'ban_id': b.ban_id, 'reason': b.reason, 'player_name': b.player_name,
        'steam': b.steam, 'ip': b.ip, 'license': b.license,
        'xbl': b.xbl, 'live': b.live, 'discord': b.discord,
        'category': b.category, 'server_id': b.server_id,
        'banned_at': b.banned_at.isoformat()
    } for b in bans]})

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
        'bans': Ban.query.count(),
    }
    return render_template('admin.html', orders=Order.query.order_by(Order.created_at.desc()).all(),
                          licenses=License.query.order_by(License.created_at.desc()).all(),
                          users=User.query.order_by(User.created_at.desc()).all(),
                          bans=Ban.query.order_by(Ban.banned_at.desc()).limit(50).all(),
                          stats=stats)

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

@app.route('/admin/unban/<int:bid>', methods=['POST'])
@admin_required
def admin_unban(bid):
    ban = Ban.query.get(bid)
    if ban:
        db.session.delete(ban)
        db.session.commit()
        flash(f'Ban {ban.ban_id} removed', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/api/server/<server_id>/unban/<int:bid>', methods=['POST'])
@rate_limit(30, 60)
def api_server_unban(server_id, bid):
    ban = ServerBan.query.get(bid)
    if ban:
        db.session.delete(ban)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Ban not found'}), 404

# ---------- SERVER DASHBOARD ----------
@app.route('/dashboard/server/<server_id>')
@login_required
def server_dashboard(server_id):
    srv = ServerInfo.query.filter_by(server_id=server_id).first()
    server_name = srv.server_name if srv else server_id
    server_online = srv.online if srv else False
    bans = ServerBan.query.filter_by(server_id=server_id).order_by(ServerBan.banned_at.desc()).all()
    players = ServerPlayer.query.filter_by(server_id=server_id).all()
    recent_logs = ServerLog.query.filter_by(server_id=server_id).order_by(ServerLog.created_at.desc()).limit(50).all()
    admins = ServerAdmin.query.filter_by(server_id=server_id).all()
    cfg = ServerConfig.query.filter_by(server_id=server_id).first()
    config_data = json.loads(cfg.config_data) if cfg else {}
    config_groups = build_config_groups(config_data)
    total_bans = len(bans)
    online_players = sum(1 for p in players if p.player_id > 0)
    stats = {
        'online': online_players,
        'staff_online': sum(1 for a in admins if a.online),
        'total_bans': total_bans,
        'uptime': srv.uptime if srv else '0h',
    }
    return render_template('server_dashboard.html',
        server_id=server_id, server_name=server_name, server_online=server_online,
        stats=stats, players=players, bans=bans, recent_bans=bans[:10],
        recent_logs=recent_logs, admins=admins, config_groups=config_groups)

CONFIG_GROUP_MAP = {
    'Components': 'Rilevamento_Cheat',
    'Protezioni Eventi': 'Protezioni_Eventi',
    'Limits': 'Limiti_e_Soglie',
    'BanComponents': 'Ban_Components',
    'Messages': 'Messaggi',
    'Webhook': 'Webhook',
}
CONFIG_REVERSE_MAP = {v: k for k, v in CONFIG_GROUP_MAP.items()}

def build_config_groups(data):
    groups = {
        'Rilevamento Cheat': {},
        'Limiti e Soglie': {},
        'Ban Components': {},
        'Protezioni Eventi': {},
        'Messaggi': {},
        'Webhook': {},
        'Blacklist': {},
    }

    toggles = data.get('Components', {})
    limits = data.get('Limits', {})
    ban_comps = data.get('BanComponents', {})
    messages = data.get('Messages', {})
    webhook = data.get('Webhook', {})
    ban_webhooks = webhook.get('Ban', {}) if isinstance(webhook, dict) else {}

    label_map = {
        'AntiCheat': 'Anticheat', 'AntiSpectate': 'Anti-Spectate', 'AntiNoclip': 'Anti-Noclip',
        'AntiCommands': 'Anti-Commands', 'AntiKeys': 'Anti-Keys', 'AntiESX': 'Anti-ESX',
        'AntiWeapons': 'Anti-Weapons', 'AntiRemoveOtherPlayersWeapons': 'Anti-Weapon Steal',
        'AntiCancelAnimations': 'Anti-Animation Cancel', 'StopOtherPlayersGivingEachOtherWeapons': 'Block Weapon Gifting',
        'ModMenuChecks': 'Mod Menu Checks', 'StopUnauthorizedResources': 'Stop Unauthorized Resources',
        'AntiAimbot': 'Anti-Aimbot', 'AntiVehicleSpawn': 'Anti-Vehicle Spawn',
        'AntiWeaponSpawn': 'Anti-Weapon Spawn', 'AntiHealthArmor': 'Anti-Health/Armor',
        'AntiTP': 'Anti-Teleport',
    }

    for k, v in toggles.items():
        label = label_map.get(k, k)
        if k in ('StopUnauthorizedResources', 'ModMenuChecks'):
            groups['Protezioni Eventi'][k] = {'label': label, 'desc': '', 'type': 'toggle', 'value': v, 'config_group': 'Components'}
        else:
            groups['Rilevamento Cheat'][k] = {'label': label, 'desc': '', 'type': 'toggle', 'value': v, 'config_group': 'Components'}

    for k, v in ban_comps.items():
        label = label_map.get(k, k)
        groups['Ban Components'][k] = {'label': label, 'desc': 'Auto-ban on detection', 'type': 'toggle', 'value': v, 'config_group': 'BanComponents'}

    limit_labels = {
        'NoClipTriggerCount': 'NoClip Trigger', 'AimbotTriggerCount': 'Aimbot Trigger',
        'TpTriggerCount': 'Teleport Trigger', 'TpMaxDistance': 'TP Max Distance',
        'VehicleSpawnLimit': 'Vehicle Spawn Limit', 'WeaponSpawnLimit': 'Weapon Spawn Limit',
    }
    for k, v in limits.items():
        lbl = limit_labels.get(k, k.replace('TriggerCount', ' Trigger').replace('Limit', ' Limit'))
        groups['Limiti e Soglie'][k] = {'label': lbl, 'desc': '', 'type': 'number', 'value': v, 'config_group': 'Limits'}

    for k, v in webhook.items():
        if k == 'Ban':
            continue
        if isinstance(v, bool):
            continue
        if not isinstance(v, str) or not v.startswith('http'):
            continue
        groups['Webhook'][k] = {'label': k.replace('URL', ' Webhook'), 'desc': '', 'type': 'text', 'value': v, 'config_group': 'Webhook'}

    if ban_webhooks:
        for category, url in ban_webhooks.items():
            v = url or ''
            if v and isinstance(v, str) and v.startswith('http'):
                groups['Webhook'][f'Ban_{category}'] = {'label': f'Ban Webhook ({category})', 'desc': '', 'type': 'text', 'value': v, 'config_group': 'Webhook'}

    msg_keys = list(messages.keys())[:12]
    for k in msg_keys:
        v = messages.get(k, '')
        groups['Messaggi'][k] = {'label': k, 'desc': '', 'type': 'text', 'value': v, 'config_group': 'Messages'}

    bl_categories = {
        'BlacklistedWeapons': 'Weapons', 'BlacklistedEvents': 'Events',
        'BlacklistedCommands': 'Commands', 'BlacklistedModels': 'Models',
    }
    for bl_key, bl_label in bl_categories.items():
        items = data.get(bl_key, [])
        groups['Blacklist'][bl_key] = {'label': f'{bl_label} ({len(items)})', 'desc': f'{len(items)} items', 'type': 'list', 'value': items[:8], 'config_group': bl_key}

    return groups

# ---------- SERVER API ----------
@app.route('/api/server/<server_id>/heartbeat', methods=['POST'])
@rate_limit(30, 60)
def api_server_heartbeat(server_id):
    data = request.get_json() or {}
    srv = ServerInfo.query.filter_by(server_id=server_id).first()
    if not srv:
        srv = ServerInfo(server_id=server_id)
        db.session.add(srv)
    srv.server_name = data.get('server_name', srv.server_name or server_id)
    srv.online = True
    srv.player_count = data.get('player_count', 0)
    srv.staff_count = data.get('staff_count', 0)
    srv.uptime = data.get('uptime', srv.uptime)
    srv.last_seen = datetime.utcnow()
    executed = data.get('kicks_executed', [])
    if executed:
        ServerKick.query.filter(ServerKick.server_id == server_id, ServerKick.id.in_(executed)).update({'executed': True})
    db.session.commit()
    kicks = ServerKick.query.filter_by(server_id=server_id, executed=False).all()
    pending = [{'id': k.id, 'player_id': k.player_id, 'player_name': k.player_name} for k in kicks]
    return jsonify({'success': True, 'pending_kicks': pending})

@app.route('/api/server/<server_id>/players', methods=['POST'])
@rate_limit(30, 60)
def api_sync_players(server_id):
    data = request.get_json() or []
    ServerPlayer.query.filter_by(server_id=server_id).delete()
    for p in data:
        sp = ServerPlayer(server_id=server_id, player_id=p.get('id', 0),
            name=p.get('name', ''), steam=p.get('steam', ''), ip=p.get('ip', ''),
            license=p.get('license', ''), discord=p.get('discord', ''),
            xbl=p.get('xbl', ''), live=p.get('live', ''), fivem=p.get('fivem', ''),
            playtime=p.get('playtime', 0),
            pos_x=p.get('pos_x', 0.0), pos_y=p.get('pos_y', 0.0), pos_z=p.get('pos_z', 0.0),
            country=p.get('country', ''))
        db.session.add(sp)
    db.session.commit()
    return jsonify({'success': True, 'count': len(data)})

@app.route('/api/server/<server_id>/ban', methods=['POST'])
@rate_limit(60, 60)
def api_server_ban(server_id):
    data = request.get_json()
    if not data or not data.get('reason'):
        return jsonify({'error': 'Missing data'}), 400
    ban = ServerBan(
        ban_id=int(data.get('ban_id', time.time())),
        server_id=server_id, player_name=data.get('player_name', ''),
        reason=data['reason'], category=data.get('category', 'ban'),
        steam=data.get('steam', ''), ip=data.get('ip', ''),
        license=data.get('license', ''), discord=data.get('discord', ''),
        xbl=data.get('xbl', ''), live=data.get('live', ''), fivem=data.get('fivem', ''))
    db.session.add(ban)
    log = ServerLog(server_id=server_id, player_name=data.get('player_name', ''),
        action='ban', reason=data['reason'], detections=1)
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'ban_id': ban.ban_id})

@app.route('/api/server/<server_id>/kick', methods=['POST'])
@rate_limit(30, 60)
def api_server_kick(server_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    kick = ServerKick(server_id=server_id,
        player_id=int(data.get('player_id', 0)),
        player_name=data.get('player_name', ''))
    db.session.add(kick)
    log = ServerLog(server_id=server_id, player_name=data.get('player_name', ''),
        action='kick', reason='Kicked via dashboard', detections=0)
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'kick_id': kick.id})

@app.route('/api/server/<server_id>/log', methods=['POST'])
@rate_limit(120, 60)
def api_server_log(server_id):
    data = request.get_json()
    if not data: return jsonify({'error': 'No data'}), 400
    log = ServerLog(server_id=server_id, player_name=data.get('player_name', ''),
        action=data.get('action', 'warn'), reason=data.get('reason', ''),
        detections=data.get('detections', 1))
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/server/<server_id>/config', methods=['GET', 'POST'])
@rate_limit(30, 60)
def api_server_config(server_id):
    if request.method == 'POST':
        data = request.get_json()
        if not data: return jsonify({'error': 'No data'}), 400
        # If data is in frontend group format, convert to proper config keys
        if 'Rilevamento_Cheat' in data or 'Limiti_e_Soglie' in data:
            converted = {}
            # Rilevamento Cheat + Protezioni Eventi → Components
            components = {}
            components.update(data.get('Rilevamento_Cheat', {}))
            components.update(data.get('Protezioni_Eventi', {}))
            if components: converted['Components'] = components
            # Limits
            limits = data.get('Limiti_e_Soglie', {})
            if limits: converted['Limits'] = limits
            # BanComponents
            ban_comps = data.get('Ban_Components', {})
            if ban_comps: converted['BanComponents'] = ban_comps
            # Messages
            messages = data.get('Messaggi', {})
            if messages: converted['Messages'] = messages
            # Webhook
            wh = data.get('Webhook', {})
            if wh:
                # Extract Ban_ sub-keys into nested Ban dict
                webhook_out = {}
                ban_webhooks = {}
                for k, v in wh.items():
                    if k.startswith('Ban_'):
                        ban_webhooks[k.replace('Ban_', '')] = v
                    else:
                        webhook_out[k] = v
                if ban_webhooks:
                    webhook_out['Ban'] = ban_webhooks
                if webhook_out:
                    converted['Webhook'] = webhook_out
            # Blacklist items are already keyed by their config key
            bl = data.get('Blacklist', {})
            if bl:
                for k, v in bl.items():
                    converted[k] = v if isinstance(v, list) else []
            data = converted
        cfg = ServerConfig.query.filter_by(server_id=server_id).first()
        if not cfg:
            cfg = ServerConfig(server_id=server_id)
            db.session.add(cfg)
        cfg.config_data = json.dumps(data)
        cfg.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})
    cfg = ServerConfig.query.filter_by(server_id=server_id).first()
    config = json.loads(cfg.config_data) if cfg else {}
    return jsonify({'config': config})

@app.route('/api/server/<server_id>/bans', methods=['GET'])
@rate_limit(30, 60)
def api_get_server_bans(server_id):
    bans = ServerBan.query.filter_by(server_id=server_id).all()
    result = {}
    for b in bans:
        result[b.player_name or str(b.ban_id)] = {
            'ID': b.ban_id,
            'reason': b.reason,
            'ip': b.ip,
            'license': b.license,
            'steam': b.steam,
            'discord': b.discord,
            'xbl': b.xbl,
            'live': b.live,
        }
    return jsonify(result)

@app.route('/api/server/<server_id>/console', methods=['GET'])
@rate_limit(30, 60)
def api_server_console(server_id):
    after = request.args.get('after', '0')
    try: after_id = int(after)
    except: after_id = 0
    logs = ServerLog.query.filter(ServerLog.server_id == server_id, ServerLog.id > after_id).order_by(ServerLog.created_at.asc()).all()
    return jsonify({'logs': [{
        'id': log.id, 'time': log.created_at.strftime('%H:%M:%S') if log.created_at else '--:--:--',
        'action': log.action, 'reason': log.reason, 'player_name': log.player_name
    } for log in logs]})

@app.route('/api/server/<server_id>/status', methods=['GET'])
@rate_limit(30, 60)
def api_server_status(server_id):
    srv = ServerInfo.query.filter_by(server_id=server_id).first()
    if not srv:
        return jsonify({'online': False, 'player_count': 0, 'staff_count': 0, 'uptime': '0h', 'total_bans': 0})
    total_bans = ServerBan.query.filter_by(server_id=server_id).count()
    return jsonify({
        'online': srv.online,
        'server_name': srv.server_name,
        'player_count': srv.player_count,
        'staff_count': srv.staff_count,
        'uptime': srv.uptime,
        'total_bans': total_bans,
        'last_seen': srv.last_seen.isoformat() if srv.last_seen else None,
    })

@app.route('/api/server/<server_id>/command', methods=['POST'])
@rate_limit(30, 60)
def api_server_command(server_id):
    data = request.get_json()
    if not data or not data.get('action'):
        return jsonify({'error': 'Missing action'}), 400
    cmd = ServerCommand(
        server_id=server_id,
        action=data['action'],
        target_id=int(data.get('target_id', 0)),
        target_name=data.get('target_name', ''),
        admin_id=int(data.get('admin_id', 0)),
        admin_name=data.get('admin_name', ''),
    )
    db.session.add(cmd)
    db.session.commit()
    return jsonify({'success': True, 'command_id': cmd.id})

@app.route('/api/server/<server_id>/commands/pending', methods=['GET'])
@rate_limit(30, 60)
def api_server_pending_commands(server_id):
    cmds = ServerCommand.query.filter_by(server_id=server_id, executed=False).all()
    return jsonify({'commands': [{
        'id': c.id, 'action': c.action,
        'target_id': c.target_id, 'target_name': c.target_name,
        'admin_name': c.admin_name,
    } for c in cmds]})

@app.route('/api/server/<server_id>/commands/execute/<int:cmd_id>', methods=['POST'])
@rate_limit(60, 60)
def api_server_execute_command(server_id, cmd_id):
    cmd = ServerCommand.query.get(cmd_id)
    if not cmd:
        return jsonify({'error': 'Command not found'}), 404
    cmd.executed = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/lookup-country', methods=['GET'])
@rate_limit(30, 60)
def api_lookup_country():
    ip = request.args.get('ip', '')
    if not ip:
        return jsonify({'country': ''})
    try:
        import urllib.request
        url = f'http://ip-api.com/json/{ip}?fields=countryCode'
        resp = urllib.request.urlopen(url, timeout=3).read()
        data = json.loads(resp)
        return jsonify({'country': data.get('countryCode', '')})
    except:
        return jsonify({'country': ''})

@app.route('/api/server/<server_id>/admins', methods=['POST'])
@rate_limit(30, 60)
def api_sync_admins(server_id):
    data = request.get_json() or []
    ServerAdmin.query.filter_by(server_id=server_id).delete()
    for a in data:
        sa = ServerAdmin(server_id=server_id, player_id=a.get('player_id', a.get('id', 0)),
            name=a.get('name', ''), ace=a.get('ace', ''), online=a.get('online', False))
        db.session.add(sa)
    db.session.commit()
    return jsonify({'success': True, 'count': len(data)})

# ---------- MULTISTREAM ----------
STREAM_FRAMES = {}
MAX_STREAM_AGE = 30

@app.route('/api/server/<server_id>/stream/<player_id>', methods=['POST'])
@rate_limit(120, 60)
def api_stream_frame(server_id, player_id):
    data = request.get_json()
    if not data or 'frame' not in data:
        return jsonify({'error': 'No frame data'}), 400
    try:
        raw = base64.b64decode(data['frame'])
    except Exception:
        return jsonify({'error': 'Invalid base64'}), 400
    if server_id not in STREAM_FRAMES:
        STREAM_FRAMES[server_id] = {}
    STREAM_FRAMES[server_id][player_id] = {'frame': raw, 'timestamp': time.time()}
    now = time.time()
    for sid in list(STREAM_FRAMES.keys()):
        for pid in list(STREAM_FRAMES[sid].keys()):
            if now - STREAM_FRAMES[sid][pid]['timestamp'] > MAX_STREAM_AGE:
                del STREAM_FRAMES[sid][pid]
        if not STREAM_FRAMES[sid]:
            del STREAM_FRAMES[sid]
    return jsonify({'success': True})

@app.route('/api/server/<server_id>/stream/<player_id>/frame', methods=['GET'])
@rate_limit(60, 60)
def api_get_stream_frame(server_id, player_id):
    frames = STREAM_FRAMES.get(server_id, {})
    entry = frames.get(player_id)
    if not entry:
        return jsonify({'error': 'No stream'}), 404
    return send_file(
        io.BytesIO(entry['frame']),
        mimetype='image/webp',
        max_age=0
    )

@app.route('/api/server/<server_id>/stream/<player_id>', methods=['DELETE'])
@rate_limit(30, 60)
def api_stop_stream(server_id, player_id):
    frames = STREAM_FRAMES.get(server_id, {})
    frames.pop(player_id, None)
    return jsonify({'success': True})

@app.route('/api/server/<server_id>/stream/active', methods=['GET'])
@rate_limit(30, 60)
def api_active_streams(server_id):
    frames = STREAM_FRAMES.get(server_id, {})
    now = time.time()
    active = [{'player_id': pid, 'last_seen': entry['timestamp']} for pid, entry in frames.items() if now - entry['timestamp'] <= MAX_STREAM_AGE]
    return jsonify({'active': active})

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
