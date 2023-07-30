import base64
import hashlib
import os
import re
import cv2
import wget
from flask import Flask, request, render_template, flash, redirect, url_for, session, logging, send_file
from flask_mysqldb import MySQL
import MySQLdb.cursors
import numpy as np
from wtforms import Form, StringField, TextAreaField, PasswordField, validators, DateTimeField, BooleanField, IntegerField, SelectField
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from functools import wraps
from werkzeug.utils import secure_filename
from coolname import generate_slug
from datetime import timedelta, datetime
from flask import render_template_string
from flask_mobility import Mobility
from proctoring.proctoring import get_analysis, yolov3_model_v3_path
from deepface import DeepFace
import functools
import math
import random
import json
import csv
import smtplib
from dotenv import load_dotenv
from flask_session import Session
from flask_cors import CORS, cross_origin
from wtforms_components import TimeField
from wtforms.fields import DateField
from wtforms.validators import ValidationError

load_dotenv()
app = Flask(__name__)

app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT'))
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_TYPE'] = 'filesystem'

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['CORS_HEADERS'] = 'Content-Type'

CORS(app)
Session(app)
Mobility(app)

mysql = MySQL(app)

# Function to check if user is logged in
def is_logged(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if (request.MOBILE):
            return render_template('mobile.html')
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('login_email'))
    return wrap


# Function to face verify
def face_verify(storedImage, inputImage):
    nparr1 = np.frombuffer(base64.b64decode(storedImage), np.uint8)
    nparr2 = np.frombuffer(base64.b64decode(inputImage), np.uint8)
    image1 = cv2.imdecode(nparr1, cv2.COLOR_BGR2GRAY)
    image2 = cv2.imdecode(nparr2, cv2.COLOR_BGR2GRAY)
    img_result = DeepFace.verify(
        image1, image2, model_name='Facenet', enforce_detection=False)
    return img_result


@app.route('/')
@app.route('/login_email', methods=['GET', 'POST'])
def login_email():
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        hash = password + app.config['SECRET_KEY']
        hash = hashlib.sha1(hash.encode())
        password = hash.hexdigest()
        imgdata1 = request.form['image_hidden']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            'SELECT * FROM users WHERE email = % s AND password = % s', (email, password, ))
        account = cursor.fetchone()
        if account:
            imgdata2 = account['user_image']
            img_result = face_verify(imgdata1, imgdata2)
            if img_result["verified"] == True:
                session['logged_in'] = True
                session['email'] = account['email']
                session['role'] = account['role']
                session['name'] = account['name']
                session['class_id'] = account['class_id']
                return redirect(url_for('dashboard'))
            else:
                msg = '⚠️ Face identity could not be verified !'
        else:
            msg = '⚠️ Incorrect email / password !'
    return render_template('login_email.html', msg=msg)


@app.route('/login_phone', methods=['GET', 'POST'])
def login_phone():
    msg = ''
    if request.method == 'POST' and 'phone' in request.form and 'password' in request.form:
        phone = request.form['phone']
        phone = phone.replace('+', '')
        password = request.form['password']
        hash = password + app.config['SECRET_KEY']
        hash = hashlib.sha1(hash.encode())
        password = hash.hexdigest()
        imgdata1 = request.form['image_hidden']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            'SELECT * FROM users WHERE phone = % s AND password = % s', (phone, password, ))
        account = cursor.fetchone()
        if account:
            imgdata2 = account['user_image']
            img_result = face_verify(imgdata1, imgdata2)
            if img_result["verified"] == True:
                session['logged_in'] = True
                session['email'] = account['email']
                session['phone'] = account['phone']
                session['role'] = account['role']
                session['name'] = account['name']
                session['class_id'] = account['class_id']
                session['isActive'] = account['isActive']
                return redirect(url_for('dashboard'))
            else:
                msg = '⚠️ Face identity could not be verified !'
        else:
            msg = '⚠️ Incorrect phone number / password !'
    return render_template('login_phone.html', msg=msg)


