#Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect
import pymysql.cursors
import hashlib
import os
import time

SALT = 'cs3083'

#Initialize the app from Flask
app = Flask(__name__)

IMAGES_DIR = os.path.join(os.getcwd(), "images")

#Configure MySQL
conn = pymysql.connect(host='localhost',
                       port = 8889,
                       user='root',
                       password='root',
                       db='finsta',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)

#Define a route to hello function
@app.route('/')
def hello():
    return render_template('index.html')

#Define route for login
@app.route('/login')
def login():
    return render_template('login.html')

#Define route for register
@app.route('/register')
def register():
    return render_template('register.html')

#Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    #grabs information from the forms
    #username = request.form['username']
    #password = request.form['password']
    
    username = request.form['username']
    password = request.form['password'] + SALT
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM person WHERE username = %s and password = %s'
    cursor.execute(query, (username, hashed_password))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if(data):
        #creates a session for the the user
        #session is a built in
        session['username'] = username
        return redirect(url_for('home'))
    else:
        #returns an error message to the html page
        error = 'Invalid login or username'
        return render_template('login.html', error=error)

#Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password'] + SALT
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    firstName = request.form['fname']
    lastName = request.form['lname']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM person WHERE username = %s'
    cursor.execute(query, (username))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    error = None
    if(data):
        #If the previous query returns data, then user exists
        error = 'This user already exists'
        return render_template('register.html', error = error)
    else:
        ins = 'INSERT INTO person (username, password, firstName, lastName) VALUES(%s, %s, %s, %s)'
        cursor.execute(ins, (username, hashed_password, firstName, lastName))
        conn.commit()
        cursor.close()
        return render_template('index.html')


@app.route('/home')
def home():
    user = session['username']
#    cursor = conn.cursor();
#    query = 'SELECT ts, blog_post FROM blog WHERE username = %s ORDER BY ts DESC'
#    cursor.execute(query, (user))
#    data = cursor.fetchall()
#    cursor.close()
    return render_template('home.html', username=user)
        #,posts=data)

# returns list of names of groups owned by 'username'
def getGroups(username):
    groupNames = []
    cursor = conn.cursor()
    ins = 'SELECT groupName FROM friendgroup WHERE groupOwner = %s'
    cursor.execute(ins, (username))
    data = cursor.fetchall()
    for i in range(len(data)):
        groupNames.append(data[i].get('groupName'))
    conn.commit()
    cursor.close()
    return groupNames

@app.route('/upload', methods=['GET','POST'])
def upload_image():
    username = session['username']
    userGroups = getGroups(username)
    if request.method == 'POST':
        image_file = request.files.get('imageToUpload', '')
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        caption = request.form['caption']
        try:
            if request.form['allFollowers']:
                allFollowers = True
        except:
            allFollowers = False
        cursor = conn.cursor()
        ins = 'INSERT INTO Photo(postingdate, filePath,allFollowers, caption, photoPoster) VALUES (%s, %s, %s, %s , %s)'
        cursor.execute(ins, (time.strftime('%Y-%m-%d %H:%M:%S'), filepath, allFollowers, caption, username))
        conn.commit()
        cursor.close()
        if (allFollowers):
            message = 'Image has been successfully uploaded and shared with all of your followers.'
            return render_template("upload.html", message=message, groups = userGroups)
        else:
            cursor = conn.cursor
            groups = request.form.getlist("groups")
            for group in groups:
                ins = 'INSERT INTO sharedwith(groupOwner, groupName, photoID) VALUES (%s, %s, LAST_INSERT_ID())'
                cursor.execute(ins, (username, group))
            message = 'Image has been successfully uploaded and shared with the groups selected.'
            conn.commit()
            cursor.close()
            return render_template('upload.html', message=message, groups = userGroups)
    return render_template('upload.html', groups = userGroups)
        
#@app.route('/post', methods=['GET', 'POST'])
#def post():
#    username = session['username']
#    cursor = conn.cursor();
#    blog = request.form['blog']
#    query = 'INSERT INTO blog (blog_post, username) VALUES(%s, %s)'
#    cursor.execute(query, (blog, username))
#    conn.commit()
#    cursor.close()
#    return redirect(url_for('home'))
#
#@app.route('/select_blogger')
#def select_blogger():
#    #check that user is logged in
#    #username = session['username']
#    #should throw exception if username not found
#
#    cursor = conn.cursor();
#    query = 'SELECT DISTINCT username FROM blog'
#    cursor.execute(query)
#    data = cursor.fetchall()
#    cursor.close()
#    return render_template('select_blogger.html', user_list=data)
#
#@app.route('/show_posts', methods=["GET", "POST"])
#def show_posts():
#    poster = request.args['poster']
#    cursor = conn.cursor();
#    query = 'SELECT ts, blog_post FROM blog WHERE username = %s ORDER BY ts DESC'
#    cursor.execute(query, poster)
#    data = cursor.fetchall()
#    cursor.close()
#    return render_template('show_posts.html', poster_name=poster, posts=data)

@app.route('/logout')
def logout():
    session.pop('username')
    return redirect('/')
        
app.secret_key = 'some key that you will never guess'
#Run the app on localhost port 5000
#debug = True -> you don't have to restart flask
#for changes to go through, TURN OFF FOR PRODUCTION
if __name__ == '__main__':
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    
    app.run('127.0.0.1', 5000, debug = True)
