import os, datetime, base64, json, requests, threading, time
from flask import Flask, request, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}}, supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'], methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
app.config.update({
    'SECRET_KEY': 'super-secret-key-change-in-production', 'SESSION_COOKIE_SAMESITE': 'Lax',
    'SESSION_COOKIE_SECURE': False, 'SESSION_COOKIE_HTTPONLY': True, 'SESSION_COOKIE_DOMAIN': None,
    'SQLALCHEMY_DATABASE_URI': f'sqlite:///{os.path.join(BASE_DIR, "instance", "data.db")}',
    'UPLOAD_FOLDER': os.path.join(BASE_DIR, 'uploads'), 'SQLALCHEMY_TRACK_MODIFICATIONS': False
})
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)
db = SQLAlchemy(app)
photo_cache = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    def set_password(self, pwd): self.password_hash = generate_password_hash(pwd)
    def check_password(self, pwd): return check_password_hash(self.password_hash, pwd)

class Camera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    mac_address = db.Column(db.String(20), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey('camera.id'), nullable=False)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now)

class HistoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey('camera.id'), nullable=False)
    chart_image = db.Column(db.String)
    photo_image = db.Column(db.String)
    sensor_data = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now)

class HistoryPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    history_id = db.Column(db.Integer, db.ForeignKey('history_item.id'), nullable=False)
    photo_url = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', is_admin=True)
        admin.set_password('123456')
        db.session.add(admin); db.session.commit()
        print("✅ Admin user created: admin/123456")

def login_required(f):
    @wraps(f)
    def dec(*a, **kw): return f(*a, **kw) if 'user_id' in session else (jsonify({"error": "Unauthorized"}), 401)
    return dec

def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
        u = User.query.get(session['user_id'])
        return f(*a, **kw) if u and u.is_admin else (jsonify({"error": "Admin access required"}), 403)
    return dec

@app.route('/api/login', methods=['POST'])
def login():
    d = request.get_json()
    u = User.query.filter_by(username=d.get('username')).first()
    if u and u.check_password(d.get('password')):
        session['user_id'], session['is_admin'] = u.id, u.is_admin
        return jsonify({"message": "Login successful", "user": {"id": u.id, "username": u.username, "is_admin": u.is_admin}})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})

@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    d = request.get_json()
    c, n = d.get('current_password'), d.get('new_password')
    if not c or not n: return jsonify({"error": "Tüm alanlar gerekli"}), 400
    u = User.query.get(session['user_id'])
    if not u.check_password(c): return jsonify({"error": "Mevcut şifre yanlış"}), 400
    if len(n) < 6: return jsonify({"error": "Yeni şifre en az 6 karakter olmalı"}), 400
    u.set_password(n); db.session.commit()
    return jsonify({"message": "Şifre başarıyla değiştirildi"})

@app.route('/api/me', methods=['GET'])
@login_required
def get_current_user():
    u = User.query.get(session['user_id'])
    return jsonify({"id": u.id, "username": u.username, "is_admin": u.is_admin})

