import os
import json
from dotenv import load_dotenv
load_dotenv()
from flask_cors import CORS
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
# ---------------- JWT関連のインポート ----------------
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager
import datetime
# ---------------- 追加でrequestsをインポート ----------------
import requests

import google.generativeai as genai
from PIL import Image
from io import BytesIO
from werkzeug.datastructures import FileStorage

# .envファイルからGemini APIキーを読み込む
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in environment variables")
genai.configure(api_key=GEMINI_API_KEY)

# Geminiモデルのインスタンスをグローバルに定義
gemini_model = genai.GenerativeModel('gemini-2.5-flash')

# データベースの初期設定とFlaskアプリの初期化
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder='static')
CORS(app)

# UPLOAD_FOLDERの設定をappの定義後に行う
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
db = SQLAlchemy(app)

# ---------------- JWTの設定 ----------------
app.config["JWT_SECRET_KEY"] = "your-super-secret-key"  # あなたのシークレットキーに変更
jwt = JWTManager(app)

# JWTエラーハンドラーを追加
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    print(f"Token expired: {jwt_header}, {jwt_payload}")
    return jsonify({'msg': 'Token has expired'}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    print(f"Invalid token error: {error}")
    print(f"Error type: {type(error)}")
    print(f"Error details: {str(error)}")
    return jsonify({'msg': f'Invalid token: {str(error)}'}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    print(f"Missing token error: {error}")
    return jsonify({'msg': 'Authorization header is missing'}), 401

# アップロードフォルダが存在しない場合は作成
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# データベースモデルの定義
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Cloth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_path = db.Column(db.String(200), nullable=False)
    
    # Geminiから取得する新しい属性
    item_type = db.Column(db.String(50)) # 例: T-shirt, Jeans
    color_name = db.Column(db.String(50)) # 例: blue
    color_hex = db.Column(db.String(10)) # 例: #0000FF
    pattern = db.Column(db.String(50)) # 例: solid, striped
    material = db.Column(db.String(50)) # 例: cotton, denim
    style = db.Column(db.String(50)) # 例: casual, formal
    recommended_temp = db.Column(db.String(50)) # 例: 20-25°C
    recommended_humidity = db.Column(db.String(50)) # 例: low to medium
    
    def to_dict(self):
        return {
            'id': self.id,
            'image_path': self.image_path,
            'item_type': self.item_type,
            'color_name': self.color_name,
            'pattern': self.pattern,
            'material': self.material,
            'style': self.style,
            'recommended_temp': self.recommended_temp,
            'recommended_humidity': self.recommended_humidity
        }

# データベースの初期化
with app.app_context():
    db.create_all()

# --- API エンドポイントの実装 ---

@app.route('/')
def index():
    return render_template('index.html')

# ユーザー登録API
@app.route('/api/register', methods=['POST'])
def register_user():
    data = request.json
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Missing data'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409

    new_user = User(name=data.get('name'), email=data['email'])
    new_user.set_password(data['password'])
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

# ---------------- ログインAPI ----------------
@app.route("/api/login", methods=["POST"])
def login():
    email = request.json.get("email", None)
    password = request.json.get("password", None)
    
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"msg": "Bad email or password"}), 401

    # ユーザーIDを文字列としてペイロードに設定してトークンを生成
    access_token = create_access_token(identity=str(user.id))
    return jsonify(access_token=access_token)

# ---------------- デバッグ用：JWTトークン検証エンドポイント ----------------
@app.route('/api/debug-token', methods=['GET'])
@jwt_required()
def debug_token():
    current_user_id = int(get_jwt_identity())
    return jsonify({
        'user_id': current_user_id,
        'user_id_type': str(type(current_user_id)),
        'message': 'Token is valid'
    })

