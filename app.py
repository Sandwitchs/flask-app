import os
import json
import uuid
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Helper untuk mendapatkan waktu WIB (UTC+7)
def get_wib_now():
    return datetime.utcnow() + timedelta(hours=7)

from config import Config
from models import db, User, Santri, Guru, ImportLog

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

ALLOWED_TARGET_TABLES = {'santri', 'guru'}


def get_upload_path(file_id):
    if not file_id or os.path.basename(file_id) != file_id:
        return None

    upload_root = os.path.abspath(app.config['UPLOAD_FOLDER'])
    filepath = os.path.abspath(os.path.join(upload_root, file_id))

    if os.path.commonpath([upload_root, filepath]) != upload_root:
        return None

    return filepath


def ensure_database():
    """Create tables, apply lightweight SQLite migrations, and seed default admin."""
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()

    migrations = [
        ("users", "email", "ALTER TABLE users ADD COLUMN email VARCHAR(100)"),
        ("import_log", "invalid_rows_data", "ALTER TABLE import_log ADD COLUMN invalid_rows_data TEXT"),
        ("import_log", "admin_id", "ALTER TABLE import_log ADD COLUMN admin_id INTEGER REFERENCES users(id)"),
        ("users", "last_active_at", "ALTER TABLE users ADD COLUMN last_active_at DATETIME"),
        ("guru", "tingkat_rombel", "ALTER TABLE guru ADD COLUMN tingkat_rombel VARCHAR(100)"),
    ]

    for table, column, statement in migrations:
        try:
            db.session.execute(db.text(statement))
            db.session.commit()
            print(f"[MIGRATION] Added {column} column to {table} table.")
        except Exception as e:
            print(f"[MIGRATION WARNING] Could not add {column} column to {table}: {e}")
            db.session.rollback()

    # Set last_active_at for all existing users
    try:
        users = User.query.all()
        for user in users:
            if not user.last_active_at:
                user.last_active_at = get_wib_now()
                db.session.commit()
        print("[MIGRATION] Set last_active_at for all existing users.")
    except Exception as e:
        print(f"[MIGRATION WARNING] Could not set last_active_at for users: {e}")
        db.session.rollback()

    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('admin123')
        admin_user = User(username='admin', password=hashed_pw, email='admindaarelhaq@gmail.com', last_active_at=get_wib_now())
        db.session.add(admin_user)
        db.session.commit()
        print("[OK] User admin default berhasil dibuat!")
    else:
        # Update email admin utama jika belum diupdate
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user.email != 'admindaarelhaq@gmail.com':
            admin_user.email = 'admindaarelhaq@gmail.com'
            db.session.commit()
            print("[OK] Email admin utama berhasil diupdate!")
        print("[INFO] User admin sudah ada!")


# --- Ensure Database & Default User ---
with app.app_context():
    try:
        ensure_database()
    except Exception as e:
        print(f'Warning: Could not initialize database. Error: {e}')


# --- Helper for Auth ---
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# --- UI Routes ---
@app.route('/')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard_page'))
    return render_template('login.html', google_client_id=app.config['GOOGLE_CLIENT_ID'])


@app.route('/dashboard')
@login_required
def dashboard_page():
    username = session.get('username', 'Admin')
    user = User.query.get(session.get('user_id'))
    last_active = ""
    if user and user.last_active_at:
        # Convert to WIB and format: DD-MM-YYYY HH:MM:SS WIB
        last_active = user.last_active_at.strftime('%d-%m-%Y %H:%M:%S WIB')
    return render_template('dashboard.html', username=username, last_active=last_active)

@app.route('/import')
@login_required
def import_page():
    return render_template('import.html')

@app.route('/preview')
@login_required
def preview_page():
    return render_template('preview.html')

@app.route('/mapping')
@login_required
def mapping_page():
    return render_template('mapping.html')

@app.route('/validation')
@login_required
def validation_page():
    return render_template('validation.html')

