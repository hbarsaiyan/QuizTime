from flask import Flask, redirect, render_template, request, url_for, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
import hashlib

app = Flask(__name__)

# Application Security Key for extra protection
app.secret_key = 'Vo8sS4FEKXgnkj'

# Enter your database connection details below
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = ''

# Intialize MySQL
mysql = MySQL(app)

if __name__ == "__main__":
    app.run()

@app.route('/')
@app.route('/login_email', methods=['GET', 'POST'])
def index():
    return render_template('index.html')