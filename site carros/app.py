# app.py

# ... (outras importações) ...
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify # Adicionado jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime # Certifique-se que datetime está importado
import random
import shutil # Para deletar arquivos/pastas

# Importações para Flask-WTF
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired # Para uploads com Flask-WTF
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, DecimalField, IntegerField, HiddenField, MultipleFileField # Adicionado MultipleFileField e HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional, NumberRange

app = Flask(__name__)
app.secret_key = os.urandom(24) # Já existe, bom para Flask-WTF CSRF

# Configuração Flask-WTF
app.config['WTF_CSRF_ENABLED'] = True
# app.config['SECRET_KEY'] = app.secret_key # Reutilizando a secret_key já definida

DATABASE = 'database.db'
UPLOAD_FOLDER = os.path.join(app.root_path, 'static/img/user_uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
VEHICLES_PER_PAGE = 12 # Para paginação

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Definições de Formulários Flask-WTF ---
class RegistrationForm(FlaskForm):
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Cadastrar')

    def validate_username(self, username):
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username.data,)).fetchone()
        conn.close()
        if user:
            raise ValidationError('Este nome de usuário já existe. Por favor, escolha outro.')

    def validate_email(self, email):
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email.data,)).fetchone()
        conn.close()
        if user:
            raise ValidationError('Este e-mail já está registrado. Por favor, escolha outro.')

class LoginForm(FlaskForm):
    username = StringField('Nome de Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')

class VehicleForm(FlaskForm):
    brand = SelectField('Marca', validators=[DataRequired()], choices=[]) # Choices serão populadas dinamicamente
    model = SelectField('Modelo', validators=[DataRequired()], choices=[]) # Choices serão populadas dinamicamente
    year = IntegerField('Ano', validators=[DataRequired(), NumberRange(min=1900, max=datetime.now().year + 1)])
    price = DecimalField('Preço (R$)', validators=[DataRequired(), NumberRange(min=0)])
    mileage = IntegerField('Km', validators=[DataRequired(), NumberRange(min=0)])
    city = StringField('Cidade', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Descrição do Veículo', validators=[DataRequired(), Length(max=1000)])
    # Para upload de múltiplas imagens no Flask-WTF MultipleFileField é adequado
    vehicle_images = MultipleFileField('Imagens do Veículo', 
                                       validators=[
                                           # FileRequired() # Pode ser opcional na edição
                                           # FileAllowed(ALLOWED_EXTENSIONS, 'Apenas imagens!') # Não funciona bem com MultipleFileField diretamente para validação de todas
                                       ])
    # Campo para IDs de imagens a serem deletadas na edição
    delete_images_ids = StringField('DeleteImages') # Usaremos para passar IDs como string separada por vírgula
    submit = SubmitField('Anunciar Veículo')

class EditVehicleForm(VehicleForm): # Herda de VehicleForm
    submit = SubmitField('Salvar Alterações')
    # Não precisa de vehicle_images ser FileRequired na edição, pois pode-se apenas alterar texto
    # A validação de FileAllowed será feita manualmente na rota para MultipleFileField

class SearchForm(FlaskForm):
    query = StringField('Buscar por marca, modelo...', validators=[DataRequired()], render_kw={"placeholder": "Buscar por marca, modelo..."})
    submit = SubmitField('Buscar')

class PaymentForm(FlaskForm):
    vehicle_id = HiddenField(validators=[DataRequired()])
    card_number = StringField('Número do Cartão', validators=[DataRequired(), Length(min=13, max=16)])
    card_name = StringField('Nome no Cartão', validators=[DataRequired()])
    expiry_date = StringField('Validade (MM/AA)', validators=[DataRequired(), Length(min=5, max=5)]) # ex: 02/25
    cvv = StringField('CVV', validators=[DataRequired(), Length(min=3, max=4)])
    submit = SubmitField('Confirmar Compra')


# Função utilitária para uploads de arquivo
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Funções do Banco de Dados (get_db_connection e init_db permanecem as mesmas)
def get_db_connection(): 
    conn = sqlite3.connect(DATABASE) 
    conn.row_factory = sqlite3.Row 
    return conn 

def init_db(): 
    conn = get_db_connection() 
    cursor = conn.cursor() 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''') 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            year INTEGER NOT NULL,
            price REAL NOT NULL,
            mileage INTEGER,
            city TEXT,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'available', -- available, sold
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''') 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            image_path TEXT NOT NULL, 
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS carts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        )
    ''') 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        )
    ''') 
    conn.commit() 
    conn.close() 
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) 

@app.context_processor
def inject_global_vars():
    # Injeta o formulário de busca em todos os templates
    search_form_global = SearchForm()
    return {'current_year': datetime.utcnow().year, 'search_form_global': search_form_global}

with app.app_context():
    init_db() 

