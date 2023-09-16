######### LIBRARIES #########

# Standard Python Libraries
import base64
import hashlib
import os
import re
import random
import json
import csv
import smtplib
from datetime import timedelta, datetime

# Third-party Libraries
import cv2
import wget
from flask import (
    Flask, request, render_template, flash, redirect, url_for,
    session, logging, send_file, render_template_string
)
from flask_mysqldb import MySQL
import MySQLdb.cursors
import numpy as np
from wtforms import Form, IntegerField, SelectField, StringField, TextAreaField, PasswordField, validators
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from functools import wraps
from werkzeug.utils import secure_filename
from coolname import generate_slug
from flask_mobility import Mobility
from flask_cors import CORS, cross_origin
from dotenv import load_dotenv
from flask_session import Session
from wtforms_components import TimeField
from wtforms.fields import DateField
from wtforms.validators import ValidationError

# Custom Modules
from proctoring.proctoring import get_analysis, yolov3_model_v3_path
from deepface import DeepFace
import math

######### APP CONFIGURATION #########

# Load environment variables from .env file
load_dotenv()

# Create a Flask app
app = Flask(__name__)

# MySQL Database Configuration
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT'))
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Session Configuration
app.config['SESSION_COOKIE_SAMESITE'] = "None"
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# Template and Secret Key Configuration
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# CORS Configuration
app.config['CORS_HEADERS'] = 'Content-Type'

# Initialize CORS, Session, and Mobility extensions
CORS(app)
Session(app)
Mobility(app)

# Initialize MySQL database connection
mysql = MySQL(app)

######### REGISTRATION & AUTHENTICATION #########

# LOGGED IN CHECK
def is_logged(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if request.MOBILE:
            return render_template('mobile.html')
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('login_email'))
    return wrap

# LOGOUT USER
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_email'))


# USER REGISTRATION
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


# EMAIL LOGIN
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

# PHONE LOGIN
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

# FACE VERIFICATION
def face_verify(storedImage, inputImage):
    # Convert base64-encoded images to numpy arrays
    nparr1 = np.frombuffer(base64.b64decode(storedImage), np.uint8)
    nparr2 = np.frombuffer(base64.b64decode(inputImage), np.uint8)

    # Decode images and convert to grayscale
    image1 = cv2.imdecode(nparr1, cv2.COLOR_BGR2GRAY)
    image2 = cv2.imdecode(nparr2, cv2.COLOR_BGR2GRAY)

    # Perform face verification using DeepFace
    img_result = DeepFace.verify(image1, image2, enforce_detection=False)
    return img_result


######### DASHBOARD #########

@app.route('/')
@app.route('/dashboard')
@is_logged
def dashboard():
    role = session.get('role', None)
    isActive = session.get('isActive', None)
    
    # Check if the user's account is disabled
    if isActive == 'N':
        return redirect(url_for('login_email', msg='⚠️ Your account is currently disabled !'))
    
    # Determine the user's role and render the appropriate dashboard
    if role == 'T':
        return render_template('admin_dashboard.html')
    elif role == 'S':
        return render_template('student_dashboard.html')
    else:
        return redirect(url_for('login_email'))

######### TEST CREATION FORM #########