# ---------------- デバッグ用：手動JWTトークン検証エンドポイント ----------------
@app.route('/api/debug-token-manual', methods=['POST'])
def debug_token_manual():
    try:
        auth_header = request.headers.get('Authorization')
        print(f"Manual debug - Authorization header: {auth_header}")
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No valid Authorization header'}), 401
            
        token = auth_header.split(' ')[1]
        print(f"Manual debug - Token: {token}")
        
        # 手動でJWTトークンをデコード
        from flask_jwt_extended import decode_token
        decoded_token = decode_token(token)
        print(f"Manual debug - Decoded token: {decoded_token}")
        
        return jsonify({
            'decoded_token': decoded_token,
            'message': 'Token decoded successfully'
        })
        
    except Exception as e:
        print(f"Manual debug - Error: {str(e)}")
        return jsonify({'error': f'Token decode failed: {str(e)}'}), 401

# ---------------- 服の登録API (JWT認証を追加) ----------------
# ---------------- 服の登録API (Gemini APIを統合) ----------------
@app.route('/api/clothes', methods=['POST'])
@jwt_required()
def register_cloth():
    try:
        current_user_id = int(get_jwt_identity())

        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file'}), 400

        # ファイルをメモリ上で操作するための処理
        img_bytes = file.read()
        
        # ファイルサイズチェック
        if len(img_bytes) == 0:
            return jsonify({'error': 'Empty file'}), 400
            
        try:
            pil_image = Image.open(BytesIO(img_bytes))
            # 画像をRGB形式に変換（RGBAやPモードの場合）
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
        except Exception as e:
            print(f"Image processing error: {e}")
            return jsonify({'error': f'Invalid image file: {str(e)}'}), 400

        # Gemini APIに投げるプロンプト
        prompt_text = (
            """You are an AI assistant designed to analyze clothing images for a personal wardrobe app. Your task is to accurately identify the garment and provide detailed attributes in a strict JSON format. Assume the garment will be worn in a **casual, everyday setting as a single-layer top or outer garment** (e.g., a tank top is worn as a top, not an undergarment). Based on the garment's visual cues like material, thickness, and style, infer the recommended temperature and humidity conditions for wearing it. For recommended_humidity, provide a numerical range of a percentage (e.g., "30-50%"). If the humidity is high, infer a range like "60-80%". If low, use "20-40%". If a specific attribute cannot be determined with high confidence, use 'unknown'. The JSON object must contain only the keys: 'item_type', 'color_name', 'color_hex', 'pattern', 'material', 'style', 'recommended_temp', and 'recommended_humidity'. Do not include any other text."""
        )
        
        # Gemini APIを呼び出して情報を取得
        try:
            contents = [prompt_text, pil_image]
            response = gemini_model.generate_content(contents)
            
            # レスポンスからJSONを抽出
            try:
                response_text = response.text.strip()
                # マークダウンのコードブロック記法を除去
                if response_text.startswith('```json'):
                    response_text = response_text[7:]  # ```json を除去
                if response_text.endswith('```'):
                    response_text = response_text[:-3]  # ``` を除去
                response_text = response_text.strip()
                
                gemini_data = json.loads(response_text)
            except json.JSONDecodeError:
                print("Gemini response is not valid JSON:", response.text)
                return jsonify({'error': 'Failed to parse Gemini API response'}), 500
                
        except Exception as e:
            print(f"Gemini API error: {e}")
            # API制限に達した場合は登録を拒否
            if "quota" in str(e).lower() or "429" in str(e):
                return jsonify({'error': 'AI分析サービスが一時的に利用できません。しばらく時間をおいてから再試行してください。'}), 503
            else:
                return jsonify({'error': f'AI分析に失敗しました: {str(e)}'}), 500

        # ファイルをサーバーに保存
        filename = secure_filename(file.filename)
        # 拡張子を強制的に.jpgに変更
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            filename = filename.rsplit('.', 1)[0] + '.jpg'
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pil_image.save(file_path, 'JPEG', quality=95)
        
        # データベースに保存
        new_cloth = Cloth(
            user_id=current_user_id,
            image_path=os.path.join('uploads', filename),
            item_type=gemini_data.get('item_type'),
            color_name=gemini_data.get('color_name'),
            color_hex=gemini_data.get('color_hex'),
            pattern=gemini_data.get('pattern'),
            material=gemini_data.get('material'),
            style=gemini_data.get('style'),
            recommended_temp=gemini_data.get('recommended_temp'),
            recommended_humidity=gemini_data.get('recommended_humidity')
        )
        
        db.session.add(new_cloth)
        db.session.commit()
        
        return jsonify({'message': 'Cloth registered successfully'}), 201

    except Exception as e:
        print(f"Error in register_cloth: {str(e)}")
        db.session.rollback()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# ---------------- コーディネート提案API (JWT認証を追加) ----------------