# Função add_demo_vehicles permanece a mesma (para brevidade, não repetida aqui)
def add_demo_vehicles(): #
    conn = get_db_connection() #
    cursor = conn.cursor() #

    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'demo_user'") #
    if cursor.fetchone()[0] == 0: #
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                       ('demo_user', 'demo@example.com', generate_password_hash('demopassword'))) #
        conn.commit() #

    demo_user_row = cursor.execute("SELECT id FROM users WHERE username = 'demo_user'").fetchone() #
    if not demo_user_row: #
        conn.close() #
        return #
    demo_user_id = demo_user_row[0] #

    cursor.execute("SELECT COUNT(DISTINCT v.id) FROM vehicles v JOIN vehicle_images vi ON v.id = vi.vehicle_id WHERE v.user_id = ?", (demo_user_id,)) #
    vehicle_count = cursor.fetchone()[0] #

    if vehicle_count < 110: #
        if vehicle_count < 20: # 
            cursor.execute("DELETE FROM vehicles WHERE user_id = ?", (demo_user_id,)) #
            conn.commit() #

        original_vehicles_data = [
            (demo_user_id, 'Volkswagen', 'Gol', 2023, 75000.00, 15000, 'São Paulo', 'Motor 1.0 flex, completo.', 'available', 'gol_g8.jpg'), #
            (demo_user_id, 'Chevrolet', 'Onix', 2024, 90000.00, 5000, 'Rio de Janeiro', 'Hatch completo, motor 1.0 turbo.', 'available', 'onix_plus.jpg'), #
            (demo_user_id, 'Hyundai', 'HB20', 2022, 68000.00, 30000, 'Belo Horizonte', 'Hatch, motor 1.0, ar, direção.', 'available', 'hb20_vision.jpg'), #
            (demo_user_id, 'Fiat', 'Cronos', 2023, 85000.00, 10000, 'Curitiba', 'Sedan espaçoso, motor 1.3.', 'available', 'cronos_drive.jpg'), #
            (demo_user_id, 'Renault', 'Kwid', 2021, 55000.00, 45000, 'Salvador', 'Carro de entrada, econômico.', 'available', 'kwid_zen.jpg'), #
            (demo_user_id, 'Toyota', 'Corolla Cross', 2024, 160000.00, 8000, 'Brasília', 'SUV híbrido, completo.', 'available', 'corolla_cross.jpg'), #
            (demo_user_id, 'Jeep', 'Renegade', 2023, 130000.00, 22000, 'Porto Alegre', 'SUV robusto, automático.', 'available', 'renegade.jpg'), #
            (demo_user_id, 'Honda', 'Civic', 2022, 175000.00, 28000, 'Recife', 'Sedan esportivo, 1.5 turbo.', 'sold', 'civic_touring.jpg'), #
            (demo_user_id, 'Ford', 'Ka', 2020, 48000.00, 60000, 'Fortaleza', 'Hatch popular, motor 1.0.', 'available', 'ka_se.jpg'), #
            (demo_user_id, 'Nissan', 'Kicks', 2023, 115000.00, 12000, 'Manaus', 'SUV compacto, design moderno.', 'available', 'kicks_advance.jpg') #
        ]
        for data in original_vehicles_data: #
            image_filename = data[-1] #
            vehicle_data = data[:-1] #
            cursor.execute("INSERT INTO vehicles (user_id, brand, model, year, price, mileage, city, description, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", vehicle_data) #
            vehicle_id = cursor.lastrowid #
            if image_filename and image_filename != 'placeholder.png': #
                 cursor.execute("INSERT INTO vehicle_images (vehicle_id, image_path) VALUES (?, ?)", (vehicle_id, image_filename)) #
            else: #
                 cursor.execute("INSERT INTO vehicle_images (vehicle_id, image_path) VALUES (?, ?)", (vehicle_id, 'placeholder.png')) #


        popular_models_data = [ #
            {'brand': 'Fiat', 'model': 'Strada', 'base_price': 100000, 'desc': 'Picape líder de vendas.', 'img': 'placeholder.png'}, #
            {'brand': 'Hyundai', 'model': 'Creta', 'base_price': 120000, 'desc': 'SUV popular e bem equipado.', 'img': 'placeholder.png'}, #
            {'brand': 'Volkswagen', 'model': 'T-Cross', 'base_price': 115000, 'desc': 'SUV compacto da VW.', 'img': 'placeholder.png'}, #
            {'brand': 'Chevrolet', 'model': 'Tracker', 'base_price': 110000, 'desc': 'SUV Chevrolet com bom mercado.', 'img': 'placeholder.png'}, #
            {'brand': 'Fiat', 'model': 'Mobi', 'base_price': 65000, 'desc': 'Carro de entrada da Fiat.', 'img': 'kwid_zen.jpg'}, #
            {'brand': 'Jeep', 'model': 'Compass', 'base_price': 180000, 'desc': 'SUV médio da Jeep, desejado.', 'img': 'renegade.jpg'}, #
            {'brand': 'Toyota', 'model': 'Hilux', 'base_price': 220000, 'desc': 'Picape robusta e confiável.', 'img': 'placeholder.png'}, #
            {'brand': 'Volkswagen', 'model': 'Nivus', 'base_price': 110000, 'desc': 'SUV coupé da Volkswagen.', 'img': 'gol_g8.jpg'}, #
            {'brand': 'Fiat', 'model': 'Pulse', 'base_price': 100000, 'desc': 'SUV compacto da Fiat.', 'img': 'cronos_drive.jpg'}, #
            {'brand': 'Hyundai', 'model': 'HB20S', 'base_price': 75000, 'desc': 'Versão sedan do HB20.', 'img': 'hb20_vision.jpg'}, #
            {'brand': 'Chevrolet', 'model': 'Montana', 'base_price': 120000, 'desc': 'Nova picape da Chevrolet.', 'img': 'onix_plus.jpg'}, #
            {'brand': 'Toyota', 'model': 'Yaris', 'base_price': 90000, 'desc': 'Hatch/Sedan da Toyota.', 'img': 'corolla_cross.jpg'}, #
            {'brand': 'Renault', 'model': 'Duster', 'base_price': 100000, 'desc': 'SUV robusto da Renault.', 'img': 'kwid_zen.jpg'}, #
            {'brand': 'Honda', 'model': 'HR-V', 'base_price': 150000, 'desc': 'SUV compacto da Honda.', 'img': 'civic_touring.jpg'}, #
            {'brand': 'Nissan', 'model': 'Versa', 'base_price': 95000, 'desc': 'Sedan da Nissan.', 'img': 'kicks_advance.jpg'}, #
            {'brand': 'Peugeot', 'model': '208', 'base_price': 80000, 'desc': 'Hatch com design moderno.', 'img': 'placeholder.png'}, #
            {'brand': 'Citroen', 'model': 'C3', 'base_price': 70000, 'desc': 'Novo C3 com proposta de SUV.', 'img': 'placeholder.png'}, #
            {'brand': 'Volkswagen', 'model': 'Polo', 'base_price': 85000, 'desc': 'Hatch compacto e moderno.', 'img': 'gol_g8.jpg'}, #
            {'brand': 'Fiat', 'model': 'Toro', 'base_price': 150000, 'desc': 'Picape intermediária da Fiat.', 'img': 'cronos_drive.jpg'}, #
            {'brand': 'Chevrolet', 'model': 'S10', 'base_price': 200000, 'desc': 'Picape média da Chevrolet.', 'img': 'onix_plus.jpg'}, #
        ]
        cities = ['São Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Curitiba', 'Salvador', 'Brasília', 'Porto Alegre', 'Recife', 'Fortaleza', 'Manaus', 'Goiânia', 'Belém', 'Campinas', 'Guarulhos', 'Osasco', 'Santos'] #
        current_year_val = datetime.now().year #

        for _ in range(100): #
            car_template = random.choice(popular_models_data) #
            year = random.randint(current_year_val - 6, current_year_val) #
            mileage = random.randint(1000, 120000) #
            price_variation = random.uniform(-0.20, 0.20) #
            price = round(car_template['base_price'] * (1 + price_variation) * ((100 - (current_year_val - year)*3)/100), 2) #
            price = max(price, car_template['base_price'] * 0.5) #
            city = random.choice(cities) #
            status = random.choice(['available'] * 8 + ['sold'] * 2) #
            description = f"{car_template['desc']} Ano {year}, de {city}. Conservado." #
            image_filename = car_template['img'] #

            cursor.execute('''INSERT INTO vehicles 
                            (user_id, brand, model, year, price, mileage, city, description, status) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (demo_user_id, car_template['brand'], car_template['model'], year, price, mileage, city, description, status)) #
            vehicle_id = cursor.lastrowid #
            if image_filename and image_filename != 'placeholder.png': #
                 cursor.execute("INSERT INTO vehicle_images (vehicle_id, image_path) VALUES (?, ?)", (vehicle_id, image_filename)) #
            else: #
                 cursor.execute("INSERT INTO vehicle_images (vehicle_id, image_path) VALUES (?, ?)", (vehicle_id, 'placeholder.png')) #
        conn.commit() #
    conn.close() #

with app.app_context():
    add_demo_vehicles()

# Funções Auxiliares para buscar dados de veículos com imagem primária (get_vehicle_with_primary_image, get_vehicles_with_primary_images)
# Permanecem as mesmas, mas serão usadas com paginação
def get_vehicle_with_primary_image(conn, vehicle_id_or_row, is_row_dict=False): #
    vehicle_dict = dict(vehicle_id_or_row) if is_row_dict else conn.execute('SELECT * FROM vehicles WHERE id = ?', (vehicle_id_or_row,)).fetchone() #
    if not vehicle_dict: #
        return None #
    
    vehicle_dict = dict(vehicle_dict) #
    
    primary_image = conn.execute( #
        "SELECT image_path FROM vehicle_images WHERE vehicle_id = ? ORDER BY id LIMIT 1", #
        (vehicle_dict['id'],) #
    ).fetchone() #
    
    vehicle_dict['display_image_url'] = primary_image['image_path'] if primary_image else 'placeholder.png' #
    return vehicle_dict #

def get_vehicles_with_primary_images(conn, query, params=(), page=None, per_page=None):
    if page and per_page:
        offset = (page - 1) * per_page
        query += f" LIMIT {per_page} OFFSET {offset}"
        
    vehicles_raw = conn.execute(query, params).fetchall()
    vehicles = []
    for v_raw in vehicles_raw:
        v = dict(v_raw) #
        primary_image = conn.execute( #
            "SELECT image_path FROM vehicle_images WHERE vehicle_id = ? ORDER BY id LIMIT 1", (v['id'],) #
        ).fetchone() #
        v['display_image_url'] = primary_image['image_path'] if primary_image else 'placeholder.png' #
        vehicles.append(v) #
    return vehicles


# --- Rotas ---
@app.route('/')
def welcome():
    conn = get_db_connection() #
    brands = sorted(list(set([row['brand'] for row in conn.execute("SELECT DISTINCT brand FROM vehicles ORDER BY brand").fetchall()]))) #
    years = sorted(list(set([row['year'] for row in conn.execute("SELECT DISTINCT year FROM vehicles ORDER BY year DESC").fetchall()]))) #
    conn.close() #
    return render_template('welcome.html', brands=brands, models=[], years=years) #

@app.route('/search')
def search():
    query_str = request.args.get('query', '')
    page = request.args.get('page', 1, type=int)

    conn = get_db_connection()
    search_query_sql = "SELECT * FROM vehicles WHERE status = 'available' AND (brand LIKE ? OR model LIKE ? OR description LIKE ?) ORDER BY price ASC"
    params = (f'%{query_str}%', f'%{query_str}%', f'%{query_str}%')
    
    vehicles = get_vehicles_with_primary_images(conn, search_query_sql, params, page=page, per_page=VEHICLES_PER_PAGE)
    
    # Contar total de veículos para paginação
    count_query = "SELECT COUNT(id) FROM vehicles WHERE status = 'available' AND (brand LIKE ? OR model LIKE ? OR description LIKE ?)"
    total_vehicles = conn.execute(count_query, params).fetchone()[0]
    conn.close()

    total_pages = (total_vehicles + VEHICLES_PER_PAGE - 1) // VEHICLES_PER_PAGE

    # Para preencher os filtros na página de resultados, se necessário (opcional para busca simples)
    # Poderia ser simplificado ou removido se a página de busca não tiver filtros laterais complexos
    conn_filters = get_db_connection()
    brands_filter = sorted(list(set(row['brand'] for row in conn_filters.execute("SELECT DISTINCT brand FROM vehicles WHERE status='available' ORDER BY brand").fetchall())))
    models_filter = sorted(list(set(row['model'] for row in conn_filters.execute("SELECT DISTINCT model FROM vehicles WHERE status='available' ORDER BY model").fetchall())))
    years_filter = sorted(list(set(row['year'] for row in conn_filters.execute("SELECT DISTINCT year FROM vehicles WHERE status='available' ORDER BY year DESC").fetchall())))
    conn_filters.close()


    return render_template('index.html', vehicles=vehicles, 
                           current_page=page, total_pages=total_pages,
                           brands=brands_filter, models=models_filter, years=years_filter,
                           search_query=query_str,
                           # Para manter valores de filtro, caso sejam adicionados à página de busca
                           selected_brand=None, selected_model=None, selected_year=None, 
                           selected_min_price=None, selected_max_price=None)


@app.route('/filter_vehicles', methods=['GET']) #
def filter_vehicles(): #
    page = request.args.get('page', 1, type=int) # Para paginação
    brand = request.args.get('brand') #
    model = request.args.get('model') #
    year = request.args.get('year') #
    min_price_str = request.args.get('min_price') #
    max_price_str = request.args.get('max_price') #

    query = "SELECT * FROM vehicles WHERE status = 'available'" #
    count_query_base = "SELECT COUNT(id) FROM vehicles WHERE status = 'available'" # Para contar total
    params = [] #

    if brand and brand != 'all': #
        query += " AND brand = ?" #
        count_query_base += " AND brand = ?" #
        params.append(brand) #
    if model and model != 'all': #
        query += " AND model = ?" #
        count_query_base += " AND model = ?" #
        params.append(model) #
    if year and year != 'all': #
        query += " AND year = ?" #
        count_query_base += " AND year = ?" #
        params.append(int(year)) #
    
    min_price_val = None
    if min_price_str: #
        try: #
            min_price_val = float(min_price_str) #
            query += " AND price >= ?" #
            count_query_base += " AND price >= ?" #
            params.append(min_price_val) #
        except ValueError: #
            flash("Valor mínimo de preço inválido.", 'error') #
    
    max_price_val = None
    if max_price_str: #
        try: #
            max_price_val = float(max_price_str) #
            query += " AND price <= ?" #
            count_query_base += " AND price <= ?" #
            params.append(max_price_val) #
        except ValueError: #
            flash("Valor máximo de preço inválido.", 'error') #
    
    query += " ORDER BY price ASC" # # A ordenação não afeta a contagem

    conn = get_db_connection() #
    vehicles = get_vehicles_with_primary_images(conn, query, tuple(params), page=page, per_page=VEHICLES_PER_PAGE) #
    
    total_vehicles = conn.execute(count_query_base, tuple(params)).fetchone()[0]
    total_pages = (total_vehicles + VEHICLES_PER_PAGE - 1) // VEHICLES_PER_PAGE
    
    brands_filter = sorted(list(set(row['brand'] for row in conn.execute("SELECT DISTINCT brand FROM vehicles WHERE status='available' ORDER BY brand").fetchall()))) #
    models_filter = []
    if brand and brand != 'all':
         models_filter = sorted(list(set(row['model'] for row in conn.execute("SELECT DISTINCT model FROM vehicles WHERE status='available' AND brand = ? ORDER BY model", (brand,)).fetchall())))
    else:
         models_filter = sorted(list(set(row['model'] for row in conn.execute("SELECT DISTINCT model FROM vehicles WHERE status='available' ORDER BY model").fetchall())))
        
    years_filter = sorted(list(set(row['year'] for row in conn.execute("SELECT DISTINCT year FROM vehicles WHERE status='available' ORDER BY year DESC").fetchall()))) #
    conn.close() #

    return render_template('index.html', vehicles=vehicles, 
                           current_page=page, total_pages=total_pages, # Para paginação
                           brands=brands_filter, models=models_filter, years=years_filter, #
                           selected_brand=brand, selected_model=model, selected_year=year, #
                           selected_min_price=min_price_str, selected_max_price=max_price_str) #

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit(): #
        username = form.username.data #
        password = form.password.data #
        conn = get_db_connection() #
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone() #
        conn.close() #
        if user and check_password_hash(user['password'], password): #
            session['user_id'] = user['id'] #
            session['username'] = user['username'] #
            flash('Login bem-sucedido!', 'success') #
            return redirect(url_for('index')) #
        else: #
            flash('Nome de usuário ou senha incorretos.', 'error') #
    return render_template('login.html', form=form) #

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit(): #
        username = form.username.data #
        email = form.email.data #
        password = form.password.data #
        hashed_password = generate_password_hash(password) #
        conn = get_db_connection() #
        try: #
            conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', #
                         (username, email, hashed_password)) #
            conn.commit() #
            flash('Cadastro realizado com sucesso! Faça login.', 'success') #
            return redirect(url_for('login')) #
        except sqlite3.IntegrityError: # # Captura erros de unicidade (username/email)
            # A validação do formulário já deve pegar isso, mas é uma segurança extra.
            flash('Nome de usuário ou e-mail já existem.', 'error') #
        finally: #
            conn.close() #
    return render_template('register.html', form=form) #

@app.route('/logout') #
def logout(): #
    session.pop('user_id', None) #
    session.pop('username', None) #
    flash('Você foi desconectado.', 'info') #
    return redirect(url_for('welcome')) #

@app.route('/index') #
def index(): #
    page = request.args.get('page', 1, type=int) # Para paginação
    conn = get_db_connection() #
    
    base_query = "SELECT * FROM vehicles WHERE status = 'available' ORDER BY id DESC"
    count_query = "SELECT COUNT(id) FROM vehicles WHERE status = 'available'"
    
    vehicles = get_vehicles_with_primary_images(conn, base_query, page=page, per_page=VEHICLES_PER_PAGE) #
    total_vehicles = conn.execute(count_query).fetchone()[0]
    total_pages = (total_vehicles + VEHICLES_PER_PAGE - 1) // VEHICLES_PER_PAGE
    
    brands = sorted(list(set(row['brand'] for row in conn.execute("SELECT DISTINCT brand FROM vehicles WHERE status='available' ORDER BY brand").fetchall()))) #
    models = sorted(list(set(row['model'] for row in conn.execute("SELECT DISTINCT model FROM vehicles WHERE status='available' ORDER BY model").fetchall()))) #
    years = sorted(list(set(row['year'] for row in conn.execute("SELECT DISTINCT year FROM vehicles WHERE status='available' ORDER BY year DESC").fetchall()))) #
    conn.close() #
    return render_template('index.html', vehicles=vehicles, 
                           current_page=page, total_pages=total_pages, # Para paginação
                           brands=brands, models=models, years=years) #

@app.route('/vehicle/<int:vehicle_id>') #
def vehicle_detail(vehicle_id): #
    conn = get_db_connection() #
    vehicle_main_data = conn.execute('SELECT v.*, u.username, u.email as seller_email FROM vehicles v JOIN users u ON v.user_id = u.id WHERE v.id = ?', (vehicle_id,)).fetchone() #
    
    if vehicle_main_data is None: #
        conn.close() #
        flash('Veículo não encontrado.', 'error') #
        return redirect(url_for('index')) #

    vehicle = dict(vehicle_main_data) #
    
    images_cursor = conn.execute("SELECT image_path FROM vehicle_images WHERE vehicle_id = ? ORDER BY id", (vehicle_id,)) #
    vehicle_images_paths = [row['image_path'] for row in images_cursor.fetchall()] #
    
    vehicle['display_image_url'] = vehicle_images_paths[0] if vehicle_images_paths else 'placeholder.png' #
    vehicle['all_image_urls'] = vehicle_images_paths #
    
    conn.close() #
    return render_template('vehicle_detail.html', vehicle=vehicle) #


@app.route('/announce', methods=['GET', 'POST']) #
def announce(): #
    if 'user_id' not in session: #
        flash('Você precisa estar logado para anunciar um veículo.', 'warning') #
        return redirect(url_for('login')) #

    form = VehicleForm()
    conn_get_brands = get_db_connection() #
    brands_choices = [(b['brand'], b['brand']) for b in conn_get_brands.execute("SELECT DISTINCT brand FROM vehicles ORDER BY brand").fetchall()] #
    form.brand.choices = [('', '-- Selecione uma Marca --')] + brands_choices
    # Models são populados via JS, mas o campo precisa existir no form
    form.model.choices = [('', '-- Selecione uma Marca Primeiro --')]
    
    if form.brand.data: # Se uma marca já foi selecionada (ex: erro de validação e recarregamento)
        models_choices = [(m['model'], m['model']) for m in conn_get_brands.execute("SELECT DISTINCT model FROM vehicles WHERE brand = ? ORDER BY model", (form.brand.data,)).fetchall()]
        form.model.choices = [('', '-- Selecione um Modelo --')] + models_choices
    conn_get_brands.close() #


    if form.validate_on_submit(): #
        user_id = session['user_id'] #
        
        conn_post = get_db_connection() #
        try: #
            cursor = conn_post.cursor() #
            cursor.execute('''INSERT INTO vehicles 
                            (user_id, brand, model, year, price, mileage, city, description, status) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (user_id, form.brand.data, form.model.data, form.year.data, form.price.data, form.mileage.data, form.city.data, form.description.data, 'available')) #
            vehicle_id = cursor.lastrowid #
            
            image_paths_stored = [] #
            # uploaded_files = request.files.getlist(form.vehicle_images.name) # Usar dados do form.vehicle_images
            uploaded_files = form.vehicle_images.data # Flask-WTF já processa isso
            
            files_processed_count = 0
            if uploaded_files: #
                for file_storage in uploaded_files: # Flask-WTF retorna uma lista de FileStorage
                    if file_storage and file_storage.filename and allowed_file(file_storage.filename): #
                        files_processed_count +=1
                        filename = secure_filename(file_storage.filename) #
                        unique_filename_base = f"{session.get('user_id', 'unknown')}_{int(datetime.now().timestamp())}" #
                        random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=4)) #
                        unique_filename = f"{unique_filename_base}_{random_suffix}_{filename}" #
                        
                        file_storage.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)) #
                        image_path_to_store = f"user_uploads/{unique_filename}" #
                        cursor.execute("INSERT INTO vehicle_images (vehicle_id, image_path) VALUES (?, ?)", #
                                       (vehicle_id, image_path_to_store)) #
                        image_paths_stored.append(image_path_to_store) #
                    elif file_storage and file_storage.filename and not allowed_file(file_storage.filename): #
                        flash(f'Arquivo de imagem inválido ignorado: {file_storage.filename}. Use png, jpg, jpeg, gif.', 'warning') #
            
            if not image_paths_stored and files_processed_count == 0 : # Se nenhuma imagem válida foi processada
                 cursor.execute("INSERT INTO vehicle_images (vehicle_id, image_path) VALUES (?, ?)", #
                               (vehicle_id, 'placeholder.png')) #


            conn_post.commit() #
            flash('Veículo anunciado com sucesso!', 'success') #
            return redirect(url_for('user_dashboard')) #
        except Exception as e: #
            conn_post.rollback() #
            flash(f'Erro ao anunciar veículo: {str(e)}', 'error') #
        finally: #
            conn_post.close() #
    # else: # DEBUG: Mostrar erros de validação
    #     if form.errors:
    #         for field, error_list in form.errors.items():
    #             for error in error_list:
    #                 flash(f"Erro no campo '{getattr(form, field).label.text}': {error}", "error")
    
    return render_template('announce.html', form=form, current_year=datetime.now().year) #


