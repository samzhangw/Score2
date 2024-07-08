from flask import Flask, render_template, request, redirect, session
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# 定義數據庫模型
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    math = db.Column(db.Integer)
    science = db.Column(db.Integer)
    leaves = db.relationship('Leave', backref='student', lazy=True)
    grade_access_start_time = db.Column(db.DateTime)  # 新字段：成績查看開始時間
    grade_access_end_time = db.Column(db.DateTime)  # 新字段：成績查看結束時間

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject = db.Column(db.String(20), nullable=False)
    score = db.Column(db.Integer)
    weight = db.Column(db.Float, default=1.0)  # 添加 weight 屬性，默認為 1.0

class Leave(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')
    weight = db.Column(db.Integer, nullable=True)  # 允許為空或者設置默認值


# 創建數據庫表
with app.app_context():
    db.create_all()

# 首頁
@app.route('/')
def index():
    return render_template('index.html')
# 添加学生账号密码
@app.route('/add_student_account', methods=['POST'])
def add_student_account():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            username = request.form['username']
            password = request.form['password']
            if not Student.query.filter_by(username=username).first():
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
                new_student = Student(username=username, password=hashed_password)
                db.session.add(new_student)
                db.session.commit()
                return redirect('/dashboard_admin')
            return "Student account already exists"
    return redirect('/dashboard_admin')
# 新增学生页面
@app.route('/add_student_page')
def add_student_page():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            return render_template('add_student_page.html')
    return redirect('/dashboard_admin')
# 設置成績查看時間頁面
@app.route('/set_grade_access_time_page')
def set_grade_access_time_page():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            students = Student.query.all()  # 确保使用 .all() 方法
            return render_template('set_grade_access_time.html', students=students)
    return redirect('/dashboard_admin')
@app.route('/set_grade_access_time', methods=['POST'])
def set_grade_access_time():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            username = request.form['username']
            access_start_time_str = request.form['access_start_time']
            access_end_time_str = request.form['access_end_time']
            
            # 檢查日期和時間格式的有效性
            try:
                access_start_time = datetime.strptime(access_start_time_str, '%Y-%m-%dT%H:%M')
                access_end_time = datetime.strptime(access_end_time_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                return "Invalid datetime format. Please select valid date and time."

            # 檢查截止時間是否晚於開始時間
            if access_start_time >= access_end_time:
                return "End time must be later than start time."

            student = Student.query.filter_by(username=username).first()
            if student:
                student.grade_access_start_time = access_start_time
                student.grade_access_end_time = access_end_time
                db.session.commit()
                return redirect('/dashboard_admin')
            return "Student does not exist"
    return redirect('/dashboard_admin')
# 登錄
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    # 學生登錄
    student = Student.query.filter_by(username=username).first()
    if student and bcrypt.check_password_hash(student.password, password):
        session['username'] = username
        session['role'] = 'student'
        return redirect('/dashboard_student')
    # 管理員登錄
    admin = Admin.query.filter_by(username=username).first()
    if admin and bcrypt.check_password_hash(admin.password, password):
        session['username'] = username
        session['role'] = 'admin'
        return redirect('/dashboard_admin')
    return render_template('index.html', error="Invalid username or password")

# 學生儀表板
@app.route('/dashboard_student')
def dashboard_student():
    if 'username' in session and session.get('role') == 'student':
        student = Student.query.filter_by(username=session['username']).first()
        if student:
            return render_template('dashboard_student.html', username=session['username'], student=student)
    return redirect('/')

@app.route('/grades')
def grades():
    if 'username' in session and session.get('role') == 'student':
        student = Student.query.filter_by(username=session['username']).first()
        if student:
            current_time = datetime.now()
            if (not student.grade_access_start_time or current_time < student.grade_access_start_time) or \
                    (student.grade_access_end_time and current_time > student.grade_access_end_time):
                return render_template('grade_access_expired.html', student=student)  # Pass student to the template
            student_grades = Grade.query.filter_by(student_id=student.id).all()
            return render_template('grades.html', grades=student_grades, student=student)
    return redirect('/')


@app.route('/delete_subject', methods=['POST'])
def delete_subject():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            subject_name = request.form['subject_name']
            if subject_name:
                # Delete subject-related records here
                Grade.query.filter_by(subject=subject_name).delete()
                db.session.commit()
                return redirect('/input_grades')
    return redirect('/dashboard_admin')

# 請假頁面
@app.route('/leave_request')
def leave_request():
    if 'username' in session and session.get('role') == 'student':
        student = Student.query.filter_by(username=session['username']).first()
        if student:
            return render_template('leave_request.html', student=student)
    return redirect('/')

# 管理員儀表板
@app.route('/dashboard_admin')
def dashboard_admin():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            students = Student.query.all()
            return render_template('dashboard_admin.html', username=session['username'], students=students)
    return redirect('/')

# 登出
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect('/')

# 學生註冊
@app.route('/register_student_page')
def register_student_page():
    return render_template('register_student_page.html')

@app.route('/register_student', methods=['POST'])
def register_student():
    username = request.form['username']
    password = request.form['password']
    if not Student.query.filter_by(username=username).first():
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_student = Student(username=username, password=hashed_password)
        db.session.add(new_student)
        db.session.commit()
        session['username'] = username
        session['role'] = 'student'
        return redirect('/dashboard_student')
    else:
        return "Student account already exists"

# 管理員註冊
@app.route('/register_admin_page')
def register_admin_page():
    return render_template('register_admin_page.html')

@app.route('/register_admin', methods=['POST'])
def register_admin():
    username = request.form['username']
    password = request.form['password']
    if not Admin.query.filter_by(username=username).first():
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_admin = Admin(username=username, password=hashed_password)
        db.session.add(new_admin)
        db.session.commit()
        session['username'] = username
        session['role'] = 'admin'
        return redirect('/dashboard_admin')
    else:
        return "Admin account already exists"

# 提交請假
@app.route('/submit_leave', methods=['POST'])
def submit_leave():
    if 'username' in session and session.get('role') == 'student':
        student = Student.query.filter_by(username=session['username']).first()
        if student:
            leave_date = request.form['leave_date']
            leave_reason = request.form['leave_reason']
            new_leave = Leave(date=leave_date, reason=leave_reason, student_id=student.id)
            db.session.add(new_leave)
            db.session.commit()
    return redirect('/leave_request')

@app.route('/leave_approval')
def leave_approval():
    if 'username' in session and session.get('role') == 'admin':
        pending_leaves = Leave.query.filter_by(status='pending').all()
        approved_leaves = Leave.query.filter_by(status='approved').all()
        return render_template('leave_approval.html', pending_leaves=pending_leaves, approved_leaves=approved_leaves)
    return redirect('/')

# 核准請假
@app.route('/approve_leave', methods=['POST'])
def approve_leave():
    if 'username' in session and session.get('role') == 'admin':
        leave_id = request.form['leave_id']
        leave = Leave.query.get(leave_id)
        if leave:
            leave.status = 'approved'
            db.session.commit()
    return redirect('/leave_approval')

# 註冊學生列表
@app.route('/registered_students')
def registered_students():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            return render_template('registered_students.html', students=Student.query.all())
    return redirect('/dashboard_admin')
@app.route('/input_grades', methods=['GET', 'POST'])
def input_grades():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            if request.method == 'POST':
                for student in Student.query.all():
                    for subject in request.form.keys():
                        if subject.startswith(f"{student.id}_"):
                            score = request.form[subject]
                            subject_name = subject.split('_')[1]
                            if score:
                                existing_grade = Grade.query.filter_by(student_id=student.id, subject=subject_name).first()
                                if existing_grade:
                                    existing_grade.score = int(score)
                                else:
                                    new_grade = Grade(student_id=student.id, subject=subject_name, score=int(score))
                                    db.session.add(new_grade)
                db.session.commit()
                return redirect('/dashboard_admin')
            
            subjects = [grade.subject for grade in Grade.query.with_entities(Grade.subject).distinct()]
            return render_template('input_grades.html', students=Student.query.all(), subjects=subjects)
    
    return redirect('/dashboard_admin')
@app.route('/student_grades', methods=['POST'])
def student_grades():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            student_id = request.form['student_id']
            student = Student.query.get(student_id)
            grades = Grade.query.filter_by(student_id=student_id).all()
            return render_template('student_grades.html', student=student, grades=grades)
    return redirect('/login')

@app.route('/select_student')
def select_student():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            students = Student.query.all()
            return render_template('select_student.html', students=students)
    return redirect('/login')

# 添加科目
@app.route('/add_subject', methods=['POST'])
def add_subject():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            subject_name = request.form['new_subject']
            if subject_name:
                # 检查科目是否已经存在
                if not Grade.query.filter_by(subject=subject_name).first():
                    # 为所有学生创建该科目的成绩记录，初始成绩为0或空
                    for student in Student.query.all():
                        new_grade = Grade(student_id=student.id, subject=subject_name, score=0)
                        db.session.add(new_grade)
                    db.session.commit()
                    return redirect('/input_grades')
                else:
                    return "Subject already exists."
    return redirect('/dashboard_admin')
# 請假歷史紀錄頁面
@app.route('/leave_history')
def leave_history():
    if 'username' in session and session.get('role') == 'student':
        student = Student.query.filter_by(username=session['username']).first()
        if student:
            return render_template('leave_history.html', student=student)
    return redirect('/')

# New route to display grade access times for all students
@app.route('/grade_access_times')
def grade_access_times():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            students = Student.query.all()
            return render_template('grade_access_times.html', students=students)
    return redirect('/dashboard_admin')
# 管理員設置科目加權頁面
@app.route('/set_subject_weights_page')
def set_subject_weights_page():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            subjects = [grade.subject for grade in Grade.query.with_entities(Grade.subject).distinct() if grade.subject != 'default']  # 过滤掉默认科目
            current_weights = {subject: Grade.weight for subject in subjects}  # 假設 Grade 模型中有 weight 属性
            return render_template('set_subject_weights.html', subjects=subjects, current_weights=current_weights)
    return redirect('/dashboard_admin')


# 設定科目權重路由
@app.route('/set_subject_weights', methods=['GET', 'POST'])
def set_subject_weights():
    if 'username' in session and session.get('role') == 'admin':
        if request.method == 'POST':
            admin = Admin.query.filter_by(username=session['username']).first()
            if admin:
                for subject in request.form.keys():
                    if subject != 'submit':
                        new_weight = request.form[subject]
                        # 更新数据库中的科目加权
                        grade = Grade.query.filter_by(subject=subject).first()
                        if grade:
                            grade.weight = float(new_weight)
                db.session.commit()
                return redirect('/weighted_total_scores')  # 重定向到加權後總分頁面

        # 取得目前設定的科目權重
        subjects = [grade.subject for grade in Grade.query.all()]
        current_weights = {grade.subject: grade.weight for grade in Grade.query.all()}
        return render_template('set_subject_weights.html', subjects=subjects, current_weights=current_weights)

    return redirect('/dashboard_admin')


@app.route('/grade_analysis')
def grade_analysis():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            # 獲取所有學生的成績
            students = Student.query.all()
            grades_summary = {}
            for student in students:
                grades = Grade.query.filter_by(student_id=student.id).all()
                total_score = 0
                num_subjects = 0
                max_score = float('-inf')
                min_score = float('inf')
                for grade in grades:
                    if grade.score is not None:
                        total_score += grade.score
                        num_subjects += 1
                        if grade.score > max_score:
                            max_score = grade.score
                        if grade.score < min_score:
                            min_score = grade.score
                
                if num_subjects > 0:
                    average_score = total_score / num_subjects
                else:
                    average_score = 0
                
                grades_summary[student.username] = {
                    'average_score': average_score,
                    'max_score': max_score if max_score != float('-inf') else None,
                    'min_score': min_score if min_score != float('inf') else None
                }
            
            return render_template('grade_analysis.html', grades_summary=grades_summary)
    return redirect('/dashboard_admin')

# Flask 路由: 管理員查看加權後總分頁面
@app.route('/weighted_total_scores')
def weighted_total_scores():
    if 'username' in session and session.get('role') == 'admin':
        admin = Admin.query.filter_by(username=session['username']).first()
        if admin:
            students = Student.query.all()
            weighted_scores = {}
            for student in students:
                grades = Grade.query.filter_by(student_id=student.id).all()
                total_weighted_score = 0
                total_weight = 0
                for grade in grades:
                    total_weighted_score += grade.score * grade.weight  # 每個科目成績乘以權重
                    total_weight += grade.weight  # 累計權重
                
                if total_weight > 0:
                    weighted_total = total_weighted_score   # 總分除以加權總權重
                else:
                    weighted_total = 0
                
                weighted_scores[student.username] = round(weighted_total, 1)  # 四捨五入到小數點後一位
            
            return render_template('weighted_total_scores.html', weighted_scores=weighted_scores)
    return redirect('/dashboard_admin')





if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=4000)
