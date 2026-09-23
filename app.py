import sqlite3
import os
import csv
import io
import unicodedata 
import re          
from flask import Flask, render_template, request, jsonify, redirect, url_for, g, flash, make_response, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
from datetime import datetime

# --- CONFIGURAÇÃO DO APP ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chave_padrao_desenvolvimento') 

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'school_system_final.db')

# --- FUNÇÕES UTILITÁRIAS ---
def gerar_username_pai(nome_aluno):
    nome_aluno = nome_aluno.strip()
    nome_limpo = ''.join(c for c in unicodedata.normalize('NFD', nome_aluno)
                         if unicodedata.category(c) != 'Mn')
    nome_limpo = nome_limpo.lower()
    nome_limpo = re.sub(r'[^a-z0-9\s]', '', nome_limpo)
    
    partes = nome_limpo.split()
    
    if len(partes) >= 2:
        base_username = f"pais.{partes[0]}.{partes[-1]}"
    else:
        base_username = f"pais.{partes[0]}"
        
    return base_username

# --- FUNÇÕES DE BANCO DE DADOS ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db_if_not_exists():
    if not os.path.exists(DATABASE):
        print("⚠️ BANCO NÃO ENCONTRADO. CRIANDO ESTRUTURA ZERADA...")
        with app.app_context():
            db = get_db()
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'parent')),
                    full_name TEXT
                );
                
                CREATE TABLE IF NOT EXISTS classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    schedule TEXT,
                    teacher_id INTEGER,
                    FOREIGN KEY (teacher_id) REFERENCES users (id)
                );

                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    class_id INTEGER NOT NULL,
                    parent_id INTEGER NOT NULL,
                    FOREIGN KEY (class_id) REFERENCES classes (id),
                    FOREIGN KEY (parent_id) REFERENCES users (id)
                );
                
                CREATE TABLE IF NOT EXISTS class_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_id INTEGER NOT NULL,
                    record_date TEXT NOT NULL,
                    topic TEXT,
                    UNIQUE(class_id, record_date)
                );
                
                CREATE TABLE IF NOT EXISTS class_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    class_id INTEGER NOT NULL,
                    teacher_id INTEGER NOT NULL,
                    record_date TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('presente', 'ausente')),
                    grade INTEGER DEFAULT 0,
                    comments TEXT,
                    homework TEXT DEFAULT 'Sim',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students (id),
                    FOREIGN KEY (class_id) REFERENCES classes (id),
                    FOREIGN KEY (teacher_id) REFERENCES users (id)
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    teacher_id INTEGER,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(student_id) REFERENCES students(id)
                );
            """)

            cur = db.cursor()
            pwd_admin = generate_password_hash('senha_admin_123')
            cur.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)", 
                        ('admin', pwd_admin, 'admin', 'Administrador Geral'))
            
            db.commit()
            print("✅ SISTEMA PRONTO: Banco de dados criado apenas com Usuário Admin.")

# --- SISTEMA DE LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_page"

class User(UserMixin):
    def __init__(self, id, username, role, full_name):
        self.id = id
        self.username = username
        self.role = role
        self.full_name = full_name

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if u: return User(u['id'], u['username'], u['role'], u['full_name'])
    return None

# --- ROTAS PRINCIPAIS ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin': return redirect(url_for('admin_dashboard'))
        if current_user.role == 'teacher': return redirect(url_for('teacher_dashboard'))
        return redirect(url_for('parent_dashboard'))
    return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            login_user(User(user['id'], user['username'], user['role'], user['full_name']))
            if user['role'] == 'admin': return redirect(url_for('admin_dashboard'))
            if user['role'] == 'teacher': return redirect(url_for('teacher_dashboard'))
            return redirect(url_for('parent_dashboard'))
        flash('Login inválido', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login_page'))

# --- ÁREA DO ADMIN ---
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin': return "403", 403
    db = get_db()
    classes = db.execute('SELECT c.*, u.full_name as teacher_name, (SELECT COUNT(*) FROM students s WHERE s.class_id = c.id) as student_count FROM classes c LEFT JOIN users u ON c.teacher_id = u.id').fetchall()
    teachers = db.execute("SELECT * FROM users WHERE role = 'teacher'").fetchall()
    return render_template('admin_dashboard.html', classes=classes, teachers=teachers)

@app.route('/admin/add_class', methods=['POST'])
@login_required
def admin_add_class():
    if current_user.role != 'admin': return "403", 403
    db = get_db()
    
    cur = db.cursor()
    cur.execute("INSERT INTO classes (name, schedule, teacher_id) VALUES (?, ?, ?)", 
                (request.form.get('name'), request.form.get('schedule'), request.form.get('teacher_id')))
    class_id = cur.lastrowid
    
    students_text = request.form.get('students_list')
    if students_text:
        pwd = generate_password_hash('senha_padrao_pais')
        names = students_text.split('\n')
        skipped = [] 
        count_add = 0
        
        cur.execute("DELETE FROM users WHERE role='parent' AND NOT EXISTS (SELECT 1 FROM students WHERE students.parent_id = users.id)")
        db.commit()
        
        for name in names:
            name = name.strip()
            if name:
                aluno_existe = cur.execute("SELECT 1 FROM students WHERE LOWER(name) = LOWER(?) AND class_id = ?", (name, class_id)).fetchone()
                
                if aluno_existe:
                    skipped.append(name)
                    continue 
                
                user_pai = gerar_username_pai(name)

                base_user_pai = user_pai
                contador = 2
                while cur.execute("SELECT 1 FROM users WHERE username=?", (user_pai,)).fetchone():
                    user_pai = f"{base_user_pai}{contador}"
                    contador += 1
                
                cur.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
                            (user_pai, pwd, 'parent', f"Resp. {name}"))
                pai_id = cur.lastrowid
                cur.execute("INSERT INTO students (name, class_id, parent_id) VALUES (?, ?, ?)",
                            (name, class_id, pai_id))
                count_add += 1
    
    db.commit()
    
    if students_text and count_add > 0:
        flash(f'Turma criada e {count_add} aluno(s) matriculado(s) com sucesso!', 'success')
    elif students_text and count_add == 0 and not skipped:
        flash('Turma criada, mas nenhum nome válido foi encontrado para matrícula.', 'warning')
        
    if 'skipped' in locals() and skipped:
        flash(f'Atenção: Os seguintes alunos já estavam nesta turma e as duplicatas foram ignoradas: {", ".join(skipped)}', 'warning')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_teacher', methods=['POST'])
@login_required
def admin_add_teacher():
    if current_user.role != 'admin': return "403", 403
    db = get_db()
    db.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)", (request.form.get('username'), generate_password_hash(request.form.get('password')), 'teacher', request.form.get('name')))
    db.commit()
    flash('Professor cadastrado com sucesso!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_class/<int:class_id>')
@login_required
def admin_delete_class(class_id):
    if current_user.role != 'admin': return "403", 403
    db = get_db()
    
    db.execute("DELETE FROM notifications WHERE student_id IN (SELECT id FROM students WHERE class_id = ?)", (class_id,))
    db.execute("DELETE FROM class_records WHERE class_id = ?", (class_id,))
    db.execute("DELETE FROM class_sessions WHERE class_id = ?", (class_id,))
    
    db.execute("DELETE FROM users WHERE role='parent' AND id IN (SELECT parent_id FROM students WHERE class_id = ?)", (class_id,))
    db.execute("DELETE FROM students WHERE class_id = ?", (class_id,))
    db.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    
    db.commit()
    flash('Turma excluída com sucesso.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_teacher/<int:user_id>')
@login_required
def admin_delete_teacher(user_id):
    if current_user.role != 'admin': return "403", 403
    db = get_db()
    db.execute("UPDATE classes SET teacher_id = NULL WHERE teacher_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ? AND role = 'teacher'", (user_id,))
    db.commit()
    flash('Professor excluído.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/class/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_class_page(class_id):
    if current_user.role != 'admin': return "403", 403
    db = get_db()
    
    if request.method == 'POST':
        name = request.form.get('name')
        schedule = request.form.get('schedule')
        teacher_id = request.form.get('teacher_id')
        db.execute("UPDATE classes SET name=?, schedule=?, teacher_id=? WHERE id=?", 
                   (name, schedule, teacher_id, class_id))
        db.commit()
        flash('Turma atualizada com sucesso!', 'success')
        return redirect(url_for('admin_edit_class_page', class_id=class_id))

    cls = db.execute('SELECT * FROM classes WHERE id = ?', (class_id,)).fetchone()
    if not cls: return "Turma não encontrada", 404
    
    students = db.execute('''
        SELECT students.*, users.username AS parent_login 
        FROM students 
        LEFT JOIN users ON students.parent_id = users.id 
        WHERE students.class_id = ?
        ORDER BY students.name ASC
    ''', (class_id,)).fetchall()
    
    teachers = db.execute("SELECT * FROM users WHERE role = 'teacher'").fetchall()
    
    return render_template('edit_class.html', cls=cls, students=students, teachers=teachers)

@app.route('/admin/class/<int:class_id>/add_students', methods=['POST'])
@login_required
def admin_add_students_to_class(class_id):
    if current_user.role != 'admin': return "403", 403
    db = get_db()
    
    students_text = request.form.get('new_students')
    if students_text:
        pwd = generate_password_hash('senha_padrao_pais')
        names = students_text.split('\n')
        cur = db.cursor()
        count_add = 0
        skipped = [] 
        
        cur.execute("DELETE FROM users WHERE role='parent' AND NOT EXISTS (SELECT 1 FROM students WHERE students.parent_id = users.id)")
        db.commit() 
        
        for name in names:
            name = name.strip()
            if name:
                aluno_existe = cur.execute("SELECT 1 FROM students WHERE LOWER(name) = LOWER(?) AND class_id = ?", (name, class_id)).fetchone()
                
                if aluno_existe:
                    skipped.append(name)
                    continue 

                user_pai = gerar_username_pai(name)

                base_user_pai = user_pai
                contador = 2
                while cur.execute("SELECT 1 FROM users WHERE username=?", (user_pai,)).fetchone():
                    user_pai = f"{base_user_pai}{contador}"
                    contador += 1
                
                cur.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
                            (user_pai, pwd, 'parent', f"Resp. {name}"))
                pai_id = cur.lastrowid
                cur.execute("INSERT INTO students (name, class_id, parent_id) VALUES (?, ?, ?)",
                            (name, class_id, pai_id))
                count_add += 1
        
        db.commit()
        
        if count_add > 0:
            flash(f'{count_add} aluno(s) adicionado(s) com sucesso!', 'success')
        elif not skipped:
            flash('Nenhum nome válido encontrado.', 'warning')
            
        if skipped:
            flash(f'Atenção: Os seguintes alunos já existem nesta turma e foram ignorados: {", ".join(skipped)}', 'warning')
            
    return redirect(url_for('admin_edit_class_page', class_id=class_id))

@app.route('/admin/student/<int:student_id>/delete', methods=['POST'])
@login_required
def admin_delete_student(student_id):
    if current_user.role != 'admin': return "403", 403
    db = get_db()
    
    std = db.execute('SELECT class_id, parent_id FROM students WHERE id = ?', (student_id,)).fetchone()
    class_id = std['class_id'] if std else None
    parent_id = std['parent_id'] if std else None
    
    db.execute("DELETE FROM class_records WHERE student_id = ?", (student_id,))
    db.execute("DELETE FROM notifications WHERE student_id = ?", (student_id,))
    db.execute("DELETE FROM students WHERE id = ?", (student_id,))
    
    if parent_id:
        db.execute("DELETE FROM users WHERE id = ?", (parent_id,))
        
    db.commit()
    
    flash('Aluno removido.', 'success')
    if class_id:
        return redirect(url_for('admin_edit_class_page', class_id=class_id))
    return redirect(url_for('admin_dashboard'))

# --- ÁREA DO PROFESSOR E RESTANTE ---
@app.route('/teacher')
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher': return "403", 403
    db = get_db()
    my_classes = db.execute('SELECT * FROM classes WHERE teacher_id = ?', (current_user.id,)).fetchall()
    return render_template('teacher_dashboard.html', classes=my_classes)

@app.route('/teacher/class/<int:class_id>')
@login_required
def teacher_class_view(class_id):
    if current_user.role != 'teacher': return "403", 403
    db = get_db()
    cls = db.execute('SELECT * FROM classes WHERE id = ? AND teacher_id = ?', (class_id, current_user.id)).fetchone()
    if not cls: return "Erro", 403
    return render_template('class_manage.html', cls=cls)

@app.route('/api/class/<int:class_id>/students')
@login_required
def api_class_students(class_id):
    db = get_db()
    students = db.execute('SELECT id, name FROM students WHERE class_id = ? ORDER BY name ASC', (class_id,)).fetchall()
    return jsonify([dict(s) for s in students])

@app.route('/api/class/<int:class_id>/history')
@login_required
def api_class_history(class_id):
    db = get_db()
    rows = db.execute('''
        SELECT r.*, s.name as student_name 
        FROM class_records r 
        JOIN students s ON r.student_id = s.id 
        WHERE r.class_id = ? 
        ORDER BY r.record_date DESC, s.name ASC
    ''', (class_id,)).fetchall()
    
    sessions = db.execute('SELECT record_date, topic FROM class_sessions WHERE class_id = ?', (class_id,)).fetchall()
    session_map = {s['record_date']: s['topic'] for s in sessions}

    grouped = defaultdict(dict)
    for r in rows:
        date = r['record_date']
        if 'records' not in grouped[date]: 
            grouped[date]['records'] = []
            grouped[date]['topic'] = session_map.get(date, "Sem tema registrado")
        
        grouped[date]['records'].append(dict(r))
        
    return jsonify(grouped)

@app.route('/api/save_records', methods=['POST'])
@login_required
def api_save_records():
    data = request.json
    db = get_db()
    
    db.execute("INSERT OR REPLACE INTO class_sessions (class_id, record_date, topic) VALUES (?, ?, ?)",
               (data['class_id'], data['date'], data['topic']))

    for rec in data['records']:
        db.execute('''
            INSERT INTO class_records (student_id, class_id, teacher_id, record_date, status, grade, comments, homework)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (rec['student_id'], data['class_id'], current_user.id, data['date'], rec['status'], rec.get('grade',0), rec.get('comments',''), rec.get('homework', 'Sim')))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/delete_day', methods=['POST'])
@login_required
def api_delete_day():
    if current_user.role != 'teacher': return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    db = get_db()
    db.execute('DELETE FROM class_records WHERE class_id = ? AND record_date = ? AND teacher_id = ?', 
               (data['class_id'], data['date'], current_user.id))
    db.execute('DELETE FROM class_sessions WHERE class_id = ? AND record_date = ?', (data['class_id'], data['date']))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/records/<int:id>', methods=['DELETE'])
@login_required
def delete_record(id):
    if current_user.role != 'teacher': return jsonify({'error': 'Unauthorized'}), 403
    db = get_db()
    db.execute('DELETE FROM class_records WHERE id = ? AND teacher_id = ?', (id, current_user.id))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/send_notification', methods=['POST'])
@login_required
def api_send_notification():
    if current_user.role != 'teacher': return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    db = get_db()
    recipients = data.get('recipients', [])
    message = data.get('message')
    if not message or not recipients: return jsonify({'error': 'Dados incompletos'}), 400
    for student_id in recipients:
        db.execute("INSERT INTO notifications (student_id, teacher_id, message) VALUES (?, ?, ?)", (student_id, current_user.id, message))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/notification/<int:id>', methods=['DELETE'])
@login_required
def delete_notification(id):
    if current_user.role != 'parent': return jsonify({'error': 'Unauthorized'}), 403
    db = get_db()
    check = db.execute('''
        SELECT n.id FROM notifications n
        JOIN students s ON n.student_id = s.id
        WHERE n.id = ? AND s.parent_id = ?
    ''', (id, current_user.id)).fetchone()
    
    if check:
        db.execute('DELETE FROM notifications WHERE id = ?', (id,))
        db.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Erro ao apagar'}), 400

@app.route('/parent')
@login_required
def parent_dashboard():
    if current_user.role != 'parent': return "Acesso negado", 403
    return render_template('parent_dashboard.html')

@app.route('/api/my-records')
@login_required
def api_my_records():
    db = get_db()
    student = db.execute('SELECT s.*, c.name as class_name, u.full_name as teacher_name FROM students s JOIN classes c ON s.class_id = c.id JOIN users u ON c.teacher_id = u.id WHERE s.parent_id = ?', (current_user.id,)).fetchone()
    
    if not student: 
        return jsonify({'error': 'Nenhum aluno vinculado a esta conta. Por favor, contate a secretaria para recadastrar o acesso.'}), 404
    
    records = db.execute('SELECT * FROM class_records WHERE student_id = ? ORDER BY record_date DESC', (student['id'],)).fetchall()
    sessions = db.execute('SELECT record_date, topic FROM class_sessions WHERE class_id = ?', (student['class_id'],)).fetchall()
    session_map = {s['record_date']: s['topic'] for s in sessions}
    final_records = []
    for r in records:
        d = dict(r)
        d['topic'] = session_map.get(r['record_date'], "")
        final_records.append(d)

    notifications = db.execute('SELECT id, message, created_at FROM notifications WHERE student_id = ? ORDER BY created_at DESC LIMIT 5', (student['id'],)).fetchall()

    total = len(records)
    presents = len([r for r in records if r['status'] == 'presente'])
    freq = round((presents/total*100), 1) if total > 0 else 0
    avg = round(sum(r['grade'] for r in records if r['status'] == 'presente')/presents, 1) if presents > 0 else 0
    
    return jsonify({
        'student_name': student['name'],
        'class_name': student['class_name'],
        'teacher_name': student['teacher_name'],
        'records': final_records,
        'notifications': [dict(n) for n in notifications],
        'stats': {'frequency': freq, 'average': avg, 'absences': total - presents}
    })

@app.route('/export_csv')
@login_required
def export_csv():
    if current_user.role != 'teacher': return "Acesso negado", 403
    db = get_db()
    my_classes = db.execute('SELECT id FROM classes WHERE teacher_id = ?', (current_user.id,)).fetchall()
    class_ids = [str(c['id']) for c in my_classes]
    
    if not class_ids: return "Sem dados", 404
    
    placeholders = ','.join(['?']*len(class_ids))
    query = f'''
        SELECT r.record_date, c.name as turma, s.name as aluno, r.status, r.grade, r.homework, r.comments
        FROM class_records r 
        JOIN students s ON r.student_id = s.id
        JOIN classes c ON r.class_id = c.id
        WHERE r.class_id IN ({placeholders})
        ORDER BY r.record_date DESC, c.name ASC, s.name ASC
    '''
    rows = db.execute(query, class_ids).fetchall()
    
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(['Data', 'Turma', 'Aluno', 'Status', 'Nota', 'Homework', 'Observacao'])
    for row in rows:
        cw.writerow([row['record_date'], row['turma'], row['aluno'], row['status'], row['grade'], row['homework'], row['comments']])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=relatorio_geral.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output


# ==========================================================
# --- ÁREA SECRETA DE MANUTENÇÃO (RAIO-X E FAXINA) ---
# ==========================================================

@app.route('/manutencao', methods=['GET', 'POST'])
def manutencao_login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == 'senha_manutencao_123': 
            session['manutencao_auth'] = True
            return redirect(url_for('manutencao_painel'))
        else:
            return "<script>alert('Senha incorreta!'); window.location.href='/manutencao';</script>"
    
    return """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head><title>Login de Manutenção</title></head>
    <body style="font-family: Arial; background: #f1f5f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
        <div style="background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); text-align: center; width: 100%; max-width: 350px;">
            <h2 style="color: #334155; margin-top:0;">🔧 Manutenção</h2>
            <p style="color: #64748b; margin-bottom: 20px; font-size: 0.9rem;">Acesso restrito para limpeza de banco</p>
            <form method="POST">
                <input type="password" name="senha" placeholder="Senha de Segurança" required style="padding: 12px; width: 100%; box-sizing: border-box; margin-bottom: 20px; border: 1px solid #cbd5e1; border-radius: 6px;">
                <button type="submit" style="background: #1e293b; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; width: 100%; font-weight: bold;">Acessar Sistema</button>
            </form>
            <br><a href="/" style="color: #3b82f6; text-decoration: none; font-size: 0.85em;">Voltar ao site principal</a>
        </div>
    </body>
    </html>
    """

@app.route('/manutencao/painel')
def manutencao_painel():
    if not session.get('manutencao_auth'):
        return redirect(url_for('manutencao_login'))
    
    return """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head><title>Painel de Manutenção</title></head>
    <body style="font-family: Arial; background: #f1f5f9; padding: 50px; text-align: center;">
        <div style="background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto;">
            <h2 style="color: #10b981; margin-top:0;">Painel de Faxina e Raio-X 🧹</h2>
            <p style="color: #475569; margin-bottom: 30px;">Clique no botão abaixo para varrer o banco de dados. Isso irá deletar perfis fantasmas e tentar remover os sufixos numéricos (como '2' ou '3') dos logins.</p>
            <form action="/manutencao/executar" method="POST">
                <button type="submit" style="background: #ef4444; color: white; border: none; padding: 15px 30px; font-size: 1.1rem; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s;">🔍 Executar Faxina e Raio-X</button>
            </form>
            <br><br>
            <a href="/manutencao/sair" style="color: #64748b; text-decoration: none; font-size: 0.9rem;">Sair e Fechar Acesso Seguro</a>
        </div>
    </body>
    </html>
    """

@app.route('/manutencao/executar', methods=['POST'])
def manutencao_executar():
    if not session.get('manutencao_auth'):
        return redirect(url_for('manutencao_login'))
        
    db = get_db()
    cur = db.cursor()
    
    cur.execute("DELETE FROM users WHERE role='parent' AND NOT EXISTS (SELECT 1 FROM students WHERE students.parent_id = users.id)")
    fantasmas_apagados = cur.rowcount
    db.commit() 
    
    alunos = cur.execute('''
        SELECT s.id as student_id, s.name as student_name, s.parent_id, u.username, c.name as class_name
        FROM students s 
        JOIN users u ON s.parent_id = u.id
        JOIN classes c ON s.class_id = c.id
        WHERE u.role = 'parent'
    ''').fetchall()
    
    atualizados = 0
    relatorio = ""
    
    for aluno in alunos:
        login_ideal = gerar_username_pai(aluno['student_name'])
        novo_login = login_ideal
        
        conflito = cur.execute('''
            SELECT u.id, u.role, u.full_name, s.name as aluno_dono, c.name as turma_dono
            FROM users u
            LEFT JOIN students s ON s.parent_id = u.id
            LEFT JOIN classes c ON s.class_id = c.id
            WHERE u.username = ? AND u.id != ?
        ''', (login_ideal, aluno['parent_id'])).fetchone()
        
        if conflito:
            if conflito['aluno_dono']:
                relatorio += f"<li>⚠️ <b>{aluno['student_name']} (Turma: {aluno['class_name']}):</b> Não pôde remover o '2' porque o login '{login_ideal}' já pertence a um registro ativo: <b>{conflito['aluno_dono']} (Turma: {conflito['turma_dono']})</b>. Remova o aluno duplicado na outra turma primeiro!</li>"
            else:
                relatorio += f"<li>⚠️ <b>{aluno['student_name']}:</b> Não pôde remover o '2' porque o login '{login_ideal}' já é usado por um Professor ou Admin do sistema ({conflito['full_name']}).</li>"
            
            contador = 2
            while True:
                checa_num = cur.execute('SELECT id FROM users WHERE username = ? AND id != ?', 
                                        (f"{login_ideal}{contador}", aluno['parent_id'])).fetchone()
                if not checa_num:
                    novo_login = f"{login_ideal}{contador}"
                    break
                contador += 1
            
        if aluno['username'] != novo_login:
            cur.execute("UPDATE users SET username = ? WHERE id = ?", (novo_login, aluno['parent_id']))
            relatorio += f"<li>✅ <b>{aluno['student_name']}:</b> Corrigido de <i style='color:#ef4444'>{aluno['username']}</i> para <b style='color:#10b981'>{novo_login}</b></li>"
            atualizados += 1
            db.commit() 
            
    if relatorio == "":
        relatorio = "<li>Nenhum login precisou ser corrigido. Todos já estão com os nomes perfeitos!</li>"
            
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 50px auto; text-align: center; background: #f8fafc; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h1 style="color: #10b981; margin-bottom: 5px;">Relatório Final 📋✨</h1>
        
        <div style="display: flex; justify-content: center; gap: 20px; margin: 20px 0;">
            <div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; width: 45%;">
                <h2 style="margin: 0; color: #ef4444;">{fantasmas_apagados}</h2>
                <small style="color: #64748b;">Fantasmas Apagados</small>
            </div>
            <div style="background: white; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; width: 45%;">
                <h2 style="margin: 0; color: #3b82f6;">{atualizados}</h2>
                <small style="color: #64748b;">Logins Corrigidos</small>
            </div>
        </div>

        <h3 style="color: #1e293b; text-align: left; margin-bottom: 10px;">📋 Ocorrências:</h3>
        <ul style="text-align: left; color: #334155; font-size: 0.95rem; line-height: 1.8; background: white; padding: 20px 40px; border-radius: 8px; border: 1px solid #e2e8f0;">
            {relatorio}
        </ul>
        <br>
        <a href='/manutencao/painel' style="color: #64748b; text-decoration: none;">Voltar ao painel</a> | 
        <a href='/manutencao/sair' style="color: #ef4444; text-decoration: none; font-weight: bold;">Sair da Manutenção</a>
    </div>
    """

@app.route('/manutencao/sair')
def manutencao_sair():
    session.pop('manutencao_auth', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db_if_not_exists()
    app.run(debug=True)