@app.route('/api/models_for_brand/<brand_name>') #
def get_models_for_brand(brand_name): #
    conn = get_db_connection() #
    models_cursor = conn.execute("SELECT DISTINCT model FROM vehicles WHERE brand = ? ORDER BY model", (brand_name,)) #
    models = [row['model'] for row in models_cursor.fetchall()] #
    conn.close() #
    return jsonify({'models': models}) #

@app.route('/user_dashboard') #
def user_dashboard(): #
    if 'user_id' not in session: #
        flash('Você precisa estar logado para acessar seu painel.', 'warning') #
        return redirect(url_for('login')) #

    user_id = session['user_id'] #
    conn = get_db_connection() #
    
    # Paginação para anúncios do usuário (exemplo, pode ser adicionada a salvos/comprados também se necessário)
    page_user_vehicles = request.args.get('page_user_vehicles', 1, type=int)
    user_vehicles_query = 'SELECT * FROM vehicles WHERE user_id = ? ORDER BY id DESC'
    user_vehicles = get_vehicles_with_primary_images(conn, user_vehicles_query, (user_id,), page=page_user_vehicles, per_page=VEHICLES_PER_PAGE) #
    total_user_vehicles = conn.execute('SELECT COUNT(id) FROM vehicles WHERE user_id = ?', (user_id,)).fetchone()[0]
    total_pages_user_vehicles = (total_user_vehicles + VEHICLES_PER_PAGE - 1) // VEHICLES_PER_PAGE
    
    saved_vehicles_query = '''
        SELECT v.* FROM vehicles v
        JOIN carts c ON v.id = c.vehicle_id
        WHERE c.user_id = ? AND v.status = 'available'
    ''' #
    saved_vehicles = get_vehicles_with_primary_images(conn, saved_vehicles_query, (user_id,)) #
    
    purchased_vehicles_query = '''
        SELECT v.*, p.purchase_date FROM vehicles v
        JOIN purchases p ON v.id = p.vehicle_id
        WHERE p.user_id = ? ORDER BY p.purchase_date DESC
    ''' #
    purchased_vehicles_raw = conn.execute(purchased_vehicles_query, (user_id,)).fetchall() #
    purchased_vehicles = [] #
    for p_raw in purchased_vehicles_raw: #
        p = dict(p_raw) #
        primary_image = conn.execute( #
            "SELECT image_path FROM vehicle_images WHERE vehicle_id = ? ORDER BY id LIMIT 1", (p['id'],) #
        ).fetchone() #
        p['display_image_url'] = primary_image['image_path'] if primary_image else 'placeholder.png' #
        purchased_vehicles.append(p) #
        
    conn.close() #
    return render_template('user_dashboard.html', user_vehicles=user_vehicles,
                           saved_vehicles=saved_vehicles, purchased_vehicles=purchased_vehicles,
                           current_page_user_vehicles=page_user_vehicles, total_pages_user_vehicles=total_pages_user_vehicles) #


