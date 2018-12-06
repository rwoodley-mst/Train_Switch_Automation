from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, IntegerField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
from sendPacket import send_packet

app = Flask(__name__)

# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'myflaskapp'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
# init MYSQL
mysql = MySQL(app)

# Index
@app.route('/')
def index():
    return render_template('home.html')


# About
@app.route('/about')
def about():
    return render_template('about.html')


# Register Form Class
class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    username = StringField('Username', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')


# User Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute query
        cur.execute("INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)", (name, email, username, password))

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash('You are now registered and can log in', 'success')

        return redirect(url_for('login'))
    return render_template('register.html', form=form)


# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get Form Fields
        username = request.form['username']
        password_candidate = request.form['password']

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])

        if result > 0:
            # Get stored hash
            data = cur.fetchone()
            password = data['password']

            # Compare Passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid login'
                return render_template('login.html', error=error)
            # Close connection
            cur.close()
        else:
            error = 'Username not found'
            return render_template('login.html', error=error)

    return render_template('login.html')

# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('login'))
    return wrap

# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))

# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():
    # Create cursor
    cur = mysql.connection.cursor()
    switchCur = mysql.connection.cursor()

    # Show all switches
    result = switchCur.execute("SELECT * FROM hubs")
    hubs = switchCur.fetchall()

    if result > 0:
        return render_template('dashboard.html', hubs=hubs)
    else:
        msg = 'No Switches Found'
        return render_template('dashboard.html', msg=msg)
    # Close connection
    cur.close()

# Switch Form Class
class SwitchForm(Form):
    address = StringField('Address', [validators.Length(min=16, max=16)])
    count = IntegerField('Switch Number', [validators.NumberRange(min=0, max=2)]) # validator is buggy

# Hub form class
class HubForm(Form):
    address = StringField('Address', [validators.Length(min=1, max=16)])
    count = StringField('Switch Total', [validators.Length(min=1, max=2)])

# Add Switch
@app.route('/add_switch', methods=['GET', 'POST'])
@is_logged_in
def add_switch():
    form = SwitchForm(request.form)
    if request.method == 'POST' and form.validate():
        address = form.address.data
        count = form.count.data

        # Create Cursor
        cur = mysql.connection.cursor()

        # Execute
        cur.execute("INSERT INTO hubs(address, switch_num) VALUES(%s, %s)",(address, count))

        # Commit to DB
        mysql.connection.commit()

        #Close connection
        cur.close()

        flash('Switch Created', 'success')

        return redirect(url_for('dashboard'))

    return render_template('add_switch.html', form=form)

# Add Hub (Does not work currently)
@app.route('/add_hub', methods=['GET', 'POST'])
@is_logged_in
def add_hub():
    form = SwitchForm(request.form)
    if request.method == 'POST' and form.validate():
        address = form.address.data
        count = form.count.data

        # Create Cursor
        cur = mysql.connection.cursor()

        # Execute
        cur.execute("INSERT INTO hubs(address, switch_num) VALUES(%s, %s)",(address, count))

        # Commit to DB
        mysql.connection.commit()

        #Close connection
        cur.close()

        flash('Switch Created', 'success')

        return redirect(url_for('dashboard'))

    return render_template('add_hub.html', form=form)

# Edit Switch
@app.route('/edit_switch/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def edit_switch(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Get switch by id
    result = cur.execute("SELECT * FROM hubs WHERE id = %s", [id])

    switch = cur.fetchone()
    cur.close()
    # Get form
    form = SwitchForm(request.form)

    # Populate switch form fields
    form.address.data = switch['address']
    form.count.data = switch['switch_num']

    if request.method == 'POST' and form.validate():
        address = request.form['address']
        count = request.form['count']

        # MySQL commands
        cur = mysql.connection.cursor() # Create cursor
        cur.execute ("UPDATE hubs SET address=%s, switch_num=%s WHERE id=%s",(address, count, id)) # Execute
        mysql.connection.commit() # Commit
        cur.close()

        flash('Switch Updated', 'success')

        return redirect(url_for('dashboard'))

    return render_template('edit_switch.html', form=form)

# Delete Switch
@app.route('/delete_switch/<string:id>', methods=['POST'])
@is_logged_in
def delete_switch(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Execute
    cur.execute("DELETE FROM hubs WHERE id = %s", [id])

    # Commit to DB
    mysql.connection.commit()

    #Close connection
    cur.close()

    flash('Switch Deleted', 'success')

    return redirect(url_for('dashboard'))

# Switch In
@app.route('/switch_in/<string:address>/<int:switch_num>', methods=['POST'])
@is_logged_in
def switch_in(address, switch_num):

    # Generate data and address
    addressList = bytes.fromhex(address) # Convert hex string to list of bytes
    newVal = switch_num << 1 # Bit shift left 1
    dataSend = 1 + newVal # Adding 1 is switch in
    print (address, dataSend, sep='<-')

    send_packet(addressList, dataSend)
    flash('Switched In', 'success')
    return redirect(url_for('dashboard'))

# Switch Right
@app.route('/switch_out/<string:address>/<int:switch_num>', methods=['POST'])
@is_logged_in
def switch_out(address, switch_num):

    # Generate data and address
    addressList = bytes.fromhex(address) # Convert hex string to list of bytes
    newVal = switch_num << 1 # Bit shift left 1
    dataSend = 0 + newVal # Adding 0 is switch out
    print(address, dataSend, sep='<-')

    send_packet(addressList, dataSend)
    flash('Switched Out', 'success')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.secret_key='secret123'
    app.run(debug=True, host='0.0.0.0')