@app.route('/simulation')
@login_required
def simulation_page():
    return render_template('simulation.html')

@app.route('/result')
@login_required
def result_page():
    return render_template('result.html')

@app.route('/logs')
@login_required
def logs_page():
    return render_template('logs.html')

@app.route('/change-password')
@login_required
def change_password_page():
    return render_template('change_password.html')

@app.route('/santri')
@login_required
def santri_page():
    return render_template('santri.html')

@app.route('/guru')
@login_required
def guru_page():
    return render_template('guru.html')

@app.route('/manage-admins')
@login_required
def manage_admins_page():
    # Pass Google Client ID to frontend so it can load Google sign-in properly
    return render_template('manage_admins.html', google_client_id=app.config['GOOGLE_CLIENT_ID'])


# --- REST API Endpoints ---

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        session['user_id'] = user.id
        session['username'] = user.username
        user.last_active_at = get_wib_now()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Login successful'})
    
    return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

# Endpoint /api/register dihapus - penambahan admin hanya via /api/admins yang membutuhkan login


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return jsonify({'success': True})

@app.route('/api/dashboard/stats', methods=['GET'])
@login_required
def api_dashboard_stats():
    santri_count = Santri.query.count()
    guru_count = Guru.query.count()
    response = jsonify({
        'santri': santri_count,
        'guru': guru_count
    })
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def get_distinct_values(model, column):
    rows = db.session.query(column.distinct()).filter(column.isnot(None)).all()
    return sorted([row[0] for row in rows if row[0]])


def apply_santri_filters(query):
    search = request.args.get('search', '').strip()
    rombel = request.args.get('rombel', '').strip()
    jenis_kelamin = request.args.get('jenis_kelamin', '').strip()
    status = request.args.get('status', '').strip()

    if search:
        query = query.filter((Santri.nama_lengkap.ilike(f'%{search}%')) | (Santri.nisn.ilike(f'%{search}%')))
    if rombel:
        query = query.filter(Santri.tingkat_rombel == rombel)
    if jenis_kelamin:
        query = query.filter(Santri.jenis_kelamin == jenis_kelamin)
    if status:
        query = query.filter(Santri.status == status)

    return query


def apply_guru_filters(query):
    search = request.args.get('search', '').strip()
    mapel = request.args.get('mapel', '').strip()

    if search:
        query = query.filter((Guru.nama.ilike(f'%{search}%')) | (Guru.nip.ilike(f'%{search}%')))
    if mapel:
        query = query.filter(Guru.mata_pelajaran == mapel)

    return query


def santri_to_dict(s):
    return {
        'id': s.id,
        'no': s.no,
        'nama_lengkap': s.nama_lengkap,
        'nisn': s.nisn,
        'nik': s.nik,
        'tempat_lahir': s.tempat_lahir,
        'tanggal_lahir': s.tanggal_lahir.strftime('%Y-%m-%d') if s.tanggal_lahir else None,
        'tingkat_rombel': s.tingkat_rombel,
        'umur': s.umur,
        'status': s.status,
        'jenis_kelamin': s.jenis_kelamin,
        'alamat': s.alamat,
        'no_telepon': s.no_telepon,
        'kebutuhan_khusus': s.kebutuhan_khusus,
        'disabilitas': s.disabilitas,
        'nomor_kip_pip': s.nomor_kip_pip,
        'nama_ayah_kandung': s.nama_ayah_kandung,
        'nama_ibu_kandung': s.nama_ibu_kandung,
        'nama_wali': s.nama_wali
    }


def guru_to_dict(g):
    return {
        'id': g.id,
        'nip': g.nip,
        'nama': g.nama,
        'mata_pelajaran': g.mata_pelajaran,
        'tingkat_rombel': g.tingkat_rombel
    }