# Define a FlaskForm class for handling file uploads and related information.
class UploadForm(FlaskForm):
    # Define fields for the form with labels and input types.
    subject = StringField('Subject')
    topic = StringField('Topic')
    
    # Define a SelectField for 'Programme' with predefined choices.
    programme = SelectField('Programme', choices=[
        ('BTech', 'B.Tech'), ('MTech', 'M.Tech')])
    
    # Define a SelectField for 'Branch' with predefined choices.
    branch = SelectField('Branch', choices=[
        ('CSE', 'CSE'), ('ECE', 'ECE'), ('DSAI', 'DSAI')])
    
    # Define a SelectField for 'Semester' with predefined choices.
    semester = SelectField('Semester', choices=[
        (1, '1'), (2, '2'), (3, '3'), (4, '4'),
        (5, '5'), (6, '6'), (7, '7'), (8, '8')])
    
    # Define fields for date and time, with default values based on the current time.
    start_date = DateField('Start Date')
    start_time = TimeField(
        'Start Time', default=datetime.utcnow() + timedelta(hours=5.5))
    end_date = DateField('End Date')
    end_time = TimeField(
        'End Time', default=datetime.utcnow() + timedelta(hours=5.5))
    
    # Define an IntegerField for duration (in minutes).
    duration = IntegerField('Duration (in mins)')

    # Define a custom validation function for 'end_date' to check it against 'start_date'.
    def validate_end_date(form, field):
        if field.data < form.start_date.data:
            raise ValidationError(
                "End date must not be earlier than the start date!")

    # Define a custom validation function for 'end_time' to check it against 'start_time'.
    def validate_end_time(form, field):
        start_date_time = datetime.strptime(str(form.start_date.data) + " " + str(
            form.start_time.data), "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
        end_date_time = datetime.strptime(str(form.end_date.data) + " " + str(
            field.data), "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
        if start_date_time >= end_date_time:
            raise ValidationError(
                "Please enter a valid end date and time!")

    # Define a custom validation function for 'start_date' to check it against the current time.
    def validate_start_date(form, field):
        if datetime.strptime(str(form.start_date.data) + " " + str(form.start_time.data), "%Y-%m-%d %H:%M:%S") < datetime.now():
            raise ValidationError(
                "Start date and time must not be earlier than the current time!")

# CREATE TEST
@app.route('/create-test', methods=['GET', 'POST'])
@is_logged
def admin_create_test():
    form = UploadForm()
    if request.method == 'POST':
        # Generate a unique test ID.
        test_id = generate_slug(2)

        cur = mysql.connection.cursor()

        # Extract form data for test details.
        start_date = form.start_date.data
        end_date = form.end_date.data
        start_time = form.start_time.data
        end_time = form.end_time.data
        start_date_time = str(start_date) + " " + str(start_time)
        end_date_time = str(end_date) + " " + str(end_time)
        duration = int(form.duration.data) * 60
        subject = form.subject.data
        topic = form.topic.data
        programme = form.programme.data
        branch = form.branch.data
        semester = form.semester.data
        
        # Get the class ID for the given program, branch, and semester.
        class_id = get_class_id(programme, branch, semester)
        
        # Execute a SQL INSERT statement to add test information to the database.
        cur.execute('INSERT INTO testinfo (email, test_id, start, end, duration, subject, topic, class_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', (
            dict(session)['email'], test_id, start_date_time, end_date_time, duration, subject, topic, class_id))
        
        # Commit the changes to the database and close the cursor.
        cur.connection.commit()
        cur.close()
        
        # Store the test ID in the session for future reference.
        session['testid'] = test_id
        
        # Redirect the user to another route ('addques') with appropriate parameters.
        return redirect(url_for('addques', testid=test_id, newq=1))
    
    # If the request method is GET, render the 'admin_create_test.html' template.
    return render_template('admin_create_test.html', form=form)

######### MODIFY TEST #########


# DISPLAY QUESTIONS 
@app.route('/admin_display_questions', methods=['GET', 'POST'])
@is_logged
def admin_display_questions():
    if request.method == 'POST':
        session['testid'] = request.form['choosetid']
    
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM questions WHERE test_id = %s', [session['testid']])
    callresults = cur.fetchall()
    cur.close()
    newq = len(callresults) + 1
    
    return render_template("admin_display_questions.html", callresults=callresults, newq=newq, testid=session['testid'])

# EDIT QUESTIONS
@app.route('/admin_edit_questions', methods=['GET'])
@is_logged 
def admin_edit_questions():
    cur = mysql.connection.cursor()
    
    # Execute a SQL query to select test information for the logged-in user's email.
    results = cur.execute(
        'SELECT test_id, subject, topic FROM testinfo WHERE email = %s', [session['email']])
    
    if results > 0:
        cresults = cur.fetchall()
        cur.close()
        
        # Render the 'admin_edit_questions.html' template with the fetched results.
        return render_template("admin_edit_questions.html", cresults=cresults)
    else:
        # Render the 'admin_edit_questions.html' template with no results if there are no tests.
        return render_template("admin_edit_questions.html", cresults=None)


# DELETE QUESTION
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


# NEW QUESTION
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


# UPDATE QUESTION
@app.route('/update/<testid>/<qid>', methods=['GET', 'POST'])
@is_logged
def update_quiz(testid, qid):
    if request.method == 'GET':
        # Get the current question details for editing.
        cur = mysql.connection.cursor()
        cur.execute(
            'SELECT * FROM questions WHERE test_id = %s AND qid = %s', (testid, qid))
        uresults = cur.fetchall()
        cur.close()
        return render_template("admin_update_question.html", uresults=uresults)

    if request.method == 'POST':
        # Update the question details.
        ques = request.form['ques']
        ao = request.form['ao']
        bo = request.form['bo']
        co = request.form['co']
        do = request.form['do']
        anso = request.form['anso']
        
        cur = mysql.connection.cursor()
        cur.execute('UPDATE questions SET q = %s, a = %s, b = %s, c = %s, d = %s, ans = %s WHERE test_id = %s AND qid = %s',
                    (ques, ao, bo, co, do, anso, testid, qid))
        cur.connection.commit()
        cur.close()
        
        msg = "Updated successfully"
        flash(msg, 'success')
        return redirect(url_for('admin_display_questions', success=msg))

    else:
        msg = "ERROR OCCURRED."
        flash(msg, 'error')
        return redirect(url_for('admin_display_questions', error=msg))


######### TEST #########


# STUDENT TEST SELECTION
@app.route("/appear-test", methods=['GET', 'POST'])
@is_logged
def give_test():
    # Create a cursor to interact with the database.
    cur = mysql.connection.cursor()
    
    # Set a variable to check for test completion status (1 means completed).
    x = 1
    
    # Execute a SQL query to select tests that are available for the student to take.
    results = cur.execute(
        'SELECT subject, topic, test_id, duration FROM testinfo WHERE (((%s, test_id) NOT IN (SELECT email, test_id FROM teststatus WHERE completed = %s)) AND testinfo.class_id = %s AND testinfo.start < NOW() AND testinfo.end > NOW())',
        (session['email'], x, session['class_id'],))
    
    # Fetch the results of the query.
    cresults = cur.fetchall()
    
    # Close the database cursor.
    cur.close()
    
    # Render the student_appear_test.html template with the fetched test information.
    return render_template("student_appear_test.html", cresults=cresults)

# INTERMEDIATE PAGE FOR STARTING/CONTINUING A TEST
@app.route('/intermediate', methods=['GET', 'POST'])
@is_logged
def intermediate():
    # Declare global variables for test duration, marked answers, subject, and topic.
    global duration, marked_ans, subject, topic

    if request.method == 'POST':
        # Extract the values from the form submitted by the user.
        values = request.form['chooseexam']
        test_id, subject, topic, duration = values.split(',')
        
        # Get the user's face image data.
        imgdata1 = request.form['image_hidden']
        
        # Create a cursor to interact with the database.
        cur1 = mysql.connection.cursor()
        
        # Check if the user has a stored face image.
        results1 = cur1.execute(
            'SELECT user_image FROM users WHERE email = %s', (session['email'],))

        if results1 > 0:
            cresults = cur1.fetchone()
            imgdata2 = cresults['user_image']
            
            # Verify the user's face identity.
            img_result = face_verify(imgdata1, imgdata2)
            
            if img_result["verified"] == True:
                # Check if the user has a previously saved test status.
                time = cur1.execute(
                    'SELECT time_to_sec(time_left) AS time_left, completed FROM teststatus WHERE email = %s AND test_id = %s',
                    (session['email'], test_id,))
                
                if time > 0:
                    time = cur1.fetchone()
                    is_completed = time['completed']
                    
                    if is_completed == 0:
                        time_left = time['time_left']
                        
                        # Update the test duration if the remaining time is less than the default duration.
                        if time_left <= duration:
                            duration = time_left
                
                # Check if the user has marked answers for the test.
                ans = cur1.execute(
                    'SELECT qid, ans FROM studentans WHERE email = %s AND test_id = %s', (session['email'], test_id,))
                marked_ans = {}

                if ans > 0:
                    ans = cur1.fetchall()
                    
                    # Create a dictionary of marked answers.
                    for row in ans:
                        qiddb = "" + row['qid']
                        marked_ans[qiddb] = row['ans']
                    
                    # Convert the dictionary to a JSON string.
                    marked_ans = json.dumps(marked_ans)
                
                # Check if the user has a test status record, and if not, create one.
                status = cur1.execute(
                    'SELECT * FROM teststatus WHERE email = %s AND test_id = %s', (session['email'], test_id,))
                
                if not status:
                    cur1.execute(
                        'INSERT INTO teststatus (email, test_id, time_left) VALUES (%s, %s, %s)',
                        (session['email'], test_id, duration))
                    mysql.connection.commit()

                # Redirect the user to the test page.
                return redirect(url_for('test', testid=test_id))
            else:
                # If face identity could not be verified, display an error message.
                msg = '⚠️ Face identity could not be verified!'
                flash(msg, 'error')
                return redirect(url_for('give_test', error=msg))


# APPEAR FOR TEST
@app.route('/appear-test/<testid>', methods=['GET', 'POST'])
@is_logged
def test(testid):
    # Declare global variables for test duration, marked answers, subject, and topic.
    global duration, marked_ans, subject, topic

    if request.method == 'GET':
        try:
            # Initialize data dictionary for rendering the quiz page.
            data = {'duration': duration, 'marks': '', 'q': '', 'a': '', 'b': '', 'c': '', 'd': ''}
            
            # Render the quiz page with provided data.
            return render_template('quiz.html', **data, answers=marked_ans, subject=subject, topic=topic, tid=testid)
        except:
            # Redirect to the test selection page if there's an error.
            return redirect(url_for('give_test'))

    if request.method == 'POST':
        cur = mysql.connection.cursor()
        flag = request.form['flag']

        if flag == 'get':
            # Handle a GET request to fetch question details.
            num = request.form['no']
            results = cur.execute(
                'SELECT test_id, qid, q, a, b, c, d, ans, marks FROM questions WHERE test_id = %s AND qid = %s', (testid, num))
            if results > 0:
                data = cur.fetchone()
                del data['ans']
                cur.close()
                return json.dumps(data)
        elif flag == 'mark':
            # Handle a flag 'mark' request to mark an answer.
            qid = request.form['qid']
            ans = request.form['ans']
            results = cur.execute(
                'SELECT * FROM studentans WHERE test_id = %s AND qid = %s AND email = %s', (testid, qid, session['email']))
            if results > 0:
                cur.execute('UPDATE studentans SET ans = %s WHERE test_id = %s AND qid = %s AND email = %s',
                            (ans, testid, qid, session['email']))
                mysql.connection.commit()
                cur.close()
            else:
                cur.execute('INSERT INTO studentans(email, test_id, qid, ans) VALUES (%s, %s, %s, %s)',
                            (session['email'], testid, qid, ans,))
                mysql.connection.commit()
                cur.close()
            return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}
        elif flag == 'time':
            # Handle a flag 'time' request to update the remaining time.
            cur = mysql.connection.cursor()
            time_left = request.form['time']
            try:
                cur.execute('UPDATE teststatus SET time_left = SEC_TO_TIME(%s) WHERE test_id = %s AND email = %s AND completed = 0',
                            (time_left, testid, session['email'],))
                mysql.connection.commit()
                cur.close()
                return json.dumps({'time': 'fired'})
            except:
                pass
        else:
            # Handle other cases (e.g., submitting the exam).
            cur = mysql.connection.cursor()
            cur.execute('UPDATE teststatus SET completed = 1, time_left = SEC_TO_TIME(0) WHERE test_id = %s AND email = %s',
                        (testid, session['email'],))
            mysql.connection.commit()
            cur.close()
            flash("Exam submitted successfully", 'info')
            return json.dumps({'sql': 'fired'})



# RANDOMIZE QUESTIONS
@app.route('/randomize', methods=['POST'])
def random_gen():
    # Check if the request method is POST
    if request.method == "POST":
        # Get the 'id' parameter from the form data
        id = request.form['id']
        
        # Create a cursor for the MySQL database connection
        cur = mysql.connection.cursor()
        
        # Execute a SQL query to get the count of questions for the specified test_id
        results = cur.execute('SELECT count(*) from questions where test_id = %s', [id])
        
        # Check if there are any results returned from the query
        if results > 0:
            # Fetch the data (count) from the query result
            data = cur.fetchone()
            
            # Get the total count of questions
            total = data['count(*)']
            
            # Generate a list of numbers from 1 to the total count
            nos = list(range(1, int(total)+1))
            
            # Shuffle the list of numbers using a random seed based on the 'id'
            random.Random(id).shuffle(nos)

            cur.close()
            
            # Return the shuffled list of numbers as JSON response
            return json.dumps(nos)
        
# MARKS FOR SPECIFIC TEST
def marks_calc(email, testid):
    # Create a cursor for the MySQL database connection
    cur = mysql.connection.cursor()
    
    # Execute a SQL query to calculate the sum of marks for a specific test and email
    results = cur.execute(
        'SELECT SUM(marks) AS totalmks FROM studentans s, questions q WHERE s.email = %s AND s.test_id = %s AND s.qid = q.qid AND s.test_id = q.test_id AND s.ans = q.ans',
        (email, testid))
    
    # Fetch the result of the query
    results = cur.fetchone()
    
    # Check if the total marks result is 'None' and set it to 0 if so
    if str(results['totalmks']) == 'None':
        results['totalmks'] = 0
        return results['totalmks']
    
    # Check if the total marks is not a Decimal
    if "Decimal" not in str(results['totalmks']):
        # Convert the total marks to a string and remove 'Decimal' if present
        mstr = str(results['totalmks']).replace('Decimal', '')
        results['totalmks'] = mstr
    
    # Return the calculated total marks for the specific test
    return results['totalmks']


# TOTAL MARKS FOR ALL TESTS
def totmarks(email, tests):
    # Create a cursor for the MySQL database connection
    cur = mysql.connection.cursor()
    
    # Iterate through the list of tests
    for test in tests:
        testid = test['test_id']
        
        # Execute a SQL query to calculate the sum of marks for a specific test and email
        results = cur.execute(
            'SELECT SUM(marks) AS totalmks FROM studentans s, questions q WHERE s.email = %s AND s.test_id = %s AND s.qid = q.qid AND s.test_id = q.test_id AND s.ans = q.ans',
            (email, testid))
        
        # Fetch the result of the query
        results = cur.fetchone()
        
        # Check if the total marks result is 'None' and set it to 0 if so
        if str(results['totalmks']) == 'None':
            results['totalmks'] = 0
        
        # Update the 'marks' field in the test with the calculated total marks
        test['marks'] = results['totalmks']
        
        # Check if the total marks is not a Decimal
        if "Decimal" not in str(results['totalmks']):
            # Convert the total marks to a string and remove 'Decimal' if present
            mstr = str(results['totalmks']).replace('Decimal', '')
            results['totalmks'] = mstr
            test['marks'] = results['totalmks']
    
    # Return the updated list of tests
    return tests

# GET CLASS ID
def get_class_id(programme, branch, semester):
    cur = mysql.connection.cursor()
    cur.execute("SELECT class_id FROM class_master WHERE programme = %s AND branch = %s AND semester = %s",
                (programme, branch, semester,))
    res = cur.fetchone()
    return res['class_id']


# DISPLAY TEST RESULTS TO STUDENT
@app.route('/<email>/tests-given')
@is_logged
def student_test_results(email):
    # Check if the provided email matches the session email
    if email == session['email']:
        # Create a cursor for the MySQL database connection
        cur = mysql.connection.cursor()
        
        # Execute SQL query to fetch distinct test information for the given student
        results = cur.execute(
            'SELECT DISTINCT(studentans.test_id), subject, topic FROM studentans, testinfo WHERE studentans.email = %s AND studentans.test_id = testinfo.test_id',
            [email])
        
        # Check if test results were found
        if (results > 0):
            results = cur.fetchall()
            
            # Calculate and update total marks for the tests
            results = totmarks(email, results)
            
            # Render the template with test results
            return render_template('student_test_results.html', tests=results)
        else:
            # Render the template with no test results
            return render_template('student_test_results.html', tests=None)
    else:
        # If the provided email does not match the session email, display an error message
        msg = "'You are not authorized'"
        flash(msg, 'danger')
        return redirect(url_for('dashboard'))


# GENERTE TEST RESULTS IN CSV FORMAT
@app.route('/<email>/tests-created/<testid>', methods=['POST', 'GET'])
@is_logged
def admin_student_results(email, testid):
    # Check if the provided email matches the session email
    if email == session['email']:
        # Create a cursor for the MySQL database connection
        cur = mysql.connection.cursor()
        
        # Execute SQL query to fetch students who completed the specified test
        results = cur.execute(
            'SELECT users.name AS name, users.email AS email, test_id FROM teststatus, users WHERE test_id = %s AND completed = 1 AND teststatus.email = users.email',
            [testid])
        
        # Fetch the results
        results = cur.fetchall()
        
        final = []
        count = 1
        
        # Iterate through the results and calculate each student's score
        for user in results:
            score = marks_calc(user['email'], testid)
            user['srno'] = count
            user['marks'] = score
            final.append([count, user['name'], score])
            count += 1
        
        # Handle GET request to display student results
        if request.method == 'GET':
            return render_template('admin_student_results.html', data=final)
        # Handle POST request to export student results as a CSV file
        else:
            fields = ['Sr No', 'Name', 'Marks']
            with open('static/' + testid + '.csv', 'w') as f:
                writer = csv.writer(f)
                writer.writerow(fields)
                writer.writerows(final)
            
            # Send the CSV file as an attachment
            return send_file('/static/' + testid + '.csv', as_attachment=True)


# DISPLAY TESTS CREATED BY ADMIN
@app.route('/<email>/tests-created')
@is_logged
def admin_tests_created(email):
    # Check if the provided email matches the session email
    if email == session['email']:
        # Create a cursor for the MySQL database connection
        cur = mysql.connection.cursor()
        
        # Execute SQL query to fetch test information created by the admin
        results = cur.execute(
            'SELECT testinfo.email, testinfo.test_id, testinfo.subject, testinfo.topic, class_master.programme, class_master.branch, class_master.semester FROM testinfo INNER JOIN class_master ON testinfo.class_id = class_master.class_id WHERE email = %s',
            [email])
        
        # Check if any tests were found
        if (results > 0):
            results = cur.fetchall()
            
            # Render the template with the tests created by the admin
            return render_template('admin_tests_created.html', tests=results)
        else:
            # Render the template with no tests found
            return render_template('admin_tests_created.html', tests=None)
    else:
        # If the provided email does not match the session email, display an error message
        flash('You are not authorized!', 'danger')
        return redirect(url_for('dashboard'))


# UPCOMING STUDENT TESTS
@app.route('/upcoming-tests')
@is_logged
def student_upcoming_tests():
    # Create a cursor for the MySQL database connection
    cur = mysql.connection.cursor()
    
    # Execute SQL query to fetch upcoming test information for the student's class
    results = cur.execute(
        'SELECT testinfo.subject, testinfo.topic, testinfo.start, testinfo.end FROM testinfo INNER JOIN class_master ON testinfo.class_id = class_master.class_id WHERE testinfo.class_id = %s AND testinfo.start > NOW()',
        [session['class_id']])
    
    # Check if any upcoming tests were found
    if (results > 0):
        results = cur.fetchall()
        
        # Render the template with upcoming test information
        return render_template('student_upcoming_tests.html', callresults=results)
    else:
        # Render the template with a message if no upcoming tests are found
        return render_template('student_upcoming_tests.html', callresults=None)


######### PROCTORING SYSTEM #########

# VIDEO FEED
@app.route('/video_feed', methods=['GET', 'POST'])
@is_logged
def video_feed():
    # Check if the YOLOv3 weights file exists; if not, download it
    if (os.path.isfile("./models/yolov3.weights")):
        pass
    else:
        wget.download(
            "https://pjreddie.com/media/files/yolov3.weights", "./models/yolov3.weights")
    
    # Check if the face landmarks model file exists; if not, download it
    if (os.path.isfile("./models/shape_predictor_68_face_landmarks.dat")):
        pass
    else:
        wget.download(
            "https://github.com/italojs/facial-landmarks-recognition/blob/master/shape_predictor_68_face_landmarks.dat?raw=true",
            "./models/shape_predictor_68_face_landmarks.dat")
    
    # Check if the request method is POST
    if request.method == "POST":
        # Get data from the POST request
        imgData = request.form['data[imgData]']
        testid = request.form['data[testid]']
        voice_db = request.form['data[voice_db]']
        
        # Load the YOLOv3 model with the downloaded weights
        yolov3_model_v3_path("./models/yolov3.weights")
        
        # Encode the image data as base64
        jpg_as_text = base64.b64encode(imgData.read()).decode('utf-8')
        
        # Get analysis data for the image using face landmarks model
        proctorData = get_analysis(
            jpg_as_text, "./models/shape_predictor_68_face_landmarks.dat")
        
        # Extract mobile and person status from proctoring data
        mob_status = proctorData['mob_status']
        person_status = proctorData['person_status']

        cur = mysql.connection.cursor()
        
        # Insert proctoring data into the database
        results = cur.execute('INSERT INTO proctoring_log (email, name, test_id, voice_db, img_log, phone_detection, person_status) values(%s,%s,%s,%s,%s,%s,%s)', (dict(
            session)['email'], dict(session)['name'], testid, voice_db, jpg_as_text, mob_status, person_status))
        
        # Commit the database transaction and close the cursor
        mysql.connection.commit()
        cur.close()
        
        # Check if the insertion was successful and return a response
        if (results > 0):
            return "recorded image of video"
        else:
            return "error in video"


# WINDOW SWITCHING EVENTS
@app.route('/window_event', methods=['GET', 'POST'])
@is_logged
def window_event():
    # Check if the request method is POST
    if request.method == "POST":
        # Get the 'testid' parameter from the form data
        testid = request.form['testid']
        
        # Create a cursor for the MySQL database connection
        cur = mysql.connection.cursor()
        
        # Insert a window event record into the database
        # Include the user's email, test ID, user's name, and a value of 1 for window_event
        results = cur.execute(
            'INSERT INTO window_estimation_log (email, test_id, name, window_event) VALUES (%s, %s, %s, %s)',
            (dict(session)['email'], testid, dict(session)['name'], 1,))
        
        # Commit the database transaction
        mysql.connection.commit()
        
        # Close the database cursor
        cur.close()
        
        # Check if the insertion was successful
        if results > 0:
            # Return a success message if recorded
            return "Window event recorded successfully"
        else:
            # Return an error message if there was an issue
            return "Error in recording window event"


# SELECT TEST FOR PROCTORING LOGS
@app.route('/proctor_student_log_test', methods=['GET'])
@is_logged
def proctor_student_log_test():
    # Create a cursor for the MySQL database connection
    cur = mysql.connection.cursor()
    
    # Execute SQL query to fetch test information for the student's tests
    results = cur.execute(
        'SELECT test_id, subject, topic FROM testinfo WHERE email = %s', (session['email'],))
    
    # Check if any tests were found
    if results > 0:
        cresults = cur.fetchall()
        cur.close()
        
        # Render the template with a list of available tests
        return render_template("proctor_student_log_test.html", cresults=cresults)
    else:
        # Render the template with a message if no tests are found
        return render_template("proctor_student_log_test.html", cresults=None)


# PROCTORING LOG DASHBOARD FOR SPECIFIC TEST
@app.route('/proctor_student_log_dashboard', methods=['GET', 'POST'])
@is_logged
def proctor_student_log_dashboard():
    if request.method == 'POST':
        tidoption = request.form['choosetid']
        
        # Create a cursor for the MySQL database connection
        cur = mysql.connection.cursor()
        
        # Execute SQL query to fetch proctoring logs for the selected test
        cur.execute(
            'SELECT DISTINCT proctoring_log.email, proctoring_log.test_id, testinfo.subject, testinfo.topic FROM proctoring_log JOIN testinfo ON proctoring_log.test_id = testinfo.test_id WHERE proctoring_log.test_id = %s', [tidoption])
        
        # Fetch the results
        callresults = cur.fetchall()
        cur.close()
        
        # Render the template with proctoring logs for the selected test
        return render_template("proctor_student_log_dashboard.html", callresults=callresults)



# STUDENT MONITORING STATISTICS
@app.route('/studentmonitoringstats/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def studentmonitoringstats(testid, email):
    # Render the 'proctor_monitoring.html' template with test ID and email
    return render_template("proctor_monitoring.html", testid=testid, email=email)


# DISPLAY WINDOW EVENT LOGS
@app.route('/wineventstudentslogs/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def wineventstudentslogs(testid, email):
    # Create a cursor for the MySQL database connection
    cur = mysql.connection.cursor()
    
    # Execute SQL query to fetch window event logs for the specified test and student
    cur.execute(
        'SELECT * from window_estimation_log where test_id = %s and email = %s', (testid, email))
    
    # Fetch the results
    callresults = cur.fetchall()
    cur.close()
    
    # Render the 'proctor_win_log.html' template with test ID, email, and window event logs
    return render_template("proctor_win_log.html", testid=testid, email=email, callresults=callresults)


# DISPLAY MOBILE DETECTION LOGS
@app.route('/proctor_mobile_log/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def proctor_mobile_log(testid, email):
    # Create a cursor for the MySQL database connection
    cur = mysql.connection.cursor()
    
    # Execute SQL query to fetch mobile detection logs for the specified test and student
    cur.execute(
        'SELECT * from proctoring_log where test_id = %s and email = %s and phone_detection = 1', (testid, email))
    
    # Fetch the results
    callresults = cur.fetchall()
    cur.close()
    
    # Render the 'proctor_mobile_log.html' template with test ID, email, and mobile detection logs
    return render_template("proctor_mobile_log.html", testid=testid, email=email, callresults=callresults)


# DISPLAY MULTIPLE PERSON DETECTION LOGS
@app.route('/proctor_multiple_person_log/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def proctor_multiple_person_log(testid, email):
    # Create a cursor for the MySQL database connection
    cur = mysql.connection.cursor()
    
    # Execute SQL query to fetch multiple person detection logs for the specified test and student
    cur.execute(
        'SELECT * from proctoring_log where test_id = %s and email = %s and person_status = 1', (testid, email))
    
    # Fetch the results
    callresults = cur.fetchall()
    cur.close()
    
    # Render the 'proctor_multiple_person_log.html' template with test ID, email, and multiple person detection logs
    return render_template("proctor_multiple_person_log.html", testid=testid, email=email, callresults=callresults)


# DISPLAY AUDIO DETECTION LOGS
@app.route('/proctor_audio_log/<testid>/<email>', methods=['GET', 'POST'])
@is_logged
def proctor_audio_log(testid, email):
    # Create a cursor for the MySQL database connection
    cur = mysql.connection.cursor()
    
    # Execute SQL query to fetch audio detection logs for the specified test and student
    cur.execute(
        'SELECT * from proctoring_log where test_id = %s and email = %s', (testid, email))
    
    # Fetch the results
    callresults = cur.fetchall()
    cur.close()
    
    # Render the 'proctor_audio_log.html' template with test ID, email, and audio detection logs
    return render_template("proctor_audio_log.html", testid=testid, email=email, callresults=callresults)


# Start the Flask application server
if __name__ == "__main__":
    app.run(debug=True, port=os.getenv("PORT", default=5000), host='0.0.0.0')