@app.route('/edit_vehicle/<int:vehicle_id>', methods=['GET', 'POST']) #
def edit_vehicle(vehicle_id): #
    if 'user_id' not in session: #
        flash('Você precisa estar logado para editar um veículo.', 'warning') #
        return redirect(url_for('login')) #

    conn = get_db_connection() #
    vehicle = conn.execute('SELECT * FROM vehicles WHERE id = ? AND user_id = ?', #
                           (vehicle_id, session['user_id'])).fetchone() #

    if not vehicle: #
        flash('Veículo não encontrado ou você não tem permissão para editá-lo.', 'error') #
        conn.close() #
        return redirect(url_for('user_dashboard')) #

    form = EditVehicleForm(obj=vehicle) # Pré-popula o formulário com dados do veículo

    brands_choices = [(b['brand'], b['brand']) for b in conn.execute("SELECT DISTINCT brand FROM vehicles ORDER BY brand").fetchall()] #
    form.brand.choices = [('', '-- Selecione uma Marca --')] + brands_choices
    
    # Popula modelos baseados na marca atual do veículo
    models_choices = [(m['model'], m['model']) for m in conn.execute("SELECT DISTINCT model FROM vehicles WHERE brand = ? ORDER BY model", (vehicle['brand'],)).fetchall()]
    form.model.choices = [('', '-- Selecione um Modelo --')] + models_choices
    form.model.data = vehicle['model'] # Define o modelo atual
    form.brand.data = vehicle['brand'] # Define a marca atual
    
    current_images_cursor = conn.execute("SELECT id, image_path FROM vehicle_images WHERE vehicle_id = ? ORDER BY id", (vehicle_id,)) #
    current_images = [{'id': row['id'], 'path': row['image_path']} for row in current_images_cursor.fetchall()] #


    if form.validate_on_submit(): #
        # IDs das imagens a serem deletadas (vem como string do campo oculto)
        img_ids_to_delete_str = form.delete_images_ids.data
        images_to_delete_ids = [int(id_str) for id_str in img_ids_to_delete_str.split(',') if id_str.isdigit()]


        try: #
            cursor = conn.cursor() #
            cursor.execute('''UPDATE vehicles SET brand = ?, model = ?, year = ?, price = ?, 
                              mileage = ?, city = ?, description = ?
                              WHERE id = ?''',
                         (form.brand.data, form.model.data, form.year.data, form.price.data, 
                          form.mileage.data, form.city.data, form.description.data, vehicle_id)) #

            # Deletar imagens marcadas
            for img_id_to_delete in images_to_delete_ids: #
                img_to_delete = conn.execute("SELECT image_path FROM vehicle_images WHERE id = ? AND vehicle_id = ?", (img_id_to_delete, vehicle_id)).fetchone() #
                if img_to_delete and img_to_delete['image_path'].startswith('user_uploads/'): #
                    try: #
                        image_full_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(img_to_delete['image_path'])) #
                        if os.path.exists(image_full_path): #
                            os.remove(image_full_path) #
                    except Exception as e_file_delete: #
                        print(f"Erro ao deletar arquivo físico {img_to_delete['image_path']}: {e_file_delete}") #
                cursor.execute("DELETE FROM vehicle_images WHERE id = ?", (img_id_to_delete,)) #

            # Adicionar novas imagens
            # uploaded_files = request.files.getlist(form.vehicle_images.name) # Usar dados do form
            new_uploaded_files = form.vehicle_images.data

            if new_uploaded_files: #
                for file_storage in new_uploaded_files: #
                    if file_storage and file_storage.filename and allowed_file(file_storage.filename): #
                        filename = secure_filename(file_storage.filename) #
                        unique_filename_base = f"{session.get('user_id', 'unknown')}_{int(datetime.now().timestamp())}" #
                        random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=4)) #
                        unique_filename = f"{unique_filename_base}_{random_suffix}_{filename}" #
                        
                        file_storage.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)) #
                        image_path_to_store = f"user_uploads/{unique_filename}" #
                        cursor.execute("INSERT INTO vehicle_images (vehicle_id, image_path) VALUES (?, ?)", #
                                       (vehicle_id, image_path_to_store)) #
                    elif file_storage and file_storage.filename and not allowed_file(file_storage.filename): #
                        flash(f'Arquivo de imagem inválido ignorado: {file_storage.filename}. Use png, jpg, jpeg, gif.', 'warning') #
            
            remaining_images = conn.execute("SELECT COUNT(*) FROM vehicle_images WHERE vehicle_id = ?", (vehicle_id,)).fetchone()[0] #
            if remaining_images == 0: #
                 cursor.execute("INSERT INTO vehicle_images (vehicle_id, image_path) VALUES (?, ?)", #
                               (vehicle_id, 'placeholder.png')) #


            conn.commit() #
            flash('Veículo atualizado com sucesso!', 'success') #
            conn.close()
            return redirect(url_for('user_dashboard')) #
        except Exception as e: #
            conn.rollback() #
            flash(f'Erro ao atualizar veículo: {str(e)}', 'error') #
    # else: # DEBUG:
    #     if form.errors:
    #         for field, error_list in form.errors.items():
    #             for error in error_list:
    #                 flash(f"Erro no campo '{getattr(form, field).label.text}': {error}", "error")


    # GET request
    # Preenche dados do formulário que não são diretamente do objeto 'vehicle' se necessário
    form.year.data = vehicle['year']
    form.price.data = vehicle['price']
    form.mileage.data = vehicle['mileage']
    form.city.data = vehicle['city']
    form.description.data = vehicle['description']
    
    conn.close() #
    return render_template('edit_vehicle.html', form=form, vehicle_id=vehicle_id, current_year=datetime.now().year, current_images=current_images) #