def get_import_log_groups(target_table):
    logs = ImportLog.query.filter_by(target_table=target_table, is_rolled_back=False).order_by(ImportLog.tanggal.desc()).all()
    id_to_log = {}
    log_order = []

    for log in logs:
        if not log.imported_ids:
            continue

        try:
            ids = json.loads(log.imported_ids)
        except Exception:
            continue

        log_info = {
            'log_id': log.id,
            'tanggal': log.tanggal.strftime('%d %B %Y, %H:%M WIB'),
            'tanggal_raw': log.tanggal.strftime('%Y-%m-%d %H:%M:%S'),
            'jumlah_data': log.jumlah_data,
            'berhasil': log.berhasil,
            'gagal': log.gagal,
            'status': log.status,
            'keterangan': log.keterangan
        }
        log_order.append((log.id, log_info))
        for item_id in ids:
            id_to_log[item_id] = log.id

    return id_to_log, log_order


def build_grouped_batches(records, serializer, target_table):
    id_to_log, log_order = get_import_log_groups(target_table)
    grouped = {}
    untracked = []

    for record in records:
        log_id = id_to_log.get(record.id)
        if log_id:
            grouped.setdefault(log_id, []).append(serializer(record))
        else:
            untracked.append(serializer(record))

    batches = []
    for log_id, log_info in log_order:
        if grouped.get(log_id):
            batches.append({
                'log': log_info,
                'data': grouped[log_id]
            })

    if untracked:
        batches.append({
            'log': {
                'log_id': None,
                'tanggal': 'Data Lama (tanpa log import)',
                'tanggal_raw': '1970-01-01 00:00:00',
                'jumlah_data': len(untracked),
                'berhasil': len(untracked),
                'gagal': 0,
                'status': 'Unknown',
                'keterangan': None
            },
            'data': untracked
        })

    return batches


@app.route('/api/santri', methods=['GET'])
@login_required
def api_santri():
    santri_list = apply_santri_filters(Santri.query).all()
    
    return jsonify({
        'success': True,
        'data': [santri_to_dict(s) for s in santri_list],
        'rombels': get_distinct_values(Santri, Santri.tingkat_rombel),
        'statuses': get_distinct_values(Santri, Santri.status),
        'genders': get_distinct_values(Santri, Santri.jenis_kelamin)
    })

@app.route('/api/guru', methods=['GET'])
@login_required
def api_guru():
    guru_list = apply_guru_filters(Guru.query).all()
    
    return jsonify({
        'success': True,
        'data': [guru_to_dict(g) for g in guru_list],
        'mapels': get_distinct_values(Guru, Guru.mata_pelajaran)
    })

@app.route('/api/santri/grouped', methods=['GET'])
@login_required
def api_santri_grouped():
    """Return santri data grouped by import batch with timestamps."""
    all_santri = apply_santri_filters(Santri.query).all()
    
    return jsonify({
        'success': True,
        'batches': build_grouped_batches(all_santri, santri_to_dict, 'santri'),
        'total': len(all_santri),
        'rombels': get_distinct_values(Santri, Santri.tingkat_rombel),
        'statuses': get_distinct_values(Santri, Santri.status),
        'genders': get_distinct_values(Santri, Santri.jenis_kelamin)
    })

@app.route('/api/guru/grouped', methods=['GET'])
@login_required
def api_guru_grouped():
    """Return guru data grouped by import batch with timestamps."""
    all_guru = apply_guru_filters(Guru.query).all()
    
    return jsonify({
        'success': True,
        'batches': build_grouped_batches(all_guru, guru_to_dict, 'guru'),
        'total': len(all_guru),
        'mapels': get_distinct_values(Guru, Guru.mata_pelajaran)
    })