@app.route('/api/users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    if request.method == 'POST':
        d = request.get_json()
        if User.query.filter_by(username=d.get('username')).first(): return jsonify({"error": "Username already exists"}), 400
        u = User(username=d.get('username'), is_admin=d.get('is_admin', False))
        u.set_password(d.get('password'))
        db.session.add(u); db.session.commit()
        return jsonify({"message": "User created", "id": u.id}), 201
    return jsonify([{"id": u.id, "username": u.username, "is_admin": u.is_admin} for u in User.query.all()])

@app.route('/api/users/<int:id>', methods=['DELETE'])
@admin_required
def delete_user(id):
    u = User.query.get_or_404(id)
    if u.username == 'admin': return jsonify({"error": "Cannot delete admin user"}), 400
    db.session.delete(u); db.session.commit()
    return jsonify({"message": "User deleted"})

@app.route('/api/cameras', methods=['GET', 'POST'])
@login_required
def manage_cameras():
    try:
        if request.method == 'POST':
            if not session.get('is_admin'): return jsonify({"error": "Admin access required"}), 403
            d = request.get_json()
            c = Camera(name=d.get('name'), ip_address=d.get('ip_address'), location=d.get('location'))
            db.session.add(c); db.session.commit()
            return jsonify({"message": "Camera added", "id": c.id}), 201
        return jsonify([{"id": c.id, "name": c.name, "ip_address": c.ip_address, "location": c.location} for c in Camera.query.all()])
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/cameras/<int:id>', methods=['PUT', 'DELETE'])
@admin_required
def modify_camera(id):
    c = Camera.query.get_or_404(id)
    if request.method == 'PUT':
        d = request.get_json()
        c.name, c.ip_address, c.location = d.get('name', c.name), d.get('ip_address', c.ip_address), d.get('location', c.location)
        db.session.commit()
        return jsonify({"message": "Camera updated"})
    db.session.delete(c); db.session.commit()
    return jsonify({"message": "Camera deleted"})

@app.route('/api/register-device', methods=['POST'])
def register_device():
    try:
        d = request.get_json()
        m, ip = d.get('mac_address'), request.remote_addr
        if not m: return jsonify({"error": "MAC address required"}), 400
        c = Camera.query.filter_by(mac_address=m).first()
        if c: c.ip_address = f"http://{ip}"
        else:
            c = Camera(name=f"Camera {Camera.query.count() + 1}", ip_address=f"http://{ip}", location="New Device", mac_address=m)
            db.session.add(c)
        db.session.commit()
        return jsonify({"id": c.id, "name": c.name})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/sensor-upload', methods=['POST'])
def upload_sensor():
    try:
        d = request.get_json()
        c_id = d.get('camera_id', 1)
        if not Camera.query.get(c_id): return jsonify({"error": "Camera not found. Please restart ESP32 to register."}), 404
        db.session.add(SensorData(camera_id=c_id, temperature=float(d['temperature']), humidity=float(d['humidity'])))
        db.session.commit()
        return jsonify({"message": "Data received"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 400

@app.route('/api/data', methods=['GET', 'DELETE'])
@login_required
def handle_data():
    c_id = request.args.get('camera_id', 1, type=int)
    if request.method == 'DELETE':
        SensorData.query.filter_by(camera_id=c_id).delete(); db.session.commit()
        return jsonify({"message": "Cleared"})
    d = SensorData.query.filter_by(camera_id=c_id).order_by(SensorData.timestamp.desc()).all()
    return jsonify([{'id': r.id, 'temperature': r.temperature, 'humidity': r.humidity, 'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S')} for r in d[::-1]])

def capture_photo(c):
    ip = c.ip_address if c.ip_address.startswith("http") else f"http://{c.ip_address}"
    r = requests.get(f"{ip}/capture", timeout=20)
    if r.status_code == 200:
        fn = f"cam{c.id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        with open(os.path.join(app.config['UPLOAD_FOLDER'], fn), 'wb') as f: f.write(r.content)
        return f'http://localhost:5001/uploads/{fn}'
    return None

@app.route('/api/photos', methods=['GET'])
@login_required
def get_photos():
    c_id = request.args.get('camera_id', 1, type=int)
    c = Camera.query.get(c_id)
    if not c: return jsonify([{'url': 'https://placehold.co/320x240?text=Camera+Not+Found'}]), 404
    now = datetime.datetime.now()
    if c_id in photo_cache:
        p_url, p_time = photo_cache[c_id]
        if (now - p_time).total_seconds() < 5: return jsonify([{'url': p_url}])
    try:
        pu = capture_photo(c)
        if pu: photo_cache[c_id] = (pu, now); return jsonify([{'url': pu}])
        return jsonify([{'url': 'https://placehold.co/320x240?text=ESP32+Error'}]), 502
    except: return jsonify([{'url': 'https://placehold.co/320x240?text=Connection+Refused'}]), 500

@app.route('/api/save-history', methods=['POST'])
@login_required
def save_history():
    try:
        d = request.get_json()
        c_id = d.get('camera_id', 1)
        fn = f"chart_cam{c_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        if d.get('chartImage'):
            img = d['chartImage'].split(',', 1)[1] if ',' in d['chartImage'] else d['chartImage']
            with open(os.path.join(app.config['UPLOAD_FOLDER'], fn), "wb") as f: f.write(base64.b64decode(img))
        itm = HistoryItem(camera_id=c_id, chart_image=fn, photo_image=d.get('photoUrl'), sensor_data=json.dumps(d.get('sensorData')))
        db.session.add(itm); db.session.flush()
        for p in d.get('photos', []):
            db.session.add(HistoryPhoto(history_id=itm.id, photo_url=p['url'], timestamp=datetime.datetime.fromisoformat(p['timestamp'])))
        db.session.commit()
        return jsonify({"message": "Saved", "id": itm.id}), 201
    except Exception as e: db.session.rollback(); return jsonify({"error": str(e)}), 500

@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    c_id = request.args.get('camera_id', type=int)
    q = HistoryItem.query.filter_by(camera_id=c_id) if c_id else HistoryItem.query
    itms = q.order_by(HistoryItem.timestamp.desc()).limit(10).all()
    res = []
    for i in itms:
        ps = HistoryPhoto.query.filter_by(history_id=i.id).order_by(HistoryPhoto.timestamp.desc()).all()
        res.append({
            'id': i.id, 'camera_id': i.camera_id, 'chart_image': f'/uploads/{i.chart_image}',
            'photo_image': i.photo_image, 'photos': [{'url': p.photo_url, 'timestamp': p.timestamp.strftime('%Y-%m-%d %H:%M:%S')} for p in ps],
            'sensor_data': json.loads(i.sensor_data) if i.sensor_data else None, 'timestamp': i.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify(res)

@app.route('/api/history/<int:id>', methods=['DELETE'])
@login_required
def delete_history(id):
    itm = HistoryItem.query.get_or_404(id)
    HistoryPhoto.query.filter_by(history_id=id).delete()
    db.session.delete(itm); db.session.commit()
    return jsonify({"message": "Deleted"})

@app.route('/uploads/<path:filename>')
def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def background_photo_capture():
    print("🔄 Background photo capture started")
    while True:
        try:
            with app.app_context():
                for c in Camera.query.all():
                    try:
                        ls = SensorData.query.filter_by(camera_id=c.id).order_by(SensorData.timestamp.desc()).first()
                        if not ls: continue
                        t = ls.temperature
                        iv = 5 if t >= 28 else (10 if t >= 24 else (20 if t >= 20 else 30))
                        now = datetime.datetime.now()
                        if c.id in photo_cache and (now - photo_cache[c.id][1]).total_seconds() < iv: continue
                        pu = capture_photo(c)
                        if pu: photo_cache[c.id] = (pu, now)
                    except: pass
        except: pass
        time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=background_photo_capture, daemon=True).start()
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)