@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        name = request.form['name']
        dob = request.form['dob']
        phone = request.form['phone']
        email = request.form['email']
        gender = request.form['gender']
        role = request.form['role']
        imgdata = request.form['image_hidden']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            'SELECT * FROM users WHERE email = % s OR phone = %s', (email, phone,))
        account = cursor.fetchone()
        if account:
            msg = '⚠️ Email/Phone Number is already registered !'
        elif not re.fullmatch(r'[A-Za-z]+', name):
            msg = '⚠️ Name must contain only characters !'
        elif not re.fullmatch(r'[+][0-9]*', phone):
            msg = '⚠️ Phone Number must contain only numbers !'
        elif not re.fullmatch(r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
            msg = '⚠️ Password must contain at least one uppercase letter, one number and one special character and be at least 8 characters long !'
        else:
            hash = password + app.config['SECRET_KEY']
            hash = hashlib.sha1(hash.encode())
            password = hash.hexdigest()
            phone = phone.replace('+', '')
            dob = dob.replace('/', '-')
            if (role == 'S'):
                programme = request.form['programme'] or None
                branch = request.form['branch'] or None
                semester = request.form['semester'] or None
                class_id = get_class_id(programme, branch, semester)
                cursor.execute("INSERT INTO users (name,password,phone,dob,email,gender,role,class_id,user_image,isActive) VALUES (% s, %s, %s, STR_TO_DATE(%s, '%%d-%%m-%%Y'), % s, %s, %s, %s, %s,'Y')",
                               (name, password, phone, dob, email, gender, role, class_id, imgdata,))
            else:
                cursor.execute("INSERT INTO users (name,password,phone,dob,email,gender,role,user_image,isActive) VALUES (% s, %s, %s, STR_TO_DATE(%s, '%%d-%%m-%%Y'), % s, %s, %s,%s,'Y')",
                               (name, password, phone, dob, email, gender, role, imgdata,))
            mysql.connection.commit()
            msg = 'You have successfully registered !'
            return render_template('login_email.html', msg=msg)
    elif request.method == 'POST':
        msg = 'Please fill out the form !'
    return render_template('register.html', msg=msg)


@app.route('/')
@app.route('/dashboard')
@is_logged
def dashboard():
    role = session.get('role', None)
    isActive = session.get('isActive', None)
    if (isActive == 'N'):
        return redirect(url_for('login_email', msg='⚠️ Your account is currently disabled !'))
    if role == 'T':
        return render_template('admin_dashboard.html')
    elif role == 'S':
        return render_template('student_dashboard.html')
    else:
        return redirect(url_for('login_email'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_email'))


class UploadForm(FlaskForm):
    subject = StringField('Subject')
    topic = StringField('Topic')
    programme = SelectField('Programme', choices=[
                            ('BTech', 'B.Tech'), ('MTech', 'M.Tech')])
    branch = SelectField('Branch', choices=[
                         ('CSE', 'CSE'), ('ECE', 'ECE'), ('DSAI', 'DSAI')])
    semester = SelectField('Semester', choices=[(
        1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5'), (6, '6'), (7, '7'), (8, '8')])
    start_date = DateField('Start Date')
    start_time = TimeField(
        'Start Time', default=datetime.utcnow()+timedelta(hours=5.5))
    end_date = DateField('End Date')
    end_time = TimeField(
        'End Time', default=datetime.utcnow()+timedelta(hours=5.5))
    duration = IntegerField('Duration (in mins)')

    def validate_end_date(form, field):
        if field.data < form.start_date.data:
            raise ValidationError(
                "End date must not be earlier than start date.")

    def validate_end_time(form, field):
        start_date_time = datetime.strptime(str(form.start_date.data) + " " + str(
            form.start_time.data), "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
        end_date_time = datetime.strptime(str(form.end_date.data) + " " + str(
            field.data), "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
        if start_date_time >= end_date_time:
            raise ValidationError(
                "End date time must not be earlier/equal than start date time")

    def validate_start_date(form, field):
        if datetime.strptime(str(form.start_date.data) + " " + str(form.start_time.data), "%Y-%m-%d %H:%M:%S") < datetime.now():
            raise ValidationError(
                "Start date and time must not be earlier than current")


@app.route('/create-test', methods=['GET', 'POST'])
@is_logged
def admin_create_test():
    form = UploadForm()
    if request.method == 'POST':
        test_id = generate_slug(2)
        cur = mysql.connection.cursor()
        start_date = form.start_date.data
        end_date = form.end_date.data
        start_time = form.start_time.data
        end_time = form.end_time.data
        start_date_time = str(start_date) + " " + str(start_time)
        end_date_time = str(end_date) + " " + str(end_time)
        duration = int(form.duration.data)*60
        subject = form.subject.data
        topic = form.topic.data
        programme = form.programme.data
        branch = form.branch.data
        semester = form.semester.data
        class_id = get_class_id(programme, branch, semester)
        cur.execute('INSERT INTO testinfo (email, test_id, start, end, duration, subject, topic, class_id) values(%s,%s,%s,%s,%s,%s,%s,%s)', (dict(
            session)['email'], test_id, start_date_time, end_date_time, duration, subject, topic, class_id))
        cur.connection.commit()
        cur.close()
        session['testid'] = test_id
        return redirect(url_for('addques', testid=test_id, newq=1))
    return render_template('admin_create_test.html', form=form)


@app.route('/admin_edit_questions', methods=['GET'])
@is_logged
def admin_edit_questions():
    cur = mysql.connection.cursor()
    results = cur.execute(
        'SELECT test_id,subject,topic from testinfo where email = %s', [session['email']])
    if results > 0:
        cresults = cur.fetchall()
        cur.close()
        return render_template("admin_edit_questions.html", cresults=cresults)
    else:
        return render_template("admin_edit_questions.html", cresults=None)


@app.route('/admin_display_questions', methods=['GET', 'POST'])
@is_logged
def admin_display_questions():
    if request.method == 'POST':
        session['testid'] = request.form['choosetid']
    cur = mysql.connection.cursor()
    cur.execute('SELECT * from questions where test_id = %s',
                [session['testid']])
    callresults = cur.fetchall()
    cur.close()
    newq = len(callresults) + 1
    return render_template("admin_display_questions.html", callresults=callresults, newq=newq, testid=session['testid'])


@app.route('/delete/<testid>/<qid>')
@is_logged
def del_qid(testid, qid):
    cur = mysql.connection.cursor()
    results = cur.execute(
        'DELETE FROM questions where test_id = %s and qid =%s', (testid, qid))
    mysql.connection.commit()
    if results > 0:
        msg = "Deleted successfully"
        flash(msg, 'success')
        cur.close()
        return redirect(url_for('admin_display_questions', success=msg))
    else:
        msg = "ERROR  OCCURED."
        flash(msg, 'error')
        return redirect(url_for('admin_display_questions', error=msg))


@app.route('/addques/<testid>/<newq>', methods=['GET', 'POST'])
@is_logged
def addques(testid, newq):
    if request.method == 'GET':
        return render_template("admin_new_question.html", testid=testid, newq=newq)
    if request.method == 'POST':
        ques = request.form['ques']
        ao = request.form['ao']
        bo = request.form['bo']
        co = request.form['co']
        do = request.form['do']
        anso = request.form['anso']
        cur = mysql.connection.cursor()
        cur.execute('INSERT INTO questions values(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (testid, newq, ques, ao, bo, co, do, anso, 1))
        cur.connection.commit()
        msg = "Added successfully"
        flash(msg, 'success')
        cur.close()
        return redirect(url_for('admin_display_questions', success=msg))
    else:
        msg = "ERROR  OCCURED."
        flash(msg, 'error')
        return redirect(url_for('admin_display_questions', error=msg))


@app.route('/update/<testid>/<qid>', methods=['GET', 'POST'])
@is_logged
def update_quiz(testid, qid):
    if request.method == 'GET':
        cur = mysql.connection.cursor()
        cur.execute(
            'SELECT * FROM questions where test_id = %s and qid =%s', (testid, qid))
        uresults = cur.fetchall()
        mysql.connection.commit()
        return render_template("admin_update_question.html", uresults=uresults)
    if request.method == 'POST':
        ques = request.form['ques']
        ao = request.form['ao']
        bo = request.form['bo']
        co = request.form['co']
        do = request.form['do']
        anso = request.form['anso']
        cur = mysql.connection.cursor()
        cur.execute('UPDATE questions SET q = %s, a = %s, b = %s, c = %s, d = %s, ans = %s where test_id = %s and qid = %s',
                    (ques, ao, bo, co, do, anso, testid, qid))
        cur.connection.commit()
        msg = "Updated successfully"
        flash(msg, 'success')
        cur.close()
        return redirect(url_for('admin_display_questions', success=msg))
    else:
        msg = "ERROR  OCCURED."
        flash(msg, 'error')
        return redirect(url_for('admin_display_questions', error=msg))


@app.route('/intermediate', methods=['GET', 'POST'])
@is_logged
def intermediate():
    global duration, marked_ans, subject, topic
    if request.method == 'POST':
        values = request.form['chooseexam']
        test_id, subject, topic, duration = values.split(',')
        imgdata1 = request.form['image_hidden']
        cur1 = mysql.connection.cursor()
        results1 = cur1.execute(
            'SELECT user_image from users where email = %s', (session['email'],))
        if results1 > 0:
            cresults = cur1.fetchone()
            imgdata2 = cresults['user_image']
            img_result = face_verify(imgdata1, imgdata2)
            if img_result["verified"] == True:
                time = cur1.execute(
                    'SELECT time_to_sec(time_left) as time_left,completed from teststatus where email = %s and test_id = %s', (session['email'], test_id,))
                if time > 0:
                    time = cur1.fetchone()
                    is_completed = time['completed']
                    if is_completed == 0:
                        time_left = time['time_left']
                        if time_left <= duration:
                            duration = time_left
                ans = cur1.execute(
                    'SELECT qid , ans from studentans where email = %s and test_id = %s', (session['email'], test_id,))
                marked_ans = {}
                if ans > 0:
                    ans = cur1.fetchall()
                    for row in ans:
                        qiddb = ""+row['qid']
                        marked_ans[qiddb] = row['ans']
                    marked_ans = json.dumps(marked_ans)
                status = cur1.execute(
                    'SELECT * from teststatus where email = %s and test_id = %s', (session['email'], test_id,))
                if (not status):
                    cur1.execute(
                        'INSERT INTO teststatus(email,test_id,time_left) values(%s,%s,%s)', (session['email'], test_id, duration))
                    mysql.connection.commit()

                return redirect(url_for('test', testid=test_id))
            else:
                msg = '⚠️ Face identity could not be verified !'
                flash(msg, 'error')
                return redirect(url_for('give_test', error=msg))


@app.route('/appear-test/<testid>', methods=['GET', 'POST'])
@is_logged
def test(testid):
    global duration, marked_ans, subject, topic
    if request.method == 'GET':
        try:
            data = {'duration': duration, 'marks': '',
                    'q': '', 'a': '', 'b': '', 'c': '', 'd': ''}
            return render_template('quiz.html', **data, answers=marked_ans, subject=subject, topic=topic, tid=testid)
        except:
            return redirect(url_for('give_test'))
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        flag = request.form['flag']
        if flag == 'get':
            num = request.form['no']
            results = cur.execute(
                'SELECT test_id,qid,q,a,b,c,d,ans,marks from questions where test_id = %s and qid =%s', (testid, num))
            if results > 0:
                data = cur.fetchone()
                del data['ans']
                cur.close()
                return json.dumps(data)
        elif flag == 'mark':
            qid = request.form['qid']
            ans = request.form['ans']
            cur = mysql.connection.cursor()
            results = cur.execute(
                'SELECT * from studentans where test_id =%s and qid = %s and email = %s', (testid, qid, session['email']))
            if results > 0:
                cur.execute('UPDATE studentans set ans = %s where test_id = %s and qid = %s and email = %s',
                            (ans, testid, qid, session['email']))
                mysql.connection.commit()
                cur.close()
            else:
                cur.execute('INSERT INTO studentans(email,test_id,qid,ans) values(%s,%s,%s,%s)',
                            (session['email'], testid, qid, ans,))
                mysql.connection.commit()
                cur.close()
            return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}
        elif flag == 'time':
            cur = mysql.connection.cursor()
            time_left = request.form['time']
            try:
                cur.execute('UPDATE teststatus set time_left=SEC_TO_TIME(%s) where test_id = %s and email = %s and completed=0',
                            (time_left, testid, session['email'],))
                mysql.connection.commit()
                cur.close()
                return json.dumps({'time': 'fired'})
            except:
                pass
        else:
            cur = mysql.connection.cursor()
            cur.execute('UPDATE teststatus set completed=1,time_left=sec_to_time(0) where test_id = %s and email = %s',
                        (testid, session['email'],))
            mysql.connection.commit()
            cur.close()
            flash("Exam submitted successfully", 'info')
            return json.dumps({'sql': 'fired'})


@app.route("/appear-test", methods=['GET', 'POST'])
@is_logged
def give_test():
    cur = mysql.connection.cursor()
    x = 1
    results = cur.execute('SELECT subject,topic,test_id,duration FROM testinfo WHERE (((%s,test_id) NOT IN (SELECT email,test_id FROM teststatus WHERE completed=%s)) AND testinfo.class_id=%s AND testinfo.start<NOW() AND testinfo.end>NOW())',
                          (session['email'], x, session['class_id'],))
    cresults = cur.fetchall()
    cur.close()
    return render_template("student_appear_test.html", cresults=cresults)


@app.route('/randomize', methods=['POST'])
def random_gen():
    if request.method == "POST":
        id = request.form['id']
        cur = mysql.connection.cursor()
        results = cur.execute(
            'SELECT count(*) from questions where test_id = %s', [id])
        if results > 0:
            data = cur.fetchone()
            total = data['count(*)']
            nos = list(range(1, int(total)+1))
            random.Random(id).shuffle(nos)
            cur.close()
            return json.dumps(nos)


@app.route('/video_feed', methods=['GET', 'POST'])
@is_logged
def video_feed():
    if (os.path.isfile("./models/yolov3.weights")):
        pass
    else:
        wget.download(
            "https://pjreddie.com/media/files/yolov3.weights", "./models/yolov3.weights")
    if (os.path.isfile("./models/shape_predictor_68_face_landmarks.dat")):
        pass
    else:
        wget.download("https://github.com/italojs/facial-landmarks-recognition/blob/master/shape_predictor_68_face_landmarks.dat?raw=true",
                      "./models/shape_predictor_68_face_landmarks.dat")
    if request.method == "POST":
        imgData = request.form['data[imgData]']
        testid = request.form['data[testid]']
        voice_db = request.form['data[voice_db]']
        yolov3_model_v3_path("./models/yolov3.weights")
        jpg_as_text = base64.b64encode(imgData.read()).decode('utf-8')
        proctorData = get_analysis(
            jpg_as_text, "./models/shape_predictor_68_face_landmarks.dat")
        mob_status = proctorData['mob_status']
        person_status = proctorData['person_status']
        cur = mysql.connection.cursor()
        results = cur.execute('INSERT INTO proctoring_log (email, name, test_id, voice_db, img_log, phone_detection, person_status) values(%s,%s,%s,%s,%s,%s,%s)', (dict(
            session)['email'], dict(session)['name'], testid, voice_db, jpg_as_text, mob_status, person_status))
        mysql.connection.commit()
        cur.close()
        if (results > 0):
            return "recorded image of video"
        else:
            return "error in video"


@app.route('/window_event', methods=['GET', 'POST'])
@is_logged
def window_event():
    if request.method == "POST":
        testid = request.form['testid']
        cur = mysql.connection.cursor()
        results = cur.execute('INSERT INTO window_estimation_log (email, test_id, name, window_event) values(%s,%s,%s,%s)', (dict(
            session)['email'], testid, dict(session)['name'], 1,))
        mysql.connection.commit()
        cur.close()
        if (results > 0):
            return "recorded window"
        else:
            return "error in window"


def totmarks(email, tests):
    cur = mysql.connection.cursor()
    for test in tests:
        testid = test['test_id']
        results = cur.execute(
            'select sum(marks) as totalmks from studentans s,questions q where s.email=%s and s.test_id=%s and s.qid=q.qid and s.test_id=q.test_id and s.ans=q.ans', (email, testid))
        results = cur.fetchone()
        if str(results['totalmks']) == 'None':
            results['totalmks'] = 0
        test['marks'] = results['totalmks']
        if "Decimal" not in str(results['totalmks']):
            mstr = str(results['totalmks']).replace('Decimal', '')
            results['totalmks'] = mstr
            test['marks'] = results['totalmks']
    return tests


def marks_calc(email, testid):
    cur = mysql.connection.cursor()
    results = cur.execute(
        'select sum(marks) as totalmks from studentans s,questions q where s.email=%s and s.test_id=%s and s.qid=q.qid and s.test_id=q.test_id and s.ans=q.ans', (email, testid))
    results = cur.fetchone()
    if str(results['totalmks']) == 'None':
        results['totalmks'] = 0
        return results['totalmks']
    if "Decimal" not in str(results['totalmks']):
        mstr = str(results['totalmks']).replace('Decimal', '')
        results['totalmks'] = mstr
        return results['totalmks']
    else:
        return results['totalmks']


def get_class_id(programme, branch, semester):
    cur = mysql.connection.cursor()
    cur.execute("SELECT class_id FROM class_master WHERE programme = %s AND branch = %s AND semester = %s",
                (programme, branch, semester,))
    res = cur.fetchone()
    return res['class_id']


@app.route('/<email>/tests-given')
@is_logged
def student_test_results(email):
    if email == session['email']:
        cur = mysql.connection.cursor()
        results = cur.execute(
            'select distinct(studentans.test_id),subject,topic from studentans,testinfo where studentans.email = %s and studentans.test_id=testinfo.test_id', [email])
        results = cur.fetchall()
        results = totmarks(email, results)
        return render_template('student_test_results.html', tests=results)
    else:
        msg = "'You are not authorized'"
        flash(msg, 'danger')
        return redirect(url_for('dashboard'))


@app.route('/<email>/tests-created/<testid>', methods=['POST', 'GET'])
@is_logged
def admin_student_results(email, testid):
    if email == session['email']:
        cur = mysql.connection.cursor()
        results = cur.execute(
            'select users.name as name,users.email as email,test_id from teststatus,users where test_id = %s and completed = 1 and teststatus.email=users.email ', [testid])
        results = cur.fetchall()
        final = []
        count = 1
        for user in results:
            score = marks_calc(user['email'], testid)
            user['srno'] = count
            user['marks'] = score
            final.append([count, user['name'], score])
            count += 1
        if request.method == 'GET':
            return render_template('admin_student_results.html', data=final)
        else:
            fields = ['Sr No', 'Name', 'Marks']
            with open('static/' + testid + '.csv', 'w') as f:
                writer = csv.writer(f)
                writer.writerow(fields)
                writer.writerows(final)
            return send_file('/static/' + testid + '.csv', as_attachment=True)


@app.route('/<email>/tests-created')
@is_logged
def admin_tests_created(email):
    if email == session['email']:
        cur = mysql.connection.cursor()
        results = cur.execute(
            'SELECT testinfo.email,testinfo.test_id,testinfo.subject,testinfo.topic,class_master.programme,class_master.branch,class_master.semester from testinfo INNER JOIN class_master ON testinfo.class_id = class_master.class_id WHERE email = %s', [email])
        if (results > 0):
            results = cur.fetchall()
            return render_template('admin_tests_created.html', tests=results)
        else:
            return render_template('admin_tests_created.html', tests=None)
    else:
        flash('You are not authorized', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/upcoming-tests')
@is_logged
def student_upcoming_tests():
    cur = mysql.connection.cursor()
    results = cur.execute(
        'SELECT testinfo.subject,testinfo.topic,testinfo.start,testinfo.end from testinfo INNER JOIN class_master ON testinfo.class_id = class_master.class_id WHERE testinfo.class_id = %s AND testinfo.start > NOW()', [session['class_id']])
    if (results > 0):
        results = cur.fetchall()
        return render_template('student_upcoming_tests.html', callresults=results)
    else:
        return render_template('student_upcoming_tests.html', callresults=None)


@app.route('/proctor_student_log_test', methods=['GET'])
@is_logged
def proctor_student_log_test():
    cur = mysql.connection.cursor()
    results = cur.execute(
        'SELECT test_id,subject,topic from testinfo where email = %s', (session['email'],))
    if results > 0:
        cresults = cur.fetchall()
        cur.close()
        return render_template("proctor_student_log_test.html", cresults=cresults)
    else:
        return render_template("proctor_student_log_test.html", cresults=None)


@app.route('/proctor_student_log_dashboard', methods=['GET', 'POST'])
@is_logged
def proctor_student_log_dashboard():
    if request.method == 'POST':
        tidoption = request.form['choosetid']
        cur = mysql.connection.cursor()
        cur.execute(
            'SELECT DISTINCT proctoring_log.email,proctoring_log.test_id,testinfo.subject,testinfo.topic from proctoring_log JOIN testinfo ON proctoring_log.test_id=testinfo.test_id where proctoring_log.test_id = %s', [tidoption])
        callresults = cur.fetchall()
        cur.close()
        return render_template("proctor_student_log_dashboard.html", callresults=callresults)


@app.route('/studentmonitoringstats/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def studentmonitoringstats(testid, email):
    return render_template("proctor_monitoring.html", testid=testid, email=email)


@app.route('/wineventstudentslogs/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def wineventstudentslogs(testid, email):
    cur = mysql.connection.cursor()
    cur.execute(
        'SELECT * from window_estimation_log where test_id = %s and email = %s', (testid, email))
    callresults = cur.fetchall()
    cur.close()
    return render_template("proctor_win_log.html", testid=testid, email=email, callresults=callresults)


@app.route('/proctor_mobile_log/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def proctor_mobile_log(testid, email):
    cur = mysql.connection.cursor()
    cur.execute(
        'SELECT * from proctoring_log where test_id = %s and email = %s and phone_detection = 1', (testid, email))
    callresults = cur.fetchall()
    cur.close()
    return render_template("proctor_mobile_log.html", testid=testid, email=email, callresults=callresults)


@app.route('/proctor_multiple_person_log/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def proctor_multiple_person_log(testid, email):
    cur = mysql.connection.cursor()
    cur.execute(
        'SELECT * from proctoring_log where test_id = %s and email = %s and person_status = 1', (testid, email))
    callresults = cur.fetchall()
    cur.close()
    return render_template("proctor_multiple_person_log.html", testid=testid, email=email, callresults=callresults)


@app.route('/proctor_audio_log/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def proctor_audio_log(testid, email):
    cur = mysql.connection.cursor()
    cur.execute(
        'SELECT * from proctoring_log where test_id = %s and email = %s', (testid, email))
    callresults = cur.fetchall()
    cur.close()
    return render_template("proctor_audio_log.html", testid=testid, email=email, callresults=callresults)


if __name__ == "__main__":
    app.run(debug=True, port=os.getenv("PORT", default=5000), host='0.0.0.0')
