from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) # Hashed password

class Santri(db.Model):
    __tablename__ = 'santri'
    id = db.Column(db.Integer, primary_key=True)
    no = db.Column(db.Integer, nullable=True)
    nama_lengkap = db.Column(db.String(150), nullable=False)
    nisn = db.Column(db.String(50), unique=True, nullable=False)  # Nomor Induk Siswa Nasional
    nik = db.Column(db.String(50), nullable=True)
    tempat_lahir = db.Column(db.String(100), nullable=True)
    tanggal_lahir = db.Column(db.Date, nullable=True)
    tingkat_rombel = db.Column(db.String(100), nullable=True)  # e.g. "Kelas 5 - CLASS 3"
    umur = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=True)  # e.g. "Aktif"
    jenis_kelamin = db.Column(db.String(20), nullable=True)  # Laki-laki / Perempuan
    alamat = db.Column(db.Text, nullable=True)
    no_telepon = db.Column(db.String(30), nullable=True)
    kebutuhan_khusus = db.Column(db.String(100), nullable=True)
    disabilitas = db.Column(db.String(100), nullable=True)
    nomor_kip_pip = db.Column(db.String(50), nullable=True)  # Nomor KIP/PIP
    nama_ayah_kandung = db.Column(db.String(150), nullable=True)
    nama_ibu_kandung = db.Column(db.String(150), nullable=True)
    nama_wali = db.Column(db.String(150), nullable=True)

class Guru(db.Model):
    __tablename__ = 'guru'
    id = db.Column(db.Integer, primary_key=True)
    nip = db.Column(db.String(50), unique=True, nullable=False)  # Nomor Induk Pegawai
    nama = db.Column(db.String(100), nullable=False)
    mata_pelajaran = db.Column(db.String(100), nullable=True)

class ImportLog(db.Model):
    __tablename__ = 'import_log'
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.DateTime, default=datetime.utcnow)
    jumlah_data = db.Column(db.Integer, default=0)
    berhasil = db.Column(db.Integer, default=0)
    gagal = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), nullable=False) # e.g. 'Success', 'Partial', 'Failed'
    target_table = db.Column(db.String(50), nullable=True) # 'santri' or 'guru'
    keterangan = db.Column(db.String(255), nullable=True) # e.g. "Kelas 7, Kelas 8"
    imported_ids = db.Column(db.Text, nullable=True) # JSON string of IDs, for rollback
    is_rolled_back = db.Column(db.Boolean, default=False)