@app.route('/delete_vehicle/<int:vehicle_id>', methods=['POST']) #
# Deveria usar um formulário WTForms para CSRF aqui também, mas para simplificar, manteremos assim por enquanto
# No entanto, idealmente, qualquer ação que modifique o estado deve ser protegida.
def delete_vehicle(vehicle_id): #
    if 'user_id' not in session: #
        flash('Você precisa estar logado para apagar um veículo.', 'warning') #
        return redirect(url_for('login')) #

    conn = get_db_connection() #
    try: #
        vehicle = conn.execute('SELECT user_id FROM vehicles WHERE id = ?', (vehicle_id,)).fetchone() #
        if not vehicle or vehicle['user_id'] != session['user_id']: #
            flash('Veículo não encontrado ou você não tem permissão para apagá-lo.', 'error') #
            return redirect(url_for('user_dashboard')) #

        images_to_delete = conn.execute("SELECT image_path FROM vehicle_images WHERE vehicle_id = ?", (vehicle_id,)).fetchall() #
        
        for img in images_to_delete: #
            image_path = img['image_path'] #
            if image_path.startswith('user_uploads/'): #
                try: #
                    file_to_delete_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(image_path)) #
                    if os.path.exists(file_to_delete_path): #
                        os.remove(file_to_delete_path) #
                except Exception as e: #
                    print(f"Erro ao deletar arquivo físico {image_path}: {e}") # 

        conn.execute('DELETE FROM vehicles WHERE id = ?', (vehicle_id,)) #
        conn.commit() #
        flash('Veículo apagado com sucesso!', 'success') #
    except Exception as e: #
        conn.rollback() #
        flash(f'Erro ao apagar veículo: {str(e)}', 'error') #
    finally: #
        conn.close() #
    return redirect(url_for('user_dashboard')) #


