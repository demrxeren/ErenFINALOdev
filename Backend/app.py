import os
import datetime
import base64
import json
import requests
from flask import Flask, request, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# ==========================================
# AYARLAR (ESP32 IP ADRESİNİ BURAYA GİRECEKSİN)
# ESP32 Serial Monitor'de "Camera Ready! Use 'http://192.168.1.XX'" yazan IP
# ==========================================
ESP32_IP = "http://10.241.231.192" 

app = Flask(__name__)
CORS(app, 
     resources={r"/api/*": {"origins": "http://localhost:5173"}},
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
app.config['SECRET_KEY'] = 'super-secret-key-change-in-production'
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Klasör ve Veritabanı Ayarları
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "instance", "data.db")}'
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)

# --- Veritabanı Modelleri ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Camera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    # YENİ EKLENEN: Cihazı tanımak için MAC Adresi
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
    # İlk admin kullanıcısını oluştur (eğer yoksa)
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', is_admin=True)
        admin.set_password('123456')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created: admin/123456")

# --- Auth Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"🔐 Session check - user_id in session: {'user_id' in session}")
        print(f"🔐 Session contents: {dict(session)}")
        if 'user_id' not in session:
            print("❌ Unauthorized - no user_id in session")
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# --- Endpointler ---

# Auth Endpoints
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if user and user.check_password(data.get('password')):
        session['user_id'] = user.id
        session['is_admin'] = user.is_admin
        return jsonify({
            "message": "Login successful",
            "user": {"id": user.id, "username": user.username, "is_admin": user.is_admin}
        }), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200

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
        db.session.add(user)
        db.session.commit()
        return jsonify({"message": "User created", "id": user.id}), 201
    
    users = User.query.all()
    return jsonify([{"id": u.id, "username": u.username, "is_admin": u.is_admin} for u in users])

