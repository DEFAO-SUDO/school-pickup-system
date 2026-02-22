from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"
DB_NAME = 'students.db'

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # USERS TABLE
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    ''')
    # Ensure 'classes' and 'phone' exist
    try:
        c.execute("ALTER TABLE users ADD COLUMN classes TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    except sqlite3.OperationalError:
        pass

    # STUDENTS TABLE
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            class TEXT,
            stream TEXT,
            parent TEXT,
            parent_number TEXT,
            admission_number TEXT UNIQUE,
            status TEXT DEFAULT 'Not Picked'
        )
    ''')

    # HISTORY TABLE
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            parent TEXT,
            parent_number TEXT,
            time TEXT
        )
    ''')

    # DEFAULT ADMIN
    c.execute("INSERT OR IGNORE INTO users (id, username, password, role, classes, phone) VALUES (1,'admin','admin123','admin','','')")

    conn.commit()
    conn.close()

init_db()

# ================= LOGIN =================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username,password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user'] = user[1]
            session['role'] = user[3]
            session['classes'] = user[4] if user[4] else ''
            return redirect('/')
        else:
            return "Invalid Login"
    return render_template('login.html')

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ================= CREATE USER =================
@app.route('/create_user', methods=['GET','POST'])
def create_user():
    if 'user' not in session or session['role'] != 'admin':
        return "Access Denied"
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        classes = request.form['classes']
        phone = request.form['phone']

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username,password,role,classes,phone) VALUES (?,?,?,?,?)",
                      (username,password,role,classes,phone))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists!"
        conn.close()
        return redirect('/')
    return render_template('create_user.html')

# ================= MANAGE TEACHERS =================
@app.route('/manage_users')
def manage_users():
    if 'user' not in session or session['role'] != 'admin':
        return "Access Denied"

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, role, classes, phone FROM users WHERE role='teacher'")
    teachers = c.fetchall()
    conn.close()
    
    teacher_count = len(teachers)
    return render_template('manage_users.html', teachers=teachers, teacher_count=teacher_count)

@app.route('/delete_user/<int:id>')
def delete_user(id):
    if 'user' not in session or session['role'] != 'admin':
        return "Access Denied"

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/manage_users')

# ================= HOME =================
@app.route('/')
def index():
    if 'user' not in session:
        return redirect('/login')

    search = request.args.get('search')
    filter_class = request.args.get('filter_class')
    filter_stream = request.args.get('filter_stream')

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if session['role'] == 'teacher':
        assigned_classes = [cls.strip() for cls in session['classes'].split(',') if cls.strip()]
        if assigned_classes:
            query_conditions = []
            params = []
            for ac in assigned_classes:
                if '-' in ac:
                    cls, strm = ac.split('-')
                    query_conditions.append("(class=? AND stream=?)")
                    params.extend([cls,strm])
                else:
                    query_conditions.append("(class=?)")
                    params.append(ac)
            where_clause = ' OR '.join(query_conditions)
            if search:
                c.execute(f"SELECT * FROM students WHERE ({where_clause}) AND name LIKE ?", (*params,f'%{search}%'))
            else:
                c.execute(f"SELECT * FROM students WHERE {where_clause}", params)
        else:
            c.execute("SELECT * FROM students WHERE 1=0")
    else:
        query = "SELECT * FROM students WHERE 1=1"
        params = []
        if filter_class:
            query += " AND class=?"
            params.append(filter_class)
        if filter_stream:
            query += " AND stream=?"
            params.append(filter_stream)
        if search:
            query += " AND name LIKE ?"
            params.append(f'%{search}%')
        c.execute(query, params)

    students = c.fetchall()
    conn.close()
    return render_template('index.html', students=students, role=session['role'])

# ================= ADD STUDENT =================
@app.route('/add', methods=['GET','POST'])
def add_student():
    if 'user' not in session:
        return redirect('/login')
    if request.method == 'POST':
        name = request.form['name']
        class_name = request.form['class']
        stream = request.form['stream']
        parent = request.form['parent']
        parent_number = request.form['parent_number']
        admission_number = request.form['admission_number']

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO students (name,class,stream,parent,parent_number,admission_number) VALUES (?,?,?,?,?,?)",
                (name,class_name,stream,parent,parent_number,admission_number)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Admission Number already exists!"
        conn.close()
        return redirect('/')
    return render_template('add_student.html')

# ================= PICKUP =================
@app.route('/pickup/<int:id>', methods=['POST'])
def pickup(id):
    if 'user' not in session:
        return redirect('/login')

    admission_input = request.form['admission_number']

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name,class,stream,parent,parent_number,admission_number FROM students WHERE id=?", (id,))
    student = c.fetchone()

    if student and student[5] == admission_input:
        c.execute("UPDATE students SET status='Picked' WHERE id=?", (id,))
        c.execute(
            "INSERT INTO history (student_name,parent,parent_number,time) VALUES (?,?,?,?)",
            (student[0], student[3], student[4], datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

    conn.close()
    return redirect('/')

# ================= HISTORY =================
@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/login')
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM history ORDER BY id DESC")
    records = c.fetchall()
    conn.close()
    return render_template('history.html', records=records)

# ================= RUN =================
if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)