@app.route('/add_to_cart/<int:vehicle_id>') #
def add_to_cart(vehicle_id): #
    if 'user_id' not in session: #
        flash('Você precisa estar logado para adicionar veículos ao carrinho.', 'warning') #
        return redirect(url_for('login')) #

    user_id = session['user_id'] #
    conn = get_db_connection() #
    try: #
        vehicle_to_add = conn.execute('SELECT status FROM vehicles WHERE id = ?', (vehicle_id,)).fetchone() #
        if not vehicle_to_add: #
            flash('Veículo não encontrado.', 'error') #
            conn.close() #
            return redirect(request.referrer or url_for('index')) #
        
        if vehicle_to_add['status'] == 'sold': #
            flash('Este veículo já foi vendido e não pode ser adicionado ao carrinho.', 'error') #
        else: #
            existing_item = conn.execute('SELECT * FROM carts WHERE user_id = ? AND vehicle_id = ?', (user_id, vehicle_id)).fetchone() #
            if existing_item: #
                flash('Este veículo já está no seu carrinho.', 'info') #
            else: #
                conn.execute('INSERT INTO carts (user_id, vehicle_id) VALUES (?, ?)', (user_id, vehicle_id)) #
                conn.commit() #
                flash('Veículo adicionado ao seu carrinho!', 'success') #
    except Exception as e: #
        flash(f'Erro ao adicionar veículo ao carrinho: {str(e)}', 'error') #
    finally: #
        conn.close() #
    return redirect(request.referrer or url_for('vehicle_detail', vehicle_id=vehicle_id)) #