@app.route('/api/admins', methods=['GET'])
@login_required
def api_get_admins():
    current_user = User.query.get(session.get('user_id'))
    is_main_admin = current_user and current_user.username == 'admin'

    users = User.query.all()
    data = []
    for u in users:
        last_active = None
        if u.last_active_at:
            last_active = u.last_active_at.strftime('%d-%m-%Y %H:%M:%S WIB')
        
        # Mask email if not main admin
        masked_email = u.email
        if not is_main_admin and u.email:
            if '@' in u.email:
                local_part, domain_part = u.email.split('@', 1)
                if len(local_part) > 2:
                    masked_email = local_part[:2] + '*' * 4 + '@' + domain_part
                else:
                    masked_email = local_part + '*' * 4 + '@' + domain_part
            else:
                masked_email = u.email[:2] + '*' * (len(u.email) - 2) if len(u.email) > 2 else u.email
        
        data.append({
            'id': u.id,
            'username': u.username,
            'email': u.email if is_main_admin else masked_email,
            'last_active': last_active
        })
    
    return jsonify({'success': True, 'data': data, 'is_main_admin': is_main_admin})

@app.route('/api/admins', methods=['POST'])
@login_required
def api_add_admin():
    # Only allow main admin (username 'admin') to add admins
    current_user = User.query.get(session.get('user_id'))
    if not current_user or current_user.username != 'admin':
        return jsonify({'success': False, 'message': 'Hanya admin utama yang dapat menambah admin'}), 403
        
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username dan password wajib diisi'}), 400
        
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': f'Admin dengan username "{username}" sudah terdaftar'}), 400
        
    if email and User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': f'Admin dengan email "{email}" sudah terdaftar'}), 400
        
    hashed_pw = generate_password_hash(password)
    new_admin = User(username=username, password=hashed_pw, email=email or None, last_active_at=get_wib_now())
    db.session.add(new_admin)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Admin berhasil ditambahkan'})

@app.route('/api/admins/<int:admin_id>', methods=['DELETE'])
@login_required
def api_delete_admin(admin_id):
    # Only allow main admin (username 'admin') to delete admins
    current_user = User.query.get(session.get('user_id'))
    if not current_user or current_user.username != 'admin':
        return jsonify({'success': False, 'message': 'Hanya admin utama yang dapat menghapus admin'}), 403
        
    current_user_id = session.get('user_id')
    if current_user_id == admin_id:
        return jsonify({'success': False, 'message': 'Anda tidak dapat menghapus akun Anda sendiri'}), 400
        
    admin = User.query.get_or_404(admin_id)
    # Don't allow deleting the default 'admin' account to prevent lockouts
    if admin.username == 'admin':
        return jsonify({'success': False, 'message': 'Akun admin utama tidak dapat dihapus'}), 400
        
    db.session.delete(admin)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Admin berhasil dihapus'})

@app.route('/api/admins/<int:admin_id>/reset-password', methods=['POST'])
@login_required
def api_reset_admin_password(admin_id):
    current_user = User.query.get(session.get('user_id'))
    if not current_user:
        return jsonify({'success': False, 'message': 'Anda harus login terlebih dahulu'}), 401
    
    is_main_admin = current_user.username == 'admin'
    is_self = current_user.id == admin_id
    
    # Check permissions: only main admin can reset others, or self-reset
    if not is_main_admin and not is_self:
        return jsonify({'success': False, 'message': 'Anda tidak memiliki izin untuk mereset password akun ini'}), 403
    
    data = request.json
    password = data.get('password', '').strip()
    
    if not password or len(password) < 6:
        return jsonify({'success': False, 'message': 'Password harus memiliki minimal 6 karakter'}), 400
    
    admin = User.query.get_or_404(admin_id)
    admin.password = generate_password_hash(password)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Password berhasil direset'})