@app.route('/api/users/<int:id>', methods=['DELETE'])
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    if user.username == 'admin':
        return jsonify({"error": "Cannot delete admin user"}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"}), 200

# Camera Management
@app.route('/api/cameras', methods=['GET', 'POST'])
@login_required
def manage_cameras():
    try:
        if request.method == 'POST':
            if not session.get('is_admin'):
                return jsonify({"error": "Admin access required"}), 403
            data = request.get_json()
            camera = Camera(name=data.get('name'), ip_address=data.get('ip_address'), location=data.get('location'))
            db.session.add(camera)
            db.session.commit()
            return jsonify({"message": "Camera added", "id": camera.id}), 201
        
        cameras = Camera.query.all()
        return jsonify([{"id": c.id, "name": c.name, "ip_address": c.ip_address, "location": c.location} for c in cameras])
    except Exception as e:
        print(f"❌ /api/cameras error: {e}")
        import traceback
        traceback.print_exc()
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
    
    if request.method == 'DELETE':
        db.session.delete(camera)
        db.session.commit()
        return jsonify({"message": "Camera deleted"}), 200

# YENİ: CİHAZ OTOMATİK KAYIT ENDPOINT'I
@app.route('/api/register-device', methods=['POST'])
def register_device():
    try:
        data = request.get_json()
        mac = data.get('mac_address')
        ip = request.remote_addr # İstek yapan IP'yi al
        
        if not mac:
            return jsonify({"error": "MAC address required"}), 400

        # Bu MAC adresine sahip kamera var mı?
        camera = Camera.query.filter_by(mac_address=mac).first()

        if camera:
            # Varsa güncelle (IP değişmiş olabilir)
            # ESP32 IP'sini güncelle (Not: remote_addr bazen docker/proxy arkasında 127.0.0.1 görünebilir,
            # bu durumda esp kodundan IP'yi manuel göndermek gerekebilir)
            # Şimdilik varsayılan mantıkla kaydediyoruz.
            camera.ip_address = f"http://{ip}" 
            db.session.commit()
            print(f"♻️ Cihaz güncellendi: {camera.name} (ID: {camera.id}) -> IP: {ip}")
        else:
            # Yoksa yeni oluştur
            count = Camera.query.count()
            camera = Camera(
                name=f"Camera {count + 1}", # Otomatik isim: Camera 1, Camera 2...
                ip_address=f"http://{ip}",
                location="New Device",
                mac_address=mac
            )
            db.session.add(camera)
            db.session.commit()
            print(f"✨ Yeni cihaz kaydedildi: {camera.name} (ID: {camera.id})")

        return jsonify({"id": camera.id, "name": camera.name})

    except Exception as e:
        print(f"Register Error: {e}")
        return jsonify({"error": str(e)}), 500

# 1. ESP32'den Gelen Sensör Verisini Kaydet
@app.route('/api/sensor-upload', methods=['POST'])
def upload_sensor():
    try:
        data = request.get_json()
        print(f"📊 Gelen Veri: {data}") # Debug için
        
        # camera_id artık ESP32'den dinamik geliyor
        camera_id = data.get('camera_id')  
        if not camera_id:
             # Eğer ID yoksa (eski kod veya hata), 1. kameraya yazmayı dene veya hata ver
             # Şimdilik default 1 diyelim, ama ideali cihazın kendini register etmesidir.
             camera_id = 1 
             
        # Kameranın veritabanında var olup olmadığını kontrol et
        camera = Camera.query.get(camera_id)
        if not camera:
            # Eğer böyle bir kamera yoksa (örn: veritabanı silindi ama ESP32 çalışıyor)
            # Kayıt edilmediği için hata dönebilir veya geçici bir işlem yapılabilir.
            return jsonify({"error": "Camera not found. Please restart ESP32 to register."}), 404

        new_data = SensorData(
            camera_id=camera_id,
            temperature=float(data['temperature']), 
            humidity=float(data['humidity'])
        )
        db.session.add(new_data)
        db.session.commit()
        return jsonify({"message": "Data received"}), 201
    except Exception as e:
        print(f"Hata: {e}")
        return jsonify({"error": str(e)}), 400

# 2. Vue Arayüzü İçin Veri Çekme
@app.route('/api/data', methods=['GET', 'DELETE'])
@login_required
def handle_data():
    camera_id = request.args.get('camera_id', 1, type=int)
    
    if request.method == 'DELETE':
        SensorData.query.filter_by(camera_id=camera_id).delete()
        db.session.commit()
        return jsonify({"message": "Cleared"}), 200

    # Son 20 veriyi getir
    data = SensorData.query.filter_by(camera_id=camera_id).order_by(SensorData.timestamp.desc()).limit(20).all()
    # Grafikte doğru akış için listeyi ters çeviriyoruz [::-1]
    return jsonify([{
        'id': r.id, 
        'temperature': r.temperature, 
        'humidity': r.humidity, 
        'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for r in data[::-1]])

# 3. Fotoğraf Çek (ESP32'ye İstek Atar)
@app.route('/api/photos', methods=['GET'])
@login_required
def get_photos():
    camera_id = request.args.get('camera_id', 1, type=int)
    camera = Camera.query.get(camera_id)
    
    if not camera:
        return jsonify([{'url': 'https://placehold.co/320x240?text=Camera+Not+Found'}]), 404
    
    try:
        # ESP32'nin /capture adresine git
        # IP adresi veritabanından dinamik alınıyor
        esp_ip = camera.ip_address
        if not esp_ip.startswith("http"):
             esp_ip = "http://" + esp_ip
             
        print(f"📷 ESP32'ye bağlanılıyor: {esp_ip}/capture")
        resp = requests.get(f"{esp_ip}/capture", timeout=10)
        
        if resp.status_code == 200:
            filename = f"cam{camera_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            
            # Vue'ya gösterilecek URL
            local_url = f'http://localhost:5001/uploads/{filename}'
            return jsonify([{'url': local_url}])
        else:
            return jsonify([{'url': 'https://placehold.co/320x240?text=ESP32+Error'}]), 502
    except Exception as e:
        print(f"Kamera Hatası: {e}")
        return jsonify([{'url': 'https://placehold.co/320x240?text=Connection+Refused'}]), 500

# 4. Geçmişi Kaydet (Save Button)
@app.route('/api/save-history', methods=['POST'])
@login_required
def save_history():
    try:
        data = request.get_json()
        camera_id = data.get('camera_id', 1)
        filename = f"chart_cam{camera_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        
        # Base64 chart resmini kaydet
        if data.get('chartImage'):
            img_data = data['chartImage'].split(',', 1)[1] if ',' in data['chartImage'] else data['chartImage']
            with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "wb") as f:
                f.write(base64.b64decode(img_data))

        item = HistoryItem(
            camera_id=camera_id,
            chart_image=filename, 
            photo_image=data.get('photoUrl'), 
            sensor_data=json.dumps(data.get('sensorData'))
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({"message": "Saved", "id": item.id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 5. Geçmişi Listele
@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    camera_id = request.args.get('camera_id', type=int)
    query = HistoryItem.query
    if camera_id:
        query = query.filter_by(camera_id=camera_id)
    items = query.order_by(HistoryItem.timestamp.desc()).limit(10).all()
    return jsonify([{
        'id': i.id,
        'camera_id': i.camera_id,
        'chart_image': f'/uploads/{i.chart_image}', 
        'photo_image': i.photo_image,
        'sensor_data': json.loads(i.sensor_data) if i.sensor_data else None, 
        'timestamp': i.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for i in items])

# 6. Geçmiş Sil
@app.route('/api/history/<int:id>', methods=['DELETE'])
@login_required
def delete_history(id):
    item = HistoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200

# 7. Dosya Sunucu
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # 0.0.0.0 ile çalıştır ki ağdaki diğer cihazlar (ESP32) erişebilsin
    app.run(host='0.0.0.0', port=5001, debug=True)