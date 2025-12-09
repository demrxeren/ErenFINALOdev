import os, datetime, base64, json, requests
from flask import Flask, request, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}}, supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'], methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
app.config.update(SECRET_KEY='super-secret-key-change-in-production', SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_DOMAIN=None,
    SQLALCHEMY_DATABASE_URI=f'sqlite:///{os.path.join(BASE_DIR, "instance", "data.db")}',
    UPLOAD_FOLDER=os.path.join(BASE_DIR, 'uploads'), SQLALCHEMY_TRACK_MODIFICATIONS=False)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

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

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', is_admin=True)
        admin.set_password('123456')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created: admin/123456")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return f(*args, **kwargs) if 'user_id' in session else (jsonify({"error": "Unauthorized"}), 401)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
        user = User.query.get(session['user_id'])
        return f(*args, **kwargs) if user and user.is_admin else (jsonify({"error": "Admin access required"}), 403)
    return decorated

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if user and user.check_password(data.get('password')):
        session['user_id'], session['is_admin'] = user.id, user.is_admin
        return jsonify({"message": "Login successful", "user": {"id": user.id, "username": user.username, "is_admin": user.is_admin}}), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200

@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    curr, new = data.get('current_password'), data.get('new_password')
    if not curr or not new: return jsonify({"error": "Tüm alanlar gerekli"}), 400
    user = User.query.get(session['user_id'])
    if not user.check_password(curr): return jsonify({"error": "Mevcut şifre yanlış"}), 400
    if len(new) < 6: return jsonify({"error": "Yeni şifre en az 6 karakter olmalı"}), 400
    user.set_password(new)
    db.session.commit()
    return jsonify({"message": "Şifre başarıyla değiştirildi"}), 200

@app.route('/api/me', methods=['GET'])
@login_required
def get_current_user():
    user = User.query.get(session['user_id'])
    return jsonify({"id": user.id, "username": user.username, "is_admin": user.is_admin})

