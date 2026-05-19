"""
PetFamily - Платформа для адоптування домашніх тварин
Версія з ПОВНОЮ безпекою та SEO оптимізацією
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import re
import logging
from functools import wraps
import secrets
from collections import defaultdict

from flask_sqlalchemy import SQLAlchemy

# ============= КОНФІГУРАЦІЯ БЕЗПЕКИ =============
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

db_url = os.environ.get('DATABASE_URL', 'sqlite:///petfamily.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024

db = SQLAlchemy(app)

# ============= ЛОГУВАННЯ =============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('petfamily.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============= RATE LIMITING =============
login_attempts = defaultdict(lambda: {'count': 0, 'timestamp': None})
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 600  # 10 хвилин

def check_rate_limit(ip_address):
    """Перевірка rate limiting для IP адреси"""
    now = datetime.now()
    
    if ip_address in login_attempts:
        attempt = login_attempts[ip_address]
        
        if attempt['timestamp']:
            if now - attempt['timestamp'] > timedelta(seconds=LOCKOUT_TIME):
                login_attempts[ip_address] = {'count': 0, 'timestamp': None}
                return True
            
            if attempt['count'] >= MAX_LOGIN_ATTEMPTS:
                logger.warning(f"Rate limit exceeded for IP: {ip_address}")
                return False
    
    return True

def increment_failed_login(ip_address):
    """Збільшити лічильник невдалих спроб"""
    now = datetime.now()
    login_attempts[ip_address]['count'] += 1
    login_attempts[ip_address]['timestamp'] = now
    logger.info(f"Failed login attempt for IP: {ip_address}")

def reset_failed_login(ip_address):
    """Скинути лічильник після успішного входу"""
    login_attempts[ip_address] = {'count': 0, 'timestamp': None}


# ============= МОДЕЛІ ДАНИХ =============
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders_count = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Pet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # cats, dogs, exotic
    breed = db.Column(db.String(100))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(5))
    price = db.Column(db.Float)
    color = db.Column(db.String(50))
    emoji = db.Column(db.String(10))
    image_url = db.Column(db.Text)
    description = db.Column(db.Text)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    pet_name = db.Column(db.String(100))
    pet_type = db.Column(db.String(20))
    price = db.Column(db.Float)
    customer_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')
    ip_address = db.Column(db.String(45))

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    message = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)


# ============= ВАЛІДАЦІЯ =============
def validate_username(username):
    """Валідація імені користувача"""
    if not username or len(username) < 3 or len(username) > 50:
        return False, "Ім'я користувача повинно мати 3-50 символів"
    if not re.match(r'^[a-zA-Zа-яА-Я0-9_-]+$', username):
        return False, "Тільки букви, цифри, _, -"
    return True, ""

def validate_email(email):
    """Валідація email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Невірний формат email"
    if len(email) > 120:
        return False, "Email занадто довгий"
    return True, ""

def validate_password(password):
    """Валідація пароля"""
    if len(password) < 8:
        return False, "Пароль повинен бути мінімум 8 символів"
    if len(password) > 128:
        return False, "Пароль занадто довгий"
    if not any(c.isupper() for c in password):
        return False, "Потрібна хоча б одна велика буква"
    if not any(c.isdigit() for c in password):
        return False, "Потрібна хоча б одна цифра"
    return True, ""

def validate_phone(phone):
    """Валідація номера телефону"""
    phone = re.sub(r'\D', '', phone)
    if len(phone) < 10 or len(phone) > 15:
        return False
    return True

def sanitize_input(text):
    """Санітизація користувацького вводу для запобігання XSS"""
    if not text:
        return ""
    # Видалити HTML теги та небезпечні символи
    text = str(text)
    text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
    text = text.replace('&', '&')
    text = text.replace('<', '<')
    text = text.replace('>', '>')
    text = text.replace('"', '"')
    text = text.replace("'", '&#x27;')
    return text[:500]  # Макс 500 символів

def validate_pet_type(pet_type):
    """Валідація типу тварини - запобігання path traversal"""
    allowed_types = ['cats', 'dogs', 'exotic']
    if pet_type not in allowed_types:
        logger.warning(f"Invalid pet_type attempted: {pet_type}")
        return False
    return True