@app.route('/remove_from_cart/<int:vehicle_id>') #
def remove_from_cart(vehicle_id): #
    if 'user_id' not in session: #
        flash('Você precisa estar logado para remover veículos do carrinho.', 'warning') #
        return redirect(url_for('login')) #
    user_id = session['user_id'] #
    conn = get_db_connection() #
    try: #
        conn.execute('DELETE FROM carts WHERE user_id = ? AND vehicle_id = ?', (user_id, vehicle_id)) #
        conn.commit() #
        flash('Veículo removido do seu carrinho.', 'info') #
    except Exception as e: #
        flash(f'Erro ao remover veículo do carrinho: {str(e)}', 'error') #
    finally: #
        conn.close() #
    return redirect(url_for('user_dashboard')) #

@app.route('/checkout/<int:vehicle_id>', methods=['GET', 'POST']) #
def checkout(vehicle_id): #
    if 'user_id' not in session: #
        flash('Você precisa estar logado para prosseguir com a compra.', 'warning') #
        return redirect(url_for('login')) #
    
    conn = get_db_connection() #
    vehicle_data = conn.execute('SELECT * FROM vehicles WHERE id = ? AND status = "available"', (vehicle_id,)).fetchone() #
    
    if vehicle_data is None: #
        flash('Veículo não disponível para compra ou não encontrado.', 'error') #
        conn.close() #
        return redirect(url_for('index')) #
    
    vehicle = get_vehicle_with_primary_image(conn, vehicle_data, is_row_dict=True) #
    conn.close() #
    
    form = PaymentForm()
    form.vehicle_id.data = vehicle_id # Preenche o ID do veículo no formulário

    # A rota process_purchase será chamada pelo submit do PaymentForm,
    # então não precisamos mais da lógica POST aqui.
    # O process_purchase já tem CSRF se o formulário for usado corretamente no template.

    return render_template('checkout.html', vehicle=vehicle, form=form) #