@app.route('/api/login-google', methods=['POST'])
def api_login_google():
    data = request.json
    token = data.get('credential')
    
    if not token:
        return jsonify({'success': False, 'message': 'Token credential Google tidak ditemukan'}), 400
        
    import urllib.request
    import json
    
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
        with urllib.request.urlopen(url) as response:
            token_info = json.loads(response.read().decode('utf-8'))
            
            if 'error' in token_info:
                return jsonify({'success': False, 'message': 'Verifikasi token Google gagal'}), 401
                
            email = token_info.get('email')
            if not email:
                return jsonify({'success': False, 'message': 'Email tidak ditemukan dari akun Google'}), 400
                
            # Cari user dengan email ini
            user = User.query.filter_by(email=email).first()
            if not user:
                return jsonify({
                    'success': False, 
                    'message': f'Email Google ({email}) tidak terdaftar sebagai admin. Silakan daftarkan email ini terlebih dahulu di menu Kelola Admin.'
                }), 401
                
            # Loginkan user
            session['user_id'] = user.id
            session['username'] = user.username
            user.last_active_at = get_wib_now()
            db.session.commit()
            return jsonify({'success': True, 'message': 'Login Google berhasil'})
            
    except Exception as e:
        import traceback
        print("Error verifying google token:", e)
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': f'Terjadi kesalahan verifikasi token: {str(e)}'}), 500


@app.route('/api/import/upload', methods=['POST'])
@login_required
def api_upload_excel():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
    
    file = request.files['file']
    target_table = request.form.get('target_table')

    if target_table not in ALLOWED_TARGET_TABLES:
        return jsonify({'success': False, 'message': 'Tabel tujuan tidak valid'}), 400
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400
    
    if file and (file.filename.endswith('.xls') or file.filename.endswith('.xlsx')):
        filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())
        safe_filename = f'{unique_id}_{filename}'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(filepath)
        
        try:
            df = pd.read_excel(filepath, nrows=0)
            headers = df.columns.tolist()
            return jsonify({
                'success': True,
                'file_id': safe_filename,
                'headers': headers,
                'target_table': target_table
            })
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error reading Excel: {str(e)}'}), 500
            
    return jsonify({'success': False, 'message': 'Invalid file format. Use .xls or .xlsx'}), 400

