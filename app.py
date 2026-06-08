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

# --- Ensure Database & Default User ---
with app.app_context():
    try:
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            hashed_pw = generate_password_hash('admin123')
            admin_user = User(username='admin', password=hashed_pw)
            db.session.add(admin_user)
            db.session.commit()
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
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard_page():
    return render_template('dashboard.html')

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
        return jsonify({'success': True, 'message': 'Login successful'})
    
    return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

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

@app.route('/api/import/upload', methods=['POST'])
@login_required
def api_upload_excel():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
    
    file = request.files['file']
    target_table = request.form.get('target_table')
    
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
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    if not os.path.exists(filepath):
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
    val = clean_value(val)
    if val is None or val == '':
        return val
    
    if db_col in ('nisn', 'nip', 'nik', 'no_telepon', 'nomor_kip_pip'):
        s = str(val)
        if s.endswith('.0'):
            s = s[:-2]
        return s.strip()
    
    if db_col == 'no':
        try:
            return int(float(val))
        except:
            return val
        
    if db_col in ('nama_lengkap', 'nama', 'nama_ayah_kandung', 'nama_ibu_kandung', 'nama_wali'):
        return str(val).title()
    
    if db_col == 'tanggal_lahir' and val:
        try:
            return pd.to_datetime(val).date()
        except:
            pass
    
    if db_col in ('tempat_lahir', 'tingkat_rombel', 'umur', 'status', 'jenis_kelamin', 'alamat', 'kebutuhan_khusus', 'disabilitas', 'mata_pelajaran'):
        return str(val).strip()
        
    return val

@app.route('/api/import/validate', methods=['POST'])
@login_required
def api_validate():
    data = request.json
    file_id = data.get('file_id')
    mapping = data.get('mapping')
    target_table = data.get('target_table')
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': 'File not found'}), 404
        
    try:
        df = pd.read_excel(filepath)
        df = df.replace({np.nan: None, pd.NaT: None})
        rows = df.to_dict(orient='records')
        
        valid_rows = []
        invalid_rows = []
        
        for idx, row in enumerate(rows):
            is_valid = True
            errors = []
            mapped_data = {}
            transformed_data = {}
            
            for db_col, excel_col in mapping.items():
                val = row.get(excel_col)
                mapped_data[db_col] = val
                
                transformed_val = transform_data(db_col, val)
                transformed_data[db_col] = transformed_val
                
                if db_col == 'nisn' and not clean_value(val):
                    is_valid = False
                    errors.append('NISN (Nomor Induk Siswa Nasional) wajib diisi')
                
                if db_col == 'nip' and not clean_value(val):
                    is_valid = False
                    errors.append('NIP (Nomor Induk Pegawai) wajib diisi')
                
                if db_col == 'nama_lengkap' and not clean_value(val):
                    is_valid = False
                    errors.append('Nama Lengkap wajib diisi')
                
                if db_col == 'nama' and not clean_value(val):
                    is_valid = False
                    errors.append('Nama wajib diisi')
                
                if db_col == 'tanggal_lahir' and val:
                    try:
                        pd.to_datetime(val)
                    except:
                        is_valid = False
                        errors.append('Invalid date format')

            import_type = 'Baru'
            if is_valid:
                if target_table == 'santri' and transformed_data.get('nisn'):
                    exists = Santri.query.filter_by(nisn=transformed_data['nisn']).first()
                    if exists:
                        is_valid = False
                        errors.append(f'Santri dengan NISN {transformed_data["nisn"]} sudah ada di database')
                elif target_table == 'guru' and transformed_data.get('nip'):
                    exists = Guru.query.filter_by(nip=transformed_data['nip']).first()
                    if exists:
                        is_valid = False
                        errors.append(f'Guru dengan NIP {transformed_data["nip"]} sudah ada di database')

            if is_valid:
                valid_rows.append({
                    'original_index': idx,
                    'data': mapped_data,
                    'transformed': transformed_data,
                    'import_type': import_type
                })
            else:
                invalid_rows.append({
                    'original_index': idx,
                    'data': mapped_data,
                    'transformed': transformed_data,
                    'errors': errors
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
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': 'File not found'}), 404
        
    try:
        df = pd.read_excel(filepath)
        df = df.replace({np.nan: None, pd.NaT: None})
        
        success_count = 0
        failed_count = 0
        imported_ids = []
        imported_classes = set()
        
        for _, row in df.iterrows():
            try:
                mapped_data = {}
                for db_col, excel_col in mapping.items():
                    val = row.get(excel_col)
                    transformed_val = transform_data(db_col, val)
                    mapped_data[db_col] = transformed_val
                
                if target_table == 'santri':
                    if mapped_data.get('tingkat_rombel'):
                        imported_classes.add(str(mapped_data['tingkat_rombel']))
                    
                    nisn = mapped_data.get('nisn')
                    if not nisn or not mapped_data.get('nama_lengkap'):
                        failed_count += 1
                        continue
                    
                    exists = Santri.query.filter_by(nisn=nisn).first()
                    if exists:
                        failed_count += 1
                        continue
                    
                    new_record = Santri(**mapped_data)
                    db.session.add(new_record)
                    db.session.flush()
                    imported_ids.append(new_record.id)
                    success_count += 1
                    
                elif target_table == 'guru':
                    nip = mapped_data.get('nip')
                    if not nip or not mapped_data.get('nama'):
                        failed_count += 1
                        continue
                    
                    exists = Guru.query.filter_by(nip=nip).first()
                    if exists:
                        failed_count += 1
                        continue
                    
                    new_record = Guru(**mapped_data)
                    db.session.add(new_record)
                    db.session.flush()
                    imported_ids.append(new_record.id)
                    success_count += 1
                
            except Exception as e:
                db.session.rollback()
                failed_count += 1
                
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
            imported_ids=json.dumps(imported_ids) if imported_ids else None
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'berhasil': success_count,
            'gagal': failed_count,
            'status': status,
            'log_id': log_entry.id
        })
        
    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/logs', methods=['GET'])
@login_required
def api_logs():
    logs = ImportLog.query.order_by(ImportLog.tanggal.desc()).all()
    logs_data = [{
        'id': log.id,
        'tanggal': log.tanggal.strftime('%Y-%m-%d %H:%M:%S'),
        'jumlah_data': log.jumlah_data,
        'berhasil': log.berhasil,
        'gagal': log.gagal,
        'status': log.status,
        'target_table': log.target_table,
        'keterangan': log.keterangan,
        'is_rolled_back': log.is_rolled_back
    } for log in logs]
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
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=False)