@app.route('/api/outfit', methods=['GET'])
@jwt_required()
def get_outfit():
    try:
        current_user_id = int(get_jwt_identity())
        user_clothes = Cloth.query.filter_by(user_id=current_user_id).all()
        
        # クエリパラメータから緯度と経度を取得
        lat = request.args.get('lat')
        lon = request.args.get('lon')

        weather_data = None
        
        # 緯度・経度が存在する場合、天気APIを呼び出す
        if lat and lon:
            # OpenWeatherMapのAPIキーを環境変数から取得
            api_key = os.getenv("OPENWEATHER_API_KEY")
            if not api_key:
                print("OPENWEATHER_API_KEY is not set. Using default weather data.")
                weather_data = {'temperature': 22, 'humidity': 65}
            else:
                weather_api_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={api_key}"
                try:
                    weather_response = requests.get(weather_api_url, timeout=5)
                    weather_response.raise_for_status() # HTTPエラーが発生した場合に例外を発生させる
                    weather_data_raw = weather_response.json()

                    temperature = weather_data_raw['main']['temp']
                    humidity = weather_data_raw['main']['humidity']
                    
                    weather_data = {
                        'temperature': temperature,
                        'humidity': humidity,
                    }
                    print(f"Real-time Weather data: {weather_data}")

                except requests.exceptions.RequestException as e:
                    print(f"Error fetching weather data: {e}")
                    weather_data = {'temperature': 22, 'humidity': 65} # フォールバック

        # 緯度・経度が提供されない場合、デフォルトデータを使用
        if not weather_data:
            weather_data = {'temperature': 22, 'humidity': 65}
            print("Using default weather data.")

        # 天気情報に基づいてトップスを選定
        suggested_top = None
        temperature = weather_data['temperature']
        
        # ログを追加: 現在の気温と全アイテムの情報を表示
        print(f"--- Outfit Generation Start ---")
        print(f"Current Temperature: {temperature}°C")
        
        # 適切なトップス候補のリストを拡張
        top_types = ['t-shirt', 'blouse', 'shirt', 'tank top', 'polo', 'sweater', 'hoodie', 'jacket']
        
        # フォールバックのための変数を初期化
        closest_cloth = None
        min_temp_diff = float('inf')
        highest_max_temp_cloth = None
        highest_max_temp = -float('inf') 

        # 1. 適正温度範囲内のトップスを検索し、同時にフォールバック候補も収集する
        for cloth in user_clothes:
            if cloth.item_type and cloth.item_type.lower() in top_types and cloth.recommended_temp:
                try:
                    temp_range_str = cloth.recommended_temp.replace('°C', '').strip()
                    temp_range = temp_range_str.split('-')
                    if len(temp_range) == 2:
                        min_temp = float(temp_range[0])
                        max_temp = float(temp_range[1])
                        
                        # 気温が範囲内なら候補にする
                        if min_temp <= temperature <= max_temp:
                            suggested_top = cloth
                            print(f"Perfect match found: {suggested_top.item_type} with temp range {suggested_top.recommended_temp}")
                            break
                        
                        # 範囲外の場合、最も近い温度差を計算
                        temp_diff = min(abs(temperature - min_temp), abs(temperature - max_temp))
                        if temp_diff < min_temp_diff:
                            min_temp_diff = temp_diff
                            closest_cloth = cloth
                        
                        # 最高気温が最も高い服を記録
                        if max_temp > highest_max_temp:
                            highest_max_temp = max_temp
                            highest_max_temp_cloth = cloth
                        
                        print(f"Checking: {cloth.item_type} ({cloth.recommended_temp}) is not in range. Diff: {temp_diff:.2f}")

                    else:
                        print(f"Skipping {cloth.item_type}: recommended_temp format is invalid - '{cloth.recommended_temp}'")

                except (ValueError, IndexError):
                    print(f"Error parsing temp for {cloth.item_type}: '{cloth.recommended_temp}'")
                    continue
        
        # 2. 適切なトップスが見つからなかった場合のフォールバックロジック
        if not suggested_top:
            print("No perfect match found. Selecting the best alternative.")
            
            # 最高気温が最も高い服を優先して選択する
            if highest_max_temp_cloth:
                suggested_top = highest_max_temp_cloth
                print(f"Using highest max temp match as fallback: {suggested_top.item_type} ({suggested_top.recommended_temp}) for {temperature}°C")
            # それも見つからなければ、最も近い温度差の服を選択
            elif closest_cloth:
                suggested_top = closest_cloth
                print(f"Using closest temperature match as fallback: {suggested_top.item_type} ({suggested_top.recommended_temp}) for {temperature}°C")
        
        if not suggested_top:
            print("--- Outfit Generation Failed ---")
            return jsonify({'message': 'No suitable top found'}), 404

        print(f"--- Outfit Generation Success ---")
        
        # Geminiにボトムスとアウターの提案を依頼
        outfit_prompt = (
            f"Based on a {suggested_top.color_name} {suggested_top.item_type} ({suggested_top.style} style) with {suggested_top.material} material, "
            f"suggest a matching bottom and a suitable jacket for a temperature of {temperature}°C. "
            f"Provide the output as a JSON object with 'bottoms' and 'jackets' arrays, each containing items with 'item_type' and 'color_name'."
        )
        try:
            response = gemini_model.generate_content(outfit_prompt)

            print(f"Gemini's Outfit Suggestion (Raw): {response.text}") 
            # レスポンスからJSONを抽出
            response_text = response.text.strip()
            # マークダウンのコードブロック記法を除去
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            # 再度trimして、末尾の余分な改行やスペースを削除
            response_text = response_text.strip()
            
            gemini_outfit = json.loads(response_text)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"Gemini response is not valid JSON. Response text: '{response_text}'")
            return jsonify({'error': f'Failed to parse Gemini API response: {str(e)}'}), 500
        
        # データベースから提案されたアイテムを選択
        suggested_outfit = [suggested_top.to_dict()]
        
        # ボトムスの選定
        for bottom_suggestion in gemini_outfit.get('bottoms', []):
            match = next((c for c in user_clothes if c.item_type == bottom_suggestion['item_type'] and c.color_name == bottom_suggestion['color_name']), None)
            if match:
                suggested_outfit.append(match.to_dict())
                break
        
        # アウターの選定
        for jacket_suggestion in gemini_outfit.get('jackets', []):
            match = next((c for c in user_clothes if c.item_type == jacket_suggestion['item_type'] and c.color_name == jacket_suggestion['color_name']), None)
            if match:
                suggested_outfit.append(match.to_dict())
                break
        
        return jsonify(suggested_outfit)
        
    except Exception as e:
        print(f"Error in get_outfit: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# ---------------- 登録された服の一覧を取得するAPI ----------------
@app.route('/api/clothes', methods=['GET'])
@jwt_required()
def get_clothes():
    try:
        current_user_id = int(get_jwt_identity())
        user_clothes = Cloth.query.filter_by(user_id=current_user_id).all()

        print("--- Checking saved 'recommended_temp' data ---")
        for cloth in user_clothes:
            print(f"  Item ID: {cloth.id}")
            print(f"  Item Type: {cloth.item_type}")
            print(f"  Recommended Temp Value: '{cloth.recommended_temp}'")
            print(f"  Recommended Temp Type: {type(cloth.recommended_temp)}")
            print("-" * 20)
        
        result = [cloth.to_dict() for cloth in user_clothes]
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in get_clothes: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

if __name__ == '__main__':
    # .envファイルからAPIキーを読み込む（必要に応じて）
    # from dotenv import load_dotenv
    # load_dotenv()
    app.run(debug=True, port=5001)