@app.route('/api/import/preview/<file_id>', methods=['GET'])
@login_required
def api_preview(file_id):
    filepath = get_upload_path(file_id)
    if not filepath or not os.path.exists(filepath):
        return jsonify({'success': False, 'message': 'File not found'}), 404
        
    try:
        df = pd.read_excel(filepath)
        df = df.replace({np.nan: None, pd.NaT: None})
        data = df.to_dict(orient='records')
        for row in data:
            for k, v in row.items():
                if isinstance(v, float) and math.isnan(v):
                    row[k] = None
        headers = df.columns.tolist()
        return jsonify({'success': True, 'headers': headers, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def clean_value(val):
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if pd.isna(val):
        return None
    return val

def transform_data(db_col, val):
    # SANGAT SEDERHANA: langsung bersihkan, tanpa transformasi rumit!
    if pd.isna(val) or val == '':
        return None
    
    # Tanggal
    if db_col == 'tanggal_lahir':
        try:
            return pd.to_datetime(val).date()
        except:
            return None
    
    # NISN/NIP/NIK hapus .0
    if db_col in ('nisn', 'nip', 'nik', 'no_telepon', 'nomor_kip_pip'):
        s = str(val)
        if s.endswith('.0'):
            s = s[:-2]
        return s.strip()
    
    # Lainnya: ubah ke string, strip
    s = str(val)
    return s.strip()


def validate_import_row(row, mapping, target_table):
    mapped_data = {}
    transformed_data = {}
    errors = []
    categorized_errors = []

    for db_col, excel_col in mapping.items():
        val = row.get(excel_col)
        mapped_data[db_col] = val
        transformed_data[db_col] = transform_data(db_col, val)

        if db_col == 'nisn' and not clean_value(val):
            errors.append('NISN (Nomor Induk Siswa Nasional) wajib diisi')
            categorized_errors.append({'msg': 'NISN wajib diisi', 'category': 'Data Kosong'})

        if db_col == 'nip' and not clean_value(val):
            errors.append('NIP (Nomor Induk Pegawai) wajib diisi')
            categorized_errors.append({'msg': 'NIP wajib diisi', 'category': 'Data Kosong'})

        if db_col == 'nama_lengkap' and not clean_value(val):
            errors.append('Nama Lengkap wajib diisi')
            categorized_errors.append({'msg': 'Nama Lengkap wajib diisi', 'category': 'Data Kosong'})

        if db_col == 'nama' and not clean_value(val):
            errors.append('Nama wajib diisi')
            categorized_errors.append({'msg': 'Nama wajib diisi', 'category': 'Data Kosong'})

        if db_col == 'tanggal_lahir' and val:
            try:
                pd.to_datetime(val)
            except Exception:
                errors.append('Invalid date format')
                categorized_errors.append({'msg': 'Format Tanggal Lahir salah', 'category': 'Format Salah'})

    if not errors:
        if target_table == 'santri' and transformed_data.get('nisn'):
            exists = Santri.query.filter_by(nisn=transformed_data['nisn']).first()
            if exists:
                msg = f'Santri dengan NISN {transformed_data["nisn"]} sudah ada di database'
                errors.append(msg)
                categorized_errors.append({'msg': msg, 'category': 'Duplikat'})
        elif target_table == 'guru' and transformed_data.get('nip'):
            exists = Guru.query.filter_by(nip=transformed_data['nip']).first()
            if exists:
                msg = f'Guru dengan NIP {transformed_data["nip"]} sudah ada di database'
                errors.append(msg)
                categorized_errors.append({'msg': msg, 'category': 'Duplikat'})

    return {
        'is_valid': not errors,
        'mapped_data': mapped_data,
        'transformed_data': transformed_data,
        'errors': errors,
        'categorized_errors': categorized_errors
    }


@app.route('/api/import/validate', methods=['POST'])
@login_required
def api_validate():
    data = request.json
    file_id = data.get('file_id')
    mapping = data.get('mapping')
    target_table = data.get('target_table')

    if target_table not in ALLOWED_TARGET_TABLES:
        return jsonify({'success': False, 'message': 'Tabel tujuan tidak valid'}), 400

    if not isinstance(mapping, dict) or not mapping:
        return jsonify({'success': False, 'message': 'Mapping kolom tidak valid'}), 400
    
    filepath = get_upload_path(file_id)
    if not filepath or not os.path.exists(filepath):
        return jsonify({'success': False, 'message': 'File not found'}), 404
        
    try:
        df = pd.read_excel(filepath)
        df = df.replace({np.nan: None, pd.NaT: None})
        rows = df.to_dict(orient='records')
        
        valid_rows = []
        invalid_rows = []
        
        for idx, row in enumerate(rows):
            import_type = 'Baru'
            row_validation = validate_import_row(row, mapping, target_table)

            if row_validation['is_valid']:
                valid_rows.append({
                    'original_index': idx,
                    'data': row_validation['mapped_data'],
                    'transformed': row_validation['transformed_data'],
                    'import_type': import_type
                })
            else:
                invalid_rows.append({
                    'original_index': idx,
                    'data': row_validation['mapped_data'],
                    'transformed': row_validation['transformed_data'],
                    'errors': row_validation['errors']
                })
                
        return jsonify({
            'success': True,
            'total': len(rows),
            'valid_count': len(valid_rows),
            'invalid_count': len(invalid_rows),
            'valid_rows': valid_rows,
            'invalid_rows': invalid_rows
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/import/execute', methods=['POST'])
@login_required
def api_execute():
    data = request.json
    file_id = data.get('file_id')
    mapping = data.get('mapping')
    target_table = data.get('target_table')

    if target_table not in ALLOWED_TARGET_TABLES:
        return jsonify({'success': False, 'message': 'Tabel tujuan tidak valid'}), 400

    if not isinstance(mapping, dict) or not mapping:
        return jsonify({'success': False, 'message': 'Mapping kolom tidak valid'}), 400
    
    filepath = get_upload_path(file_id)
    if not filepath or not os.path.exists(filepath):
        return jsonify({'success': False, 'message': 'File not found'}), 404
        
    try:
        df = pd.read_excel(filepath)
        df = df.replace({np.nan: None, pd.NaT: None})
        
        success_count = 0
        failed_count = 0
        imported_ids = []
        imported_classes = set()
        invalid_rows_list = []
        
        print('[IMPORT] Mulai import data...')
        print('[IMPORT] Mapping:', mapping)
        
        for idx, row in df.iterrows():
            try:
                row_validation = validate_import_row(row, mapping, target_table)
                mapped_data = row_validation['transformed_data']
                row_errors = row_validation['categorized_errors']

                if not row_validation['is_valid']:
                    failed_count += 1
                    key_val = mapped_data.get('nisn') or mapped_data.get('nip') or '-'
                    name_val = mapped_data.get('nama_lengkap') or mapped_data.get('nama') or '-'
                    error_msgs = [e['msg'] for e in row_errors]
                    categories = list(set([e['category'] for e in row_errors]))
                    
                    invalid_rows_list.append({
                        'row': idx + 2, # Index baris di Excel (biasanya baris ke-1 header, data mulai baris 2)
                        'name': str(name_val),
                        'key': str(key_val),
                        'error': ', '.join(error_msgs),
                        'category': ', '.join(categories)
                    })
                    print(f'[SKIPPED] Baris {idx+2} tidak valid: {", ".join(error_msgs)}')
                    continue
                
                # Simpan data jika valid
                if target_table == 'santri':
                    new_record = Santri(**mapped_data)
                    db.session.add(new_record)
                    db.session.commit()
                    imported_ids.append(new_record.id)
                    success_count += 1
                    print(f'[OK] Baris {idx+2} berhasil disimpan! ID: {new_record.id}')
                    
                    if mapped_data.get('tingkat_rombel'):
                        imported_classes.add(str(mapped_data['tingkat_rombel']))
                
                elif target_table == 'guru':
                    new_record = Guru(**mapped_data)
                    db.session.add(new_record)
                    db.session.commit()
                    imported_ids.append(new_record.id)
                    success_count += 1
                    print(f'[OK] Baris {idx+2} berhasil disimpan! ID: {new_record.id}')
                    
                    if mapped_data.get('tingkat_rombel'):
                        imported_classes.add(str(mapped_data['tingkat_rombel']))
                    
            except Exception as e:
                import traceback
                error_str = str(e)
                print(f'[ERROR EXCEPTION] Baris {idx+2}: {error_str}')
                print(traceback.format_exc())
                db.session.rollback()
                failed_count += 1
                
                key_val = row.get(mapping.get('nisn') or mapping.get('nip') or '') or '-'
                name_val = row.get(mapping.get('nama_lengkap') or mapping.get('nama') or '') or '-'
                
                # Deteksi jenis error untuk pesan yang lebih ramah
                if 'UNIQUE constraint failed' in error_str or 'IntegrityError' in error_str or 'Duplicate entry' in error_str:
                    error_category = 'Duplikat'
                    error_msg = f'Data dengan NISN/NIP "{key_val}" sudah ada di database. Kemungkinan data sudah pernah diimport sebelumnya.'
                elif 'NOT NULL constraint' in error_str:
                    error_category = 'Data Kosong'
                    error_msg = f'Ada kolom wajib yang kosong pada baris ini.'
                else:
                    error_category = 'Lainnya'
                    error_msg = f'Error: {error_str[:150]}'
                
                invalid_rows_list.append({
                    'row': idx + 2,
                    'name': str(name_val),
                    'key': str(key_val),
                    'error': error_msg,
                    'category': error_category
                })
                
        status = 'Success' if failed_count == 0 else ('Partial' if success_count > 0 else 'Failed')
        
        keterangan = None
        if target_table == 'santri' and imported_classes:
            keterangan = ', '.join(sorted(list(imported_classes)))
            
        log_entry = ImportLog(
            tanggal=get_wib_now(),
            jumlah_data=success_count + failed_count,
            berhasil=success_count,
            gagal=failed_count,
            status=status,
            target_table=target_table,
            keterangan=keterangan,
            imported_ids=json.dumps(imported_ids) if imported_ids else None,
            invalid_rows_data=json.dumps(invalid_rows_list) if invalid_rows_list else None,
            admin_id=session.get('user_id')
        )
        db.session.add(log_entry)
        db.session.commit()
        
        print(f'[IMPORT SELESAI] Sukses: {success_count}, Gagal: {failed_count}')
        
        return jsonify({
            'success': True,
            'berhasil': success_count,
            'gagal': failed_count,
            'status': status,
            'log_id': log_entry.id
        })
        
    except Exception as e:
        import traceback
        print('ERROR BESAR DI API_EXECUTE:', str(e))
        print(traceback.format_exc())
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/logs', methods=['GET'])
@login_required
def api_logs():
    limit = request.args.get('limit', type=int)
    query = ImportLog.query.order_by(ImportLog.tanggal.desc())
    if limit:
        logs = query.limit(limit).all()
    else:
        logs = query.all()
        
    logs_data = []
    for log in logs:
        admin_name = None
        if log.admin:
            admin_name = log.admin.username
            
        logs_data.append({
            'id': log.id,
            'tanggal': log.tanggal.strftime('%Y-%m-%d %H:%M:%S'),
            'jumlah_data': log.jumlah_data,
            'berhasil': log.berhasil,
            'gagal': log.gagal,
            'status': log.status.lower(),
            'table_target': log.target_table,
            'keterangan': log.keterangan,
            'is_rolled_back': log.is_rolled_back,
            'invalid_rows_data': json.loads(log.invalid_rows_data) if log.invalid_rows_data else [],
            'admin_name': admin_name,
            'created_at': log.tanggal.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    # If it's a request with limit (for dashboard recent activity), return just the array
    if limit:
        return jsonify(logs_data)
    else:
        return jsonify({'success': True, 'data': logs_data})


@app.route('/api/logs/rollback/<int:log_id>', methods=['POST'])
@login_required
def api_rollback_log(log_id):
    log = ImportLog.query.get_or_404(log_id)
    
    if log.is_rolled_back:
        return jsonify({'success': False, 'message': 'Log sudah dirollback'}), 400
    
    if not log.imported_ids or not log.target_table:
        return jsonify({'success': False, 'message': 'Tidak ada data untuk dirollback'}), 400
    
    try:
        imported_ids = json.loads(log.imported_ids)
        
        if log.target_table == 'santri':
            Santri.query.filter(Santri.id.in_(imported_ids)).delete(synchronize_session=False)
        elif log.target_table == 'guru':
            Guru.query.filter(Guru.id.in_(imported_ids)).delete(synchronize_session=False)
        else:
            return jsonify({'success': False, 'message': 'Tabel target tidak valid'}), 400
            
        log.is_rolled_back = True
        log.status = 'Rolled Back'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Rollback berhasil'})
        
    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/change-password', methods=['POST'])
@login_required
def api_change_password():
    data = request.json
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    
    if not old_password or not new_password or not confirm_password:
        return jsonify({'success': False, 'message': 'Semua kolom harus diisi'}), 400
    
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'Password baru dan konfirmasi tidak cocok'}), 400
    
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': 'Password baru minimal 8 karakter'}), 400
    
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not check_password_hash(user.password, old_password):
        return jsonify({'success': False, 'message': 'Password lama salah'}), 400
    
    user.password = generate_password_hash(new_password)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Password berhasil diubah! Silakan login kembali.'})

if __name__ == '__main__':
    app.run(debug=False)