@app.route('/api/users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    if request.method == 'POST':
        data = request.get_json()
        if User.query.filter_by(username=data.get('username')).first(): 
            return jsonify({"error": "Username already exists"}), 400
        user = User(username=data.get('username'), is_admin=data.get('is_admin', False))
        user.set_password(data.get('password'))
        db.session.add(user); db.session.commit()
        return jsonify({"message": "User created", "id": user.id}), 201
    return jsonify([{"id": u.id, "username": u.username, "is_admin": u.is_admin} for u in User.query.all()])

@app.route('/api/users/<int:id>', methods=['DELETE'])
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    if user.username == 'admin': return jsonify({"error": "Cannot delete admin user"}), 400
    db.session.delete(user); db.session.commit()
    return jsonify({"message": "User deleted"}), 200

@app.route('/api/cameras', methods=['GET', 'POST'])
@login_required
def manage_cameras():
    try:
        if request.method == 'POST':
            if not session.get('is_admin'): return jsonify({"error": "Admin access required"}), 403
            data = request.get_json()
            camera = Camera(name=data.get('name'), ip_address=data.get('ip_address'), location=data.get('location'))
            db.session.add(camera)
            db.session.commit()
            return jsonify({"message": "Camera added", "id": camera.id}), 201
        return jsonify([{"id": c.id, "name": c.name, "ip_address": c.ip_address, "location": c.location} for c in Camera.query.all()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cameras/<int:id>', methods=['PUT', 'DELETE'])
@admin_required
def modify_camera(id):
    camera = Camera.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.get_json()
        camera.name = data.get('name', camera.name)
        camera.ip_address = data.get('ip_address', camera.ip_address)
        camera.location = data.get('location', camera.location)
        db.session.commit()
        return jsonify({"message": "Camera updated"}), 200
    db.session.delete(camera); db.session.commit()
    return jsonify({"message": "Camera deleted"}), 200

@app.route('/api/register-device', methods=['POST'])
def register_device():
    try:
        data = request.get_json()
        mac, ip = data.get('mac_address'), request.remote_addr
        if not mac: return jsonify({"error": "MAC address required"}), 400
        camera = Camera.query.filter_by(mac_address=mac).first()
        if camera:
            camera.ip_address = f"http://{ip}"
            db.session.commit()
        else:
            camera = Camera(name=f"Camera {Camera.query.count() + 1}", ip_address=f"http://{ip}", location="New Device", mac_address=mac)
            db.session.add(camera)
            db.session.commit()
        return jsonify({"id": camera.id, "name": camera.name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sensor-upload', methods=['POST'])
def upload_sensor():
    try:
        data = request.get_json()
        camera_id = data.get('camera_id', 1)
        if not Camera.query.get(camera_id): 
            return jsonify({"error": "Camera not found. Please restart ESP32 to register."}), 404
        db.session.add(SensorData(camera_id=camera_id, temperature=float(data['temperature']), 
                                   humidity=float(data['humidity'])))
        db.session.commit()
        return jsonify({"message": "Data received"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/data', methods=['GET', 'DELETE'])
@login_required
def handle_data():
    camera_id = request.args.get('camera_id', 1, type=int)
    if request.method == 'DELETE':
        SensorData.query.filter_by(camera_id=camera_id).delete()
        db.session.commit()
        return jsonify({"message": "Cleared"}), 200
    data = SensorData.query.filter_by(camera_id=camera_id).order_by(SensorData.timestamp.desc()).all()
    return jsonify([{'id': r.id, 'temperature': r.temperature, 'humidity': r.humidity, 'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S')} for r in data[::-1]])

@app.route('/api/photos', methods=['GET'])
@login_required
def get_photos():
    camera_id = request.args.get('camera_id', 1, type=int)
    camera = Camera.query.get(camera_id)
    if not camera: return jsonify([{'url': 'https://placehold.co/320x240?text=Camera+Not+Found'}]), 404
    try:
        esp_ip = camera.ip_address if camera.ip_address.startswith("http") else f"http://{camera.ip_address}"
        resp = requests.get(f"{esp_ip}/capture", timeout=10)
        if resp.status_code == 200:
            filename = f"cam{camera_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'wb') as f: f.write(resp.content)
            return jsonify([{'url': f'http://localhost:5001/uploads/{filename}'}])
        return jsonify([{'url': 'https://placehold.co/320x240?text=ESP32+Error'}]), 502
    except:
        return jsonify([{'url': 'https://placehold.co/320x240?text=Connection+Refused'}]), 500

@app.route('/api/save-history', methods=['POST'])
@login_required
def save_history():
    try:
        data = request.get_json()
        camera_id = data.get('camera_id', 1)
        filename = f"chart_cam{camera_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        if data.get('chartImage'):
            img_data = data['chartImage'].split(',', 1)[1] if ',' in data['chartImage'] else data['chartImage']
            with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "wb") as f: f.write(base64.b64decode(img_data))
        item = HistoryItem(camera_id=camera_id, chart_image=filename, photo_image=data.get('photoUrl'), sensor_data=json.dumps(data.get('sensorData')))
        db.session.add(item)
        db.session.commit()
        return jsonify({"message": "Saved", "id": item.id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    camera_id = request.args.get('camera_id', type=int)
    query = HistoryItem.query.filter_by(camera_id=camera_id) if camera_id else HistoryItem.query
    items = query.order_by(HistoryItem.timestamp.desc()).limit(10).all()
    return jsonify([{'id': i.id, 'camera_id': i.camera_id, 'chart_image': f'/uploads/{i.chart_image}', 
                     'photo_image': i.photo_image, 'sensor_data': json.loads(i.sensor_data) if i.sensor_data else None, 
                     'timestamp': i.timestamp.strftime('%Y-%m-%d %H:%M:%S')} for i in items])

@app.route('/api/history/<int:id>', methods=['DELETE'])
@login_required
def delete_history(id):
    db.session.delete(HistoryItem.query.get_or_404(id))
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)