@app.route('/process_purchase', methods=['POST']) #
def process_purchase(): #
    if 'user_id' not in session: #
        flash('Você precisa estar logado para concluir a compra.', 'warning') #
        return redirect(url_for('login')) #

    user_id = session['user_id'] #
    form = PaymentForm() # Valida os dados recebidos

    # vehicle_id é um HiddenField, então form.vehicle_id.data deve funcionar
    vehicle_id = form.vehicle_id.data
    
    if form.validate_on_submit(): #
        conn = get_db_connection() #
        try: #
            vehicle_check = conn.execute('SELECT * FROM vehicles WHERE id = ? AND status = "available"', (vehicle_id,)).fetchone() #
            if not vehicle_check: #
                flash('Veículo não disponível ou já foi vendido.', 'error') #
                conn.close() #
                return redirect(url_for('index')) #

            # Simulação de pagamento bem-sucedido
            payment_successful = True #

            if payment_successful: #
                conn.execute('INSERT INTO purchases (user_id, vehicle_id, purchase_date) VALUES (?, ?, ?)', #
                             (user_id, vehicle_id, datetime.now())) #
                conn.execute('UPDATE vehicles SET status = "sold" WHERE id = ?', (vehicle_id,)) #
                conn.execute('DELETE FROM carts WHERE user_id = ? AND vehicle_id = ?', (user_id, vehicle_id)) # # E também de outros carrinhos se necessário
                conn.execute('DELETE FROM carts WHERE vehicle_id = ?', (vehicle_id,)) # Remove de todos os carrinhos
                conn.commit() #
                flash('Compra realizada com sucesso! Parabéns pelo seu novo veículo!', 'success') #
                return redirect(url_for('user_dashboard')) #
            # else: # Pagamento falhou (não implementado neste exemplo)
            #     flash('Ocorreu um erro ao processar seu pagamento. Tente novamente.', 'error') #
            #     return redirect(url_for('checkout', vehicle_id=vehicle_id)) #

        except Exception as e: #
            if conn: conn.rollback() #
            flash(f'Erro interno ao concluir a compra: {str(e)}', 'error') #
            return redirect(url_for('checkout', vehicle_id=vehicle_id) if vehicle_id else url_for('index')) #
        finally: #
            if conn: #
                conn.close() #
    else:
        # Se a validação do formulário falhar, redireciona de volta para o checkout
        # Os erros de validação do WTForms podem ser exibidos no template checkout.html
        flash('Por favor, preencha todos os dados de pagamento corretamente.', 'error') #
        # Para recarregar a página de checkout, precisamos buscar os dados do veículo novamente.
        conn_vehicle = get_db_connection()
        vehicle_data = conn_vehicle.execute('SELECT * FROM vehicles WHERE id = ?', (vehicle_id,)).fetchone()
        vehicle_checkout = None
        if vehicle_data:
            vehicle_checkout = get_vehicle_with_primary_image(conn_vehicle, vehicle_data, is_row_dict=True)
        conn_vehicle.close()
        
        if not vehicle_checkout: # Se o veículo não for encontrado por algum motivo
            return redirect(url_for('index'))
            
        return render_template('checkout.html', vehicle=vehicle_checkout, form=form)


if __name__ == '__main__': #
    if not os.path.exists(UPLOAD_FOLDER): #
        os.makedirs(UPLOAD_FOLDER) #
    app.run(debug=True) #