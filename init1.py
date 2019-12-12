#Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect, flash
import pymysql.cursors
import hashlib
import secrets
from PIL import Image
import os
import time
from functools import wraps


SALT = 'cs3083'

#Initialize the app from Flask
app = Flask(__name__)

IMAGES_DIR = os.path.join(os.getcwd(), 'images')

#Configure MySQL
conn = pymysql.connect(host='localhost',
                       port = 8889,
                       user='root',
                       password='root',
                       db='finsta',
                       charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor)
def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not 'username' in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return dec
    
#Define a route to hello function
@app.route('/')
def hello():
    if 'username' in session:
        return redirect(url_for('home'))
    return render_template('index.html')

@app.route('/home')
@login_required
def home():
    username = session['username']
    # get the users information
    cursor = conn.cursor()
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    data = cursor.fetchone()
    firstName = data['firstName']
    lastName = data['lastName']
    # get the photos visible to the username
    query = 'SELECT photoID,postingdate,filepath,caption,photoPoster FROM photo WHERE photoPoster = %s OR photoID IN (SELECT photoID FROM Photo WHERE photoPoster != %s AND allFollowers = 1 AND photoPoster IN (SELECT username_followed FROM follow WHERE username_follower = %s AND username_followed = photoPoster AND followstatus = 1)) OR photoID IN (SELECT photoID FROM sharedwith NATURAL JOIN belongto NATURAL JOIN photo WHERE member_username = %s AND photoPoster != %s) ORDER BY postingdate DESC'
    cursor.execute(query, (username, username, username, username, username))
    data = cursor.fetchall()
    for post in data: # post is a dictionary within a list of dictionaries for all the photos
        query = 'SELECT username, firstName, lastName FROM tagged NATURAL JOIN person WHERE tagstatus = 1 AND photoID = %s'
        cursor.execute(query, (post['photoID']))
        result = cursor.fetchall()
        print('hello')
        if (result):
            post['tagees'] = result
        query = 'SELECT firstName, lastName FROM person WHERE username = %s'
        cursor.execute(query, (post['photoPoster']))
        ownerInfo = cursor.fetchone()
        post['firstName'] = ownerInfo['firstName']
        post['lastName'] = ownerInfo['lastName']
        query = "SELECT username,rating FROM likes WHERE photoID = %s"
        cursor.execute(query, (post['photoID']))
        result = cursor.fetchall()
        if (result):
            post['likers'] = result
            
    cursor.close()
    return render_template('home.html', username=username, firstName=firstName, lastName =lastName, posts = data)


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

@app.route('/managerequests', methods=['GET','POST'])
@login_required
def managerequests():
    # get all the requests that have followstatus = 0 for the current user
    cursor = conn.cursor()
    query = 'SELECT username_follower FROM follow WHERE username_followed = %s AND followstatus = 0'
    cursor.execute(query, (session['username']))
    data = cursor.fetchall()
    if request.form:
        chosenUsers = request.form.getlist('chooseUsers')
        for user in chosenUsers:
            if request.form['action'] ==  'Accept':
                query = 'UPDATE follow SET followstatus = 1 WHERE username_followed=%s AND username_follower = %s'
                cursor.execute(query, (session['username'], user))
                conn.commit()
                flash('The selected friend requests have been accepted!')
            elif request.form['action'] == 'Decline':
                query = 'DELETE FROM follow WHERE username_followed = %s AND username_follower = %s'
                cursor.execute(query, (session['username'], user))
                conn.commit()
                flash('The selected friend requests have been deleted')
        return redirect(url_for('managerequests'))
        # handle form goes here
    cursor.close()
    return render_template('managerequests.html', followers = data)
    
@app.route('/createFriendGroup', methods=['GET', 'POST'])
@login_required
def createFriendGroup():
    if request.form:
        groupName = request.form['groupName']
        description = request.form['description']
        cursor = conn.cursor()
        # check to make sure the group Name doesn't already exist for the user
        query = 'SELECT * FROM friendGroup WHERE groupOwner = %s AND groupName = %s'
        cursor.execute(query, (session['username'], groupName))
        data = cursor.fetchone()
        if data: # bad, return error message
            error = f'You already have a friend group called {groupName}'
            return render_template('createFriendGroup.html', message = error)
        else: # good, add group into database
            query = 'INSERT INTO friendGroup VALUES(%s,%s,%s)'
            cursor.execute(query, (session['username'], groupName, description))
            conn.commit()
            flash(f'Successfully created the {groupName} friend group')
            return redirect(url_for('createFriendGroup'))

    return render_template('createFriendGroup.html')

@app.route('/follow', methods=['GET', 'POST'])
@login_required
def follow():
    if request.form: #submitted
        username = request.form['username']
        # check if the username extists
        cursor = conn.cursor()
        query = 'SELECT * FROM person WHERE username = %s'
        cursor.execute(query,(username))
        data = cursor.fetchone()
        if data:
            query = 'SELECT * FROM follow WHERE username_followed = %s AND username_follower = %s'
            cursor.execute(query,(username, session['username']))
            data = cursor.fetchone()
            if (data):
                if(data['followstatus'] == 1):
                    error  = f'You already follow {username}!'
                else:
                    error = f'You already sent a request to {username}'
                cursor.close()
                return render_template('follow.html', message = error)
            else:
                query = 'INSERT INTO follow VALUES(%s,%s,0)'
                cursor.execute(query,(username, session['username']))
                conn.commit()
            
                message = f'Request successfully sent to {username}'
                cursor.close()
                return render_template('follow.html', message = message)
        else:
            error = 'That username does not exist, try another one'
            cursor.close()
            return render_template('follow.html', error = error)
            cursor.close()
    return render_template('follow.html')

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

def savePhoto(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/images', picture_fn)
    output_size = (400, 500)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn

@app.route('/upload', methods=['GET','POST'])
@login_required
def upload_image():
    username = session['username']
    userGroups = getGroups(username)
    if request.method == 'POST':
        image_file = request.files.get('imageToUpload', '')
        filepath = savePhoto(image_file)
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
            return render_template('upload.html', message=message, groups = userGroups)
        else:
            cursor = conn.cursor()
            groups = request.form.getlist('groups')
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
#@app.route('/show_posts', methods=['GET', 'POST'])
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
    if not os.path.isdir('images'):
        os.mkdir(IMAGES_DIR)
    
    app.run('127.0.0.1', 5000, debug = True)