# ============= MIDDLEWARE БЕЗПЕКИ =============
@app.after_request
def set_security_headers(response):
    """Додати security headers до кожної відповіді"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Allow images, scripts, styles, and fetch/XMLHttpRequest to same origin and external HTTPS sources
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: https:; script-src 'self'; style-src 'self'; connect-src 'self'"
    response.headers['Strict-Transport-Security'] = "max-age=31536000; includeSubDomains"
    return response

# ============= ДЕКОРАТОРИ ТА ФІЛЬТРИ =============
@app.template_filter('format_date')
def format_date(value, format_str='%d.%m.%Y %H:%M'):
    """Універсальний фільтр для форматування дати"""
    if value is None:
        return ""
    if isinstance(value, str):
        # Спробувати розпарсити різні формати SQLite
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                value = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
    
    if isinstance(value, (datetime)):
        return value.strftime(format_str)
    return str(value)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def generate_csrf_token():
    """Генерувати CSRF токен"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def verify_csrf_token(token):
    """Перевірити CSRF токен"""
    session_token = session.get('_csrf_token', '')
    if not session_token or session_token != token:
        return False
    return True

# Додати CSRF токен до контексту шаблонів
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token)

@app.route('/')
def index():
    """Головна сторінка з SEO оптимізацією"""
    return render_template('index.html', 
        page_title='PetFamily - Знайди домашнього улюбленця',
        page_description='Платформа для адоптування котиків, собачок та екзотичних тварин. Зменш самотність новою дружбою!'
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Реєстрація з повною безпекою"""
    try:
        if request.method == 'POST':
            # Перевірити CSRF токен
            if not verify_csrf_token(request.form.get('csrf_token', '')):
                logger.warning(f"CSRF attack attempt from {request.remote_addr}")
                return render_template('register.html', error='Помилка безпеки. Спробуй ще раз.')
            
            # Отримати та санітизувати дані
            username = sanitize_input(request.form.get('username', ''))
            email = sanitize_input(request.form.get('email', ''))
            password = request.form.get('password', '')
            
            # Валідація
            valid, msg = validate_username(username)
            if not valid:
                logger.info(f"Invalid username format: {username[:20]}")
                return render_template('register.html', error=msg)
            
            valid, msg = validate_email(email)
            if not valid:
                logger.info(f"Invalid email format: {email[:20]}")
                return render_template('register.html', error=msg)
            
            valid, msg = validate_password(password)
            if not valid:
                return render_template('register.html', error=msg)
            
            # Перевірити, чи користувач вже існує
            if User.query.filter_by(username=username).first():
                logger.warning(f"Attempt to register existing user: {username}")
                return render_template('register.html', error='Користувач вже існує!')
            
            # Зберегти користувача
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            
            logger.info(f"New user registered successfully: {username}")
            return redirect(url_for('login'))
        
        return render_template('register.html')
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return render_template('register.html', error='Сталась помилка. Спробуй ще раз.')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вхід з rate limiting та logging"""
    try:
        if request.method == 'POST':
            ip_address = request.remote_addr
            
            # Перевірити rate limit
            if not check_rate_limit(ip_address):
                logger.warning(f"Login rate limit triggered for IP: {ip_address}")
                return render_template('login.html', 
                    error='Занадто багато спроб. Спробуй через 10 хвилин.')
            
            # Перевірити CSRF
            if not verify_csrf_token(request.form.get('csrf_token', '')):
                logger.warning(f"CSRF attack attempt during login from {ip_address}")
                return render_template('login.html', error='Помилка безпеки.')
            
            username = sanitize_input(request.form.get('username', ''))
            password = request.form.get('password', '')
            
            # Перевірити дані
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                session.permanent = True
                session['user_id'] = username
                reset_failed_login(ip_address)
                logger.info(f"Successful login: {username}")
                return redirect(url_for('catalog'))
            
            # Невдалий вхід
            increment_failed_login(ip_address)
            logger.warning(f"Failed login attempt for username: {username[:20]}")
            return render_template('login.html', error='Невірні дані для входу!')
        
        return render_template('login.html')
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return render_template('login.html', error='Сталась помилка. Спробуй ще раз.')

@app.route('/logout')
def logout():
    """Вихід з логуванням"""
    user = session.get('user_id')
    logger.info(f"User logged out: {user}")
    session.clear()
    return redirect(url_for('index'))

@app.route('/catalog')
def catalog():
    """Каталог тварин"""
    return render_template('catalog.html',
        page_title='Каталог - Знайди свого друга | PetFamily',
        page_description='Переглядай котиків, собачок та екзотичних тварин. Фільтруй за породою, віком, кольором.'
    )

@app.route('/api/pets')
def get_pets():
    """API для отримання тварин з валідацією"""
    try:
        # Валідація pet_type - запобігання path traversal
        pet_type = request.args.get('type', 'cats')
        if not validate_pet_type(pet_type):
            return jsonify({'error': 'Invalid pet type'}), 400
        
        breed = sanitize_input(request.args.get('breed', ''))
        gender = request.args.get('gender', '')
        age = request.args.get('age', '')
        color = sanitize_input(request.args.get('color', ''))
        sort = request.args.get('sort', 'name')
        
        # Валідація сортування
        allowed_sorts = ['name', 'price_asc', 'price_desc', 'age_asc', 'age_desc']
        if sort not in allowed_sorts:
            sort = 'name'
        
        # Валідація gender
        if gender and gender not in ['М', 'Ж']:
            gender = ''
        
        # Отримання тварин з бази даних
        query = Pet.query.filter_by(type=pet_type)
        
        # Фільтрація
        if breed:
            query = query.filter(Pet.breed.ilike(f'%{breed}%'))
        if gender:
            query = query.filter_by(gender=gender)
        if age:
            try:
                age_int = int(age)
                if 0 < age_int < 30:
                    query = query.filter_by(age=age_int)
            except (ValueError, TypeError):
                pass
        if color:
            query = query.filter(Pet.color.ilike(f'%{color}%'))
        
        # Сортування
        if sort == 'price_asc':
            query = query.order_by(Pet.price.asc())
        elif sort == 'price_desc':
            query = query.order_by(Pet.price.desc())
        elif sort == 'age_asc':
            query = query.order_by(Pet.age.asc())
        elif sort == 'age_desc':
            query = query.order_by(Pet.age.desc())
        else:
            query = query.order_by(Pet.name.asc())
            
        pets = query.all()
        
        # Форматування результату для JSON
        pets_list = []
        for p in pets:
            pets_list.append({
                'id': p.id,
                'name': p.name,
                'breed': p.breed,
                'age': p.age,
                'gender': p.gender,
                'price': p.price,
                'color': p.color,
                'emoji': p.emoji,
                'image_url': p.image_url,
                'description': p.description
            })
        
        logger.info(f"Pets fetched - type: {pet_type}, count: {len(pets_list)}")
        return jsonify(pets_list)
    
    except Exception as e:
        logger.error(f"Error fetching pets: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/pet/<pet_type>/<int:pet_id>')
def pet_detail(pet_type, pet_id):
    """Деталі тварини з валідацією"""
    try:
        if not validate_pet_type(pet_type):
            return redirect(url_for('catalog'))
        
        # Перевірити ID
        if not isinstance(pet_id, int) or pet_id < 1 or pet_id > 1000:
            return redirect(url_for('catalog'))
        
        pet = Pet.query.filter_by(type=pet_type, id=pet_id).first()
        
        if not pet:
            logger.warning(f"Pet not found: {pet_type}/{pet_id}")
            return redirect(url_for('catalog'))
        
        return render_template('pet_detail.html', 
            pet=pet, 
            pet_type=pet_type,
            page_title=f"{pet.name} - {pet.breed} | PetFamily",
            page_description=f"Знайомся з {pet.name}! {pet.description} Ціна: ₴{pet.price}"
        )
    except Exception as e:
        logger.error(f"Pet detail error: {str(e)}")
        return redirect(url_for('catalog'))

@app.route('/order/<pet_type>/<int:pet_id>', methods=['GET', 'POST'])
@login_required
def order(pet_type, pet_id):
    """Замовлення з безпекою та валідацією"""
    try:
        if not validate_pet_type(pet_type):
            return redirect(url_for('catalog'))
        
        # Знайти тварину
        pet = Pet.query.filter_by(type=pet_type, id=pet_id).first()
        
        if not pet:
            return redirect(url_for('catalog'))
        
        if request.method == 'POST':
            # Перевірити CSRF
            if not verify_csrf_token(request.form.get('csrf_token', '')):
                logger.warning(f"CSRF attack during order from {request.remote_addr}")
                return render_template('order.html', pet=pet, pet_type=pet_type, 
                    error='Помилка безпеки.')
            
            # Валідація форми
            name = sanitize_input(request.form.get('name', ''))
            phone = sanitize_input(request.form.get('phone', ''))
            email = sanitize_input(request.form.get('email', ''))
            address = sanitize_input(request.form.get('address', ''))
            
            # Перевірити заповненість
            if not all([name, phone, email, address]):
                return render_template('order.html', pet=pet, pet_type=pet_type,
                    error='Заповни всі поля!')
            
            # Валідація
            if not validate_phone(phone):
                return render_template('order.html', pet=pet, pet_type=pet_type,
                    error='Невірний номер телефону!')
            
            valid, msg = validate_email(email)
            if not valid:
                return render_template('order.html', pet=pet, pet_type=pet_type,
                    error='Невірний email!')
            
            if len(address) < 5 or len(address) > 500:
                return render_template('order.html', pet=pet, pet_type=pet_type,
                    error='Адреса повинна мати 5-500 символів!')
            
            # Створити замовлення
            new_order = Order(
                user_id=session['user_id'],
                pet_name=pet.name,
                pet_type=pet_type,
                price=pet.price,
                customer_name=name,
                phone=phone,
                email=email,
                address=address,
                ip_address=request.remote_addr
            )
            db.session.add(new_order)
            
            # Оновити статистику користувача
            user = User.query.filter_by(username=session['user_id']).first()
            if user:
                user.orders_count += 1
            
            db.session.commit()
            
            logger.info(f"Order created for user: {session['user_id']}, Pet: {pet.name}")
            return redirect(url_for('order_success', order_id=new_order.id))
        
        return render_template('order.html', pet=pet, pet_type=pet_type)
    
    except Exception as e:
        logger.error(f"Order error: {str(e)}")
        return redirect(url_for('catalog'))

@app.route('/order_success/<int:order_id>')
@login_required
def order_success(order_id):
    """Сторінка успішного замовлення"""
    try:
        order = Order.query.get_or_404(order_id)
        if order.user_id != session['user_id']:
            return redirect(url_for('catalog'))
        return render_template('order_success.html', order=order)
    except Exception as e:
        logger.error(f"Order success page error: {str(e)}")
        return redirect(url_for('catalog'))


@app.route('/my_orders')
@login_required
def my_orders():
    """Мої замовлення - тільки користувача"""
    try:
        user_orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.date.desc()).all()
        logger.info(f"Orders viewed for user: {session['user_id']}, count: {len(user_orders)}")
        return render_template('my_orders.html', 
            orders=user_orders,
            page_title='Мої замовлення | PetFamily'
        )
    except Exception as e:
        logger.error(f"My orders error: {str(e)}")
        return redirect(url_for('catalog'))

@app.route('/profile')
@login_required
def profile():
    """Профіль користувача"""
    try:
        user_data = User.query.filter_by(username=session['user_id']).first()
        return render_template('profile.html', 
            username=session['user_id'],
            user_data=user_data,
            page_title='Мій профіль | PetFamily'
        )
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return redirect(url_for('index'))

# ============= API ПОВІДОМЛЕНЬ =============
@app.route('/api/message', methods=['POST'])
def receive_message():
    """Ендпоінт для контактної форми"""
    try:
        data = request.get_json()
        if not data:
            # Fallback for form data if needed
            name = sanitize_input(request.form.get('name', ''))
            email = sanitize_input(request.form.get('email', ''))
            message = sanitize_input(request.form.get('message', ''))
        else:
            name = sanitize_input(data.get('name', ''))
            email = sanitize_input(data.get('email', ''))
            message = sanitize_input(data.get('message', ''))

        if not name or not email or not message:
            return jsonify({'error': 'All fields are required'}), 400

        new_msg = ContactMessage(name=name, email=email, message=message)
        db.session.add(new_msg)
        db.session.commit()

        logger.info(f"New contact message from: {email}")
        return jsonify({'status': 'success', 'message': 'Message received'})
    except Exception as e:
        logger.error(f"Contact message error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# ============= ROBOTS.TXT =============
@app.route('/robots.txt')
def robots():
    """Robots.txt для пошукових систем"""
    return '''User-agent: *
Allow: /
Disallow: /admin
Disallow: /api/internal
Sitemap: https://petfamily.ua/sitemap.xml
Crawl-delay: 1
'''

# ============= SITEMAP.XML =============
@app.route('/sitemap.xml')
def sitemap():
    """Sitemap для SEO"""
    urls = [
        {'loc': '/', 'priority': '1.0'},
        {'loc': '/catalog', 'priority': '0.9'},
        {'loc': '/register', 'priority': '0.8'},
        {'loc': '/login', 'priority': '0.8'},
    ]
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        xml += f'  <url>\n'
        xml += f'    <loc>{url["loc"]}</loc>\n'
        xml += f'    <priority>{url["priority"]}</priority>\n'
        xml += f'    <lastmod>{datetime.now().isoformat()}</lastmod>\n'
        xml += f'  </url>\n'
    xml += '</urlset>'
    
    return xml, 200, {'Content-Type': 'application/xml'}

# ============= ERROR HANDLING =============
@app.errorhandler(400)
def bad_request(error):
    logger.warning(f"Bad request: {error}")
    return render_template('error.html', 
        error_code=400,
        error_message='Невірний запит'
    ), 400

@app.errorhandler(403)
def forbidden(error):
    logger.warning(f"Forbidden request: {error}")
    return render_template('error.html',
        error_code=403,
        error_message='Доступ заборонено'
    ), 403

@app.errorhandler(404)
def not_found(error):
    logger.warning(f"Page not found: {request.path}")
    return render_template('error.html',
        error_code=404,
        error_message='Сторінка не знайдена'
    ), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return render_template('error.html',
        error_code=500,
        error_message='Внутрішня помилка сервера'
    ), 500

def init_db():
    """Ініціалізація бази даних та початкове наповнення"""
    with app.app_context():
        db.create_all()
        
        if Pet.query.count() == 0:
            logger.info("Seeding database with initial pets data...")
            pets_data = [
                # Cats
                {'name': 'Мурзик', 'type': 'cats', 'breed': 'Британська короткошерста', 'age': 2, 'gender': 'М', 'price': 1500, 'color': 'Сіра', 'emoji': '😸', 'image_url': 'https://images.unsplash.com/photo-1574158622682-e40e69881006?w=500&h=500&fit=crop', 'description': 'Грайливий і дружелюбний кіт'},
                {'name': 'Сніжка', 'type': 'cats', 'breed': 'Перська', 'age': 1, 'gender': 'Ж', 'price': 2000, 'color': 'Біла', 'emoji': '😻', 'image_url': 'https://images.unsplash.com/photo-1519052537078-e6302a4968d4?w=500&h=500&fit=crop', 'description': 'Лагідна принцеса'},
                {'name': 'Тіграш', 'type': 'cats', 'breed': 'Мейн-кун', 'age': 3, 'gender': 'М', 'price': 2500, 'color': 'Рудий', 'emoji': '😺', 'image_url': 'https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=500&h=500&fit=crop', 'description': 'Велета з великим серцем'},
                {'name': 'Даша', 'type': 'cats', 'breed': 'Абіссинська', 'age': 1, 'gender': 'Ж', 'price': 1800, 'color': 'Коричневий', 'emoji': '😼', 'image_url': 'https://images.unsplash.com/photo-1574144611937-0df059b5ef3e?w=500&h=500&fit=crop', 'description': 'Енергійна і розумна'},
                {'name': 'Васька', 'type': 'cats', 'breed': 'Сфінкс', 'age': 2, 'gender': 'М', 'price': 3000, 'color': 'Рожевий', 'emoji': '😽', 'image_url': 'https://images.unsplash.com/photo-1573865526739-10659fec78a5?w=500&h=500&fit=crop', 'description': 'Унікальна та цікава'},
                {'name': 'Люся', 'type': 'cats', 'breed': 'Регдолл', 'age': 1, 'gender': 'Ж', 'price': 2200, 'color': 'Кремовий', 'emoji': '🐱', 'image_url': 'https://images.unsplash.com/photo-1495360010541-f48722b34f7d?w=500&h=500&fit=crop', 'description': 'Мяка як хмаринка'},
                # Dogs
                {'name': 'Рекс', 'type': 'dogs', 'breed': 'Німецька вівчарка', 'age': 3, 'gender': 'М', 'price': 2500, 'color': 'Білий', 'emoji': '🐕', 'image_url': 'https://images.unsplash.com/photo-1568572933382-74d440642117?w=500&h=500&fit=crop', 'description': 'Вірний помічник'},
                {'name': 'Лесі', 'type': 'dogs', 'breed': 'Золотистий ретривер', 'age': 2, 'gender': 'Ж', 'price': 2000, 'color': 'Рудий', 'emoji': '🐶', 'image_url': 'https://images.unsplash.com/photo-1552053831-71594a27632d?w=500&h=500&fit=crop', 'description': 'Найдобріша собака'},
                {'name': 'Дружок', 'type': 'dogs', 'breed': 'Лабрадор', 'age': 1, 'gender': 'М', 'price': 1800, 'color': 'Чорний', 'emoji': '🐩', 'image_url': 'https://images.unsplash.com/photo-1534361960057-19889db9621e?w=500&h=500&fit=crop', 'description': 'Грайливий і енергійний'},
                {'name': 'Афіна', 'type': 'dogs', 'breed': 'Овчарка кавказька', 'age': 4, 'gender': 'Ж', 'price': 3000, 'color': 'Білий', 'emoji': '🦮', 'image_url': 'https://images.unsplash.com/photo-1548199973-03cce0bbc87b?w=500&h=500&fit=crop', 'description': 'Гідна охоронниця'},
                {'name': 'Чіп', 'type': 'dogs', 'breed': 'Цвергшнауцер', 'age': 1, 'gender': 'М', 'price': 1500, 'color': 'Чорний', 'emoji': '🐕', 'image_url': 'https://images.unsplash.com/photo-1553322378-eb94e5966b0c?w=500&h=500&fit=crop', 'description': 'Малий але сміливий'},
                {'name': 'Белла', 'type': 'dogs', 'breed': 'Біглі', 'age': 2, 'gender': 'Ж', 'price': 1700, 'color': 'Триколір', 'emoji': '🐶', 'image_url': 'https://images.unsplash.com/photo-1505628346881-b72b27e84530?w=500&h=500&fit=crop', 'description': 'Друзелюба і товариська'},
                {'name': 'Макс', 'type': 'dogs', 'breed': 'Хаскі', 'age': 3, 'gender': 'М', 'price': 2200, 'color': 'Сіра', 'emoji': '🐕', 'image_url': 'https://images.unsplash.com/photo-1558788353-f76d92427f16?w=500&h=500&fit=crop', 'description': 'Гарна та благородна'},
                # Exotic
                {'name': 'Рарі', 'type': 'exotic', 'breed': 'Кролик', 'age': 1, 'gender': 'М', 'price': 800, 'color': 'Білий', 'emoji': '🐰', 'image_url': 'https://images.unsplash.com/photo-1583337130417-3346a1be7dee?w=500&h=500&fit=crop', 'description': 'Милий і м\'який'},
                {'name': 'Ара', 'type': 'exotic', 'breed': 'Папуга Ара', 'age': 2, 'gender': 'Ж', 'price': 5000, 'color': 'Красна', 'emoji': '🦜', 'image_url': 'https://images.unsplash.com/photo-1456926631375-92c8ce872def?w=500&h=500&fit=crop', 'description': 'Розговірлива красиця'},
                {'name': 'Генрі', 'type': 'exotic', 'breed': 'Мідь удав', 'age': 3, 'gender': 'М', 'price': 3500, 'color': 'Мідь', 'emoji': '🐍', 'image_url': 'https://images.unsplash.com/photo-1526336024174-e58f5cdd8e13?w=500&h=500&fit=crop', 'description': 'Спокійна та цікава'},
            ]
            
            for p in pets_data:
                pet = Pet(**p)
                db.session.add(pet)
            db.session.commit()
            logger.info("Database seeded successfully.")

# Ініціалізація БД (виклик для gunicorn)
init_db()

if __name__ == '__main__':
    # ВАЖНО: debug=False в продакшені!
    app.run(
        debug=os.environ.get('FLASK_ENV') == 'development',
        host='0.0.0.0',
        port=5000
    )