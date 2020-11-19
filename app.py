from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_mail import Mail, Message # YOU HAVE TO INSTALL FLASK-MAIL: pip install flask-mail
from werkzeug.utils import secure_filename
from datetime import timedelta 
from flask_mysqldb import MySQL
from decimal import Decimal
import MySQLdb.cursors
import re
import yaml
import time
import datetime
import os
import random
#from flask_sqlalchemy import sqlalchemy

# Substantiate flaskapp
app = Flask(__name__)

# Make secret key for session data
app.secret_key = "yeet"

# Configure dbs
# DB.YAML FILE PARAMETERS MUST ALL MATCH LOCAL MACHINE VALUES
# FOR OUR VM USER (currently uploaded): 'user' PASSWORD: 'HEJDIhsdf83-Q'
# FOR RJ'S LOCAL MACHINE: USER: 'ROOT' PASSWORD: 'password'

db = yaml.load(open('./templates/db.yaml'))
app.config['MYSQL_HOST'] = db['mysql_host']
app.config['MYSQL_USER'] = db['mysql_user']
app.config['MYSQL_PASSWORD'] = db['mysql_password']
app.config['MYSQL_DB'] = db['mysql_db']
mysql = MySQL(app)

# Set up for Emailing Forgotten Password
# Our account information:
#   EMAIL: BazarCustomerService@gmail.com;
#   PASSWORD: BazarCS316;
#   FIRST NAME: Bazar;
#   LAST NAME: Customer Service;
#   BIRTH DATE: Dec 20, 2000
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'BazarCustomerService@gmail.com'
app.config['MAIL_PASSWORD'] = 'BazarCS316'
app.config['MAIL_DEBUG'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_MAX_EMAILS'] = 1
app.config['MAIL_DEFAULT_SENDER'] = 'BazarCustomerService@gmail.com'
mail = Mail(app)

# Set-up for item and user image uploads
UPLOAD_FOLDER = 'static/jpg/avatars/'
IMG_UPLOAD  = 'static/jpg/item_images'
ALLOWED_EXTENSIONS = {'jpg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_EXTENSIONS'] = ALLOWED_EXTENSIONS
def allowed_file(filename): return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
DEFAULT_USER_AVATARS = ["apple.jpg", "cat.jpg", "chicken.jpg", "dog.jpg", "duck.jpg", "primrose.jpg"]

# Home page, renders homepage.html
@app.route("/", methods = ["POST","GET"])
def home():
    if "user" in session:
        logvar = True 
        first_name = session["first_name"]
        if request.method == "POST": # If the method that is called in homepage.html is a post method
            # Store Values from the form into searchinput variable
            searchinput = request.form["searchinput"]
            print(searchinput)
            showTable = "none;"
            if searchinput is not None:
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor) # This opens a cursor that can interact with the databases
                cursor.execute('SELECT itemID, name, price, avg_rating, description, category, image FROM iteminformation WHERE %s LIKE name OR %s LIKE category OR %s LIKE organization', [searchinput, searchinput, searchinput]) # Selects all items where searchinput matches
                searchr = cursor.fetchall() # takes all of these instances into account
                showTable = "inline;"
                print(searchr)
                return render_template("homepage.html", logvar = logvar, first_name = first_name, searchr = searchr, showTable = showTable)
        return render_template("homepage.html", logvar = logvar, first_name = first_name)
    else:
        logvar = False
        return render_template("homepage.html", logvar = logvar)
            
@app.route("/login", methods = ["POST","GET"])
def login():
    if request.method == "POST": # If the method that is called in login.html is a post method
        # Store Values from the form into user and password variables
        user = request.form["nm"]
        password = request.form["pw"]
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor) # This opens a cursor that can interact with the databases
        cursor.execute('SELECT * FROM buyers WHERE email = %s AND password = %s',(user,password)) # Selects all buyers where email and password both match
        account = cursor.fetchone() # takes one of these instances into account
        if account: # If succesfully found in database
            cursor =  mysql.connection.cursor() #Opens another Cursor
            cursor.execute('SELECT first_name FROM buyers WHERE email = %s AND password = %s',(user,password))
            first_name = cursor.fetchone()
            cursor.execute('SELECT last_name FROM buyers WHERE email = %s AND password = %s',(user,password))
            last_name = cursor.fetchone()
            cursor.execute('SELECT userID FROM buyers WHERE email = %s AND password = %s',(user,password))
            userID = cursor.fetchone()

            #Give email (user), password, first_name, userID variables to the session 
            session["first_name"] = first_name[0]
            session["last_name"] = last_name[0]
            session["userID"] = userID[0]
            session["user"] = user
            session["password"] = password
        
            # Check seller table to see if buyer/user is also a seller
            userID = session["userID"]
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT * FROM sellers WHERE userID = %s', [userID])
            seller = cursor.fetchone()

            # Set session seller status to corresponding boolean 
            if seller:
                session["seller"] = True
                session["org"] = seller['organization']
                session["descr"] = seller['description']
            else:
                session["seller"] = False
            flash("Login Successful!") # Flash a message that says login succesful 
            return redirect(url_for("home")) # Redirects to home page
        else: # If login is unsuccesful
            # Redirects to login page and flashes a message that login was incorrect
            flash("Incorrect Login!") 
            return redirect(url_for("login"))
    # If no method call 
    else:
        # if already logged in 
        if "user" in session:
            flash("Already Logged in!")
            return redirect(url_for("user"))
        return render_template("login.html")

# Sends email with password to input recovery email (if valid)!
@app.route("/forgotpw", methods = ["POST","GET"])
def forgotpw():
    if request.method == "POST":
        # Access form input: Email address
        recovery_email = request.form["email"]

        # Check if email exists in our database (we do not allow multiple accounts to have the same email address,
        # by our restrictions in registration, so this will be a unique access)
        cursor =  mysql.connection.cursor()
        cursor.execute('SELECT email FROM buyers WHERE email = %s',[recovery_email])
        if_email_exists = cursor.fetchone()

        # If email does not exist in db, return error and redirect to registration page
        if(if_email_exists[0] != recovery_email):
            flash("Whoops! No account matches this email address.")
            return redirect(url_for("registration"))
        
        # Access User's Info in DB
        cursor.execute('SELECT * FROM buyers WHERE email = %s', [recovery_email])
        user_info = cursor.fetchone()
        name = user_info[4]
        pw = user_info[2]

        # Send email with password to input email address
        msg = Message('Bazar Password Recovery', recipients = [recovery_email])
        msg.body = "Hello {}!\n\nYou recently selected the 'Forgot Password' option on our site.  Your current password is: {} .\nIf this request did not come from you, consider resetting your password on our site through your User Profile page.\n\nPlease do not reply to this email. This account is not monitored.".format(name, pw)
        mail.send(msg)
        flash("Password recovery successful. Check your email!")
        return redirect(url_for("login"))
    else:
        return render_template("forgotpw.html")

# Logout page, clears session
@app.route("/logout")
def logout():
    # notifies that you've been logged out
    flash("You have been logged out", "info") #warning, info, error
    # Pops the user info out of the session
    session.pop("user", None)
    session.pop("email", None)
    return redirect(url_for("home"))

# Display user data, link to modify user data
@app.route("/user", methods = ["POST", "GET"])
def user():
   if "user" in session:
       # Access user information for logged-in user
       logvar = True
       first_name = session["first_name"]
       last_name = session["last_name"]
       userID = session["userID"]
       seller = session["seller"]
       cursor = mysql.connection.cursor()
       # All user data stored in Buyers: (userID, email, password,
       #   currentBalance, first_name, last_name, image)
       cursor.execute('SELECT * FROM buyers WHERE userID = %s', [userID])
       info = cursor.fetchone()
       return render_template("user.html", logvar = logvar, first_name = first_name, last_name = last_name, balance = info[3], user = info[1], seller = seller, info = info, image_path = info[6])
   else:
       flash("You are not logged in!")
       return redirect(url_for("login"))

# REGISTER NEW USER
@app.route("/registration", methods = ["POST", "GET"])
def registration():
   if "user" in session:
       flash("You are already logged in! Logout to register as different user.")
       return redirect(url_for("user"))
   elif request.method == "POST":
       
       cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
 
       # Save password and confirmed password
       # Ensure that password matches with confirmed pw
       password = request.form["password"]
       confirmation = request.form["confirmedpw"]
       if(password != confirmation):
           flash("Whoops! Your password and confirmed password don't match!")
           return redirect(url_for("registration"))
 
       # Save input email and ensure it is unique in our db; otherwise, reject it
       email = request.form["email"]
       cursor.execute('SELECT email FROM buyers WHERE email = %s',[email])
       if_email_exists = cursor.fetchone()
       # If exists in database already -> Error: email already in use; Login or use other email
       if(if_email_exists):
           flash("Whoops! A user with this email already exists. Please login with this address or register with a different one.")
           return redirect(url_for("registration"))
 
       # Save first and last name, organization name (optional), organization description (optional), whether user is a seller
       # If user does not want to be a seller, org name and description are never used/are discarded even if input
       first = request.form["first_name"]
       last = request.form["last_name"]
       org_name = request.form["org_name"]
       if len(org_name) == 0: org_name = "{} {}".format(first, last)
       descr = request.form["description"]
       ifSeller = request.form.get("sellercheck")
 
       # Determine New Unique UserID
       cursor.execute('SELECT max(userID) as A FROM Buyers')
       maxID = cursor.fetchone()
       if(maxID == None): maxID = 0
       print(maxID)
       userID = maxID["A"] + 1

       # Handle avatar/profile picture upload
       uploaded_file = request.files['avatar']
       filename = secure_filename(uploaded_file.filename)
       if filename != '' and allowed_file(filename):
           avatarID = "{}.jpg".format(userID)
           avatar_path = "static/jpg/avatars/{}".format(avatarID)
           uploaded_file.save(os.path.join(avatar_path))
       else:
           avatar_path = "static/jpg/default_avatars/{}".format(random.choice(DEFAULT_USER_AVATARS))

       # Create User in Buyers
       # Buyers(userID, email, password, currentBalance, firstname, lastname, image)
       cursor.execute('INSERT INTO Buyers VALUES(%s, %s, %s, %s, %s, %s, %s)',[userID, email, password, 0.00, first, last, avatar_path])
       mysql.connection.commit()
 
       # Create a seller with the same UserID as in Buyers if seller is checked
       if(ifSeller == "true"):
           cursor.execute('INSERT INTO Sellers VALUES(%s, %s, %s, %s, %s)',[userID, org_name, None, descr, 0.00])
           mysql.connection.commit()
 
       flash("Thank you for registering as a new user!")

       # Once you register as a user, you have to log in as
       # the new user to access site, so redirect to login once registration is complete
       return redirect(url_for("login"))
   return render_template("registration.html")


@app.route("/cart")
def cart():
   if "user" in session: # Check if user is logged in
      logvar = True # Update logvar boolean if so
      # Retrieve session data
      first_name = session["first_name"]
      buyerID = session["userID"]
      # Open a cursor and get items purchased from user in purchases
      cursor = mysql.connection.cursor()
      cursor.execute('SELECT itemID, name, sellerId, price, num FROM cartitems WHERE buyerID = %s', [buyerID])
      cartItems = cursor.fetchall()
      totalPrice = 0
      for row in cartItems:
          totalPrice = totalPrice + (row[3] * row[4])
      return render_template("cart.html", logvar = logvar, buyerID = buyerID, first_name = first_name, cartItems = cartItems, totalPrice = totalPrice)
   else: # If you somehow accessed this page and weren't logged in
     flash("You are not logged in to add balance")
     return redirect(url_for("home"))
 
# UPDATE CART QUANTITY
# check if sufficient seller supply
@app.route('/cart/<id>', methods = ["POST", "GET"])
def modQuantity(id):
    if "user" in session:
        if request.method == 'POST':
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            logvar = True
            itemID = id
            cursor.execute('SELECT num FROM cart WHERE itemID = %s', [itemID])
            currQuantity = cursor.fetchone()
            quantity = currQuantity['num']
            #find quantity available of item on seller side
            cursor.execute('SELECT num FROM items WHERE itemID = %s', [itemID])
            available = cursor.fetchone()
            supply = available['num']
            print("Supply: ", supply)
            #retrieve values from form
            addValue = Decimal(request.form['addQuantity'])
            if addValue > supply:
                flash("Insufficient number of copies of item: {} items remaining. Please remove item from cart or reduce item quantity".format(supply))
                return redirect(url_for("cart"))
            else:
                newQuantity = quantity + addValue
                print(newQuantity)
                cursor.execute('UPDATE cart SET num = %s WHERE itemID = %s', [newQuantity, itemID])
                mysql.connection.commit()
                return redirect(url_for("cart"))
    else: # If you somehow accessed this page and weren't logged in
        flash("Incorrect Payment Information")
        return redirect(url_for("home"))

# Checkout Ability successful:
# - reduce buyer balance
# - increase seller balance
# - all items in cart will be added to purchase history
# - seller history will be updated with history of seller
# - quantity of item available on seller side decreased by quantity checked OUT
# - if insufficient funds --> Flash "Insufficient Funds"
# - if seller no longer has enough supply, "Insufficient number of copies of item: 
# (current quantity of that item) items remaining. 
# Please remove item from cart or reduce item quantity"
@app.route('/cart/checkout/<id>/<price>', methods = ["POST", "GET"])
def checkSuccess(id, price):
    if "user" in session:
        if request.method == 'POST':
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            logvar = True
            buyerID = id
            totalPrice = price
            cursor.execute('SELECT currentBalance FROM buyers WHERE userID = %s',[buyerID])
            balance = cursor.fetchone()
            money = balance['currentBalance']
            funds = Decimal(money)
            print(funds)
            #check sufficient funds
            if funds >= Decimal(totalPrice):
                #reduce buyer balance
                remainBalance = funds - Decimal(totalPrice)
                cursor.execute('UPDATE buyers SET currentBalance = %s WHERE userID = %s', [remainBalance, buyerID])
                #address updates per item in cart
                cursor.execute('SELECT itemID, name, sellerId, price, num FROM cartitems WHERE buyerID = %s', [buyerID])
                cartItems = cursor.fetchall()
                #example row:  {'itemID': 1, 'name': 'Til There Was You', 'sellerID': 167, 'price': Decimal('6.00'), 'num': 2}
                for dataRow in cartItems:
                    print("ID: ", dataRow['itemID'])
                    itemID = dataRow['itemID']
                    sellerID = dataRow['sellerID']
                    num = dataRow['num']
                    price = dataRow['price']
                    timeFormat = '%Y-%m-%d %H:%M:%S'
                    currTime = datetime.datetime.now().strftime(timeFormat)
                    print(currTime)
                    #Purchase: buyerID, itemID, dayTime, num
                    #add item to purchase --> populate user history + seller history
                    cursor.execute('INSERT INTO purchase (buyerID, itemID, dayTime, num) VALUES (%s, %s, %s, %s)', [buyerID, itemID, currTime, num])
                    mysql.connection.commit()
                    #reduce supply of item in Item
                    cursor.execute('SELECT num FROM items WHERE itemID = %s', [itemID])
                    itemQuantity = cursor.fetchone()['num']
                    print("itemQ: ", itemQuantity)
                    newCount = itemQuantity - num
                    print("newCount = itemQ - num: ", newCount)
                    cursor.execute('UPDATE items SET num = %s WHERE itemID = %s', [newCount, itemID])
                    mysql.connection.commit()
                    #increase individual seller balance
                    cursor.execute('SELECT currentBalance FROM buyers WHERE userID = %s', [sellerID])
                    sellerBalance = cursor.fetchone()['currentBalance']
                    newSellerBalance = sellerBalance + (num*price)
                    cursor.execute('UPDATE buyers SET currentBalance = %s WHERE userID = %s', [newSellerBalance, sellerID])
                    mysql.connection.commit()
                    #remove items from cart database to clear cart after successful checkout
                    cursor.execute('DELETE FROM cart WHERE buyerID = %s AND itemID = %s', [buyerID, itemID])
                    mysql.connection.commit()
                flash("Thank you for shopping at BAZAR!")
                return redirect(url_for("purchasehistory"))
            else: #if insufficient funds
                flash("Insufficient Funds")
                return redirect(url_for("cart"))
    else: # If you somehow accessed this page and weren't logged in
        flash("Incorrect Payment Information")
        return redirect(url_for("home"))

@app.route("/item/<id>", methods = ["POST","GET"])
def item(id):
    if "user" in session: # Check if user is logged in
        logvar = True # Update logvar boolean if so
        # Retrieve session data
        first_name = session["first_name"] 
        sellerID = session["userID"]
        seller = session["seller"]
        if request.method == "POST":
            num = request.form['num']
            userID = session["userID"]
            cursor = mysql.connection.cursor()
            cursor.execute("INSERT INTO cart VALUES (%s,%s,%s)",[userID,id,num])
            mysql.connection.commit()

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM items WHERE itemID = %s",[id])
    items = cursor.fetchall()
    item = items[0]
    return render_template("item.html",logvar = logvar, first_name = first_name,item = item)

@app.route("/addreview")
def addreview():
    if "user" in session: # Check if user is logged in
        logvar = True # Update logvar boolean if so
        # Retrieve session data
        userID = session["userID"]
        return render_template("addreview.html", logvar = logvar, userID = userID)
    else: # If you somehow accessed this page and weren't logged in
        flash("You are not logged in to add a review!")
        return redirect(url_for("home")) 

@app.route('/addreview/<id>', methods = ["POST", "GET"])
def updatereview(id):
    if "user" in session:
        if request.method == 'POST':
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            logvar = True
            userID = id
            input_itemID = request.form["item_id"]
            input_stars = request.form["stars"]
            input_comments = request.form["body"]
            timeFormat = '%Y-%m-%d %H:%M:%S'
            currTime = datetime.datetime.now().strftime(timeFormat)
            #ensure valid info
            cursor.execute('INSERT INTO ItemReview VALUES(%s, %s, %s, %s, %s)', [userID, input_itemID, input_stars, input_comments, currTime])
            mysql.connection.commit()
            flash('Review successfully added!')
            return redirect(url_for("addreview"))
    else: # If you somehow accessed this page and weren't logged in
        flash("You are not logged in to add a review!")
        return redirect(url_for("home"))
    
@app.route("/seller", methods = ["POST","GET"])
def seller():
    if "user" in session and session["seller"] == True: # Check if user is logged in
        logvar = True # Update logvar boolean if so
        # Retrieve session data
        first_name = session["first_name"] 
        sellerID = session["userID"]
        seller = session["seller"]
        # Open a cursor and get all items sold for a seller
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT itemID, name, price, num, image FROM items WHERE sellerID = %s', [sellerID])
        items = cursor.fetchall()
        cursor.execute('SELECT * FROM buyers WHERE userID = %s', [sellerID])
        user = cursor.fetchall()
        org = session["org"]
        descr = session["descr"]
        # This is where the delete function is implemented
        if request.method == "POST":
            item_id = request.form["item_id"]
            cursor.execute('DELETE FROM items WHERE itemID = %s',(item_id,))
            mysql.connection.commit() # This commits the change to the actual mysql database
            return redirect(url_for("seller"))
        return render_template("seller.html", logvar = logvar, first_name = first_name, seller = seller, items = items, user=user[0], org=org, descr = descr)
    else: # If you somehow accessed this page and weren't logged in
        flash("You are not logged in as a seller")
        return redirect(url_for("home"))

@app.route("/addbalance")
def addbalance():
   if "user" in session: # Check if user is logged in
       logvar = True # Update logvar boolean if so
       # Retrieve session data
       first_name = session["first_name"]
       last_name = session["last_name"]
       userID = session["userID"]
       # Open a cursor and get current balance for user
       cursor = mysql.connection.cursor()
       cursor.execute('SELECT currentBalance FROM buyers WHERE userID = %s', [userID])
       currentBalance = cursor.fetchone()
       return render_template("addbalance.html", logvar = logvar, userID = userID, first_name = first_name, last_name = last_name, currentBalance = currentBalance)
   else: # If you somehow accessed this page and weren't logged in
       flash("You are not logged in to add balance")
       return redirect(url_for("home"))

@app.route("/purchasehistory")
def purchasehistory():
   if "user" in session: # Check if user is logged in
       logvar = True # Update logvar boolean if so
       # Retrieve session data
       first_name = session["first_name"]
       buyerID = session["userID"]
       # Open a cursor and get items purchased from user in purchases
       cursor = mysql.connection.cursor()
       cursor.execute('SELECT * FROM itemhistory WHERE buyerID = %s', [buyerID])
       itemsPurchased = cursor.fetchall()
       return render_template("purchasehistory.html", logvar = logvar, buyerID = buyerID, first_name = first_name, itemsPurchased = itemsPurchased)
   else: # If you somehow accessed this page and weren't logged in
      flash("You are not logged in to view purchase history")
      return redirect(url_for("home"))
 
# Get Item Details
@app.route('/itempage/<id>', methods = ["POST", "GET"])
def getDetails(id):
   cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
   cursor.execute('SELECT itemID, sellerID, price, num FROM items WHERE itemID = %s',[id])
   itemDetails = cursor.fetchall()
   return render_template("item.html", itemDetails = itemDetails)
 
# Get current data and reroute to modify form
@app.route('/update/<id>', methods =["POST","GET"])
def update(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM items WHERE itemID = %s',[id])
    item = cursor.fetchall()
    cursor.close()
    print(item)
    return render_template("modify.html", item = item)

#UPDATE BALANCE
@app.route('/addbalance/<id>', methods = ["POST", "GET"])
def modBalance(id):
    if "user" in session:
        if request.method == 'POST':
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            logvar = True
            userID = id
            cursor.execute('SELECT currentBalance FROM buyers WHERE userID = %s', [userID])
            currentBalance = cursor.fetchone()
            currentValue = currentBalance['currentBalance']
            #get variables from form
            first_name = session["first_name"]
            last_name = session["last_name"]
            input_fname = request.form["firstname"]
            input_lname = request.form["lastname"]
            card_number = request.form["cardnumber"]
            card_code = request.form["securitycode"]
            addValue = Decimal(request.form['addValue'])
            newValue = currentValue + addValue
            print(newValue)
            #ensure valid info
            if validCreditCard(card_number) == True and len(card_code) == 3:
                cursor.execute('UPDATE buyers SET currentBalance = %s WHERE userID = %s', [newValue, userID])
                flash('Success! Your wallet has been topped up')
                mysql.connection.commit()
                return redirect(url_for("addbalance"))
            else:
                flash("Unsuccessful transaction. Please Try Again!")
                return redirect(url_for("addbalance"))
    else: # If you somehow accessed this page and weren't logged in
        flash("Incorrect Payment Information")
        return redirect(url_for("home"))

def validCreditCard(str):
    nums = str.replace(" ", "").replace("-", "")
    return (len(nums) == 16) and nums.isdecimal()

@app.route('/modify/<id>', methods = ["POST","GET"])
def moditem(id):
    if "user" in session and session["seller"] == True:
        if request.method == 'POST':
            logvar = True
            sellerID = session["userID"]
            first_name = session["first_name"]
            # Get variables from previous form
            newname = request.form['newname']
            newprice = request.form['newprice']
            newcount = request.form['newcount']
            newdesc = request.form['newdesc']
            
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

            # Handle avatar upload
            uploaded_file = request.files['newimage']
            filename = secure_filename(uploaded_file.filename)

            if (len(filename) != 0) and allowed_file(filename):
                # Handle avatar upload
                cursor.execute('SELECT image FROM items WHERE itemID = %s',[id])
                dict_image = cursor.fetchone()
                
                if(dict_image):
                    old_image = dict_image["image"]
                    if old_image == "static/jpg/item_images/{}a.jpg".format(id):
                        avatar_path = "static/jpg/item_images/{}b.jpg".format(id)
                    else:
                        avatar_path = "static/jpg/item_images/{}a.jpg".format(id)
                    os.remove(os.path.join(old_image))
                else:
                    avatar_path = "static/jpg/item_images/{}.jpg".format(id)
                uploaded_file.save(os.path.join(avatar_path))
                cursor.execute('UPDATE items SET image = %s WHERE itemID = %s',[avatar_path, id])
                mysql.connection.commit()
            elif (len(filename) != 0) and not allowed_file(filename):
                flash('Only .jpg image formats are currently supported. Please upload a .jpg, instead.')
                return redirect(url_for("/seller"))
            elif (len(filename) == 0):
                avatar_path = "static/jpg/default_avatars/{}".format(random.choice(DEFAULT_USER_AVATARS))
                cursor.execute('UPDATE items SET image = %s WHERE itemID = %s',[avatar_path, id])
                mysql.connection.commit()
            
            cursor.execute('UPDATE items SET name = %s, price = %s, num = %s, description = %s WHERE itemID = %s',[newname, newprice, newcount, newdesc, id])
            flash('Item Updated Successfully')
            mysql.connection.commit()
            return redirect(url_for("seller"))
    else: # If you somehow accessed this page and weren't logged in
        flash("You are not logged in/a seller")
        return redirect(url_for("home"))

@app.route('/updateuser', methods =["POST","GET"])
def updateuser():
    # Access all user data stored in Buyers and pass into page rendering modify form
    cursor = mysql.connection.cursor()
    userID = session["userID"]
    cursor.execute('SELECT * FROM buyers WHERE userID = %s',[userID])
    userdata = cursor.fetchone()
    cursor.close()
    return render_template("modifyuser.html", first_name = userdata[4], last_name = userdata[5], email = userdata[1], image_path = userdata[6])

@app.route('/modifymydata', methods = ["POST","GET"])
def moduser():
    if "user" in session:
        if request.method == 'POST':
            logvar = True
            userID = session["userID"]
            cursor = mysql.connection.cursor()

            # Save all form inputs
            newfirst = request.form['newfirst']
            newlast = request.form['newlast']
            newemail = request.form['newemail']
            newpass = request.form['newpass']
            uploaded_file = request.files['newimage']
            filename = secure_filename(uploaded_file.filename)

            # If nothing was input into the form, redirect to user page
            if (len(newfirst) == 0) and (len(newlast) == 0) and (len(newemail) == 0) and (len(newpass)==0) and (len(filename)==0):
                flash('You did not change any of your user information.')
                return redirect(url_for("user"))
            # Update first name, if there exists an input
            if len(newfirst) != 0:
                cursor.execute('UPDATE buyers SET first_name = %s WHERE userID = %s',[newfirst, userID])
                session["first_name"] = newfirst
                mysql.connection.commit()
            # Update last name, if there exists an input
            if len(newlast) != 0:
                cursor.execute('UPDATE buyers SET last_name = %s WHERE userID = %s',[newlast, userID])
                session["last_name"] = newlast
                mysql.connection.commit()
            # Update email, if there exists an input
            if len(newemail) != 0:
                cursor.execute('UPDATE buyers SET email = %s WHERE userID = %s',[newemail, userID])
                session["user"] = newemail
                mysql.connection.commit()
            # Update password, if there exists an input
            if len(newpass) != 0:
                cursor.execute('UPDATE buyers SET password = %s WHERE userID = %s',[newpass, userID])
                session["password"] = newpass
                mysql.connection.commit()
            # Update avatar/profile image, if there exists an input
            if (len(filename) != 0) and allowed_file(filename):
                # Handle avatar upload
                cursor.execute('SELECT image FROM buyers WHERE userID = %s',[userID])
                old_image = cursor.fetchone()
                if(old_image):
                    old_image = old_image[0]
                    if old_image == "static/jpg/avatars/{}a.jpg".format(userID):
                        avatar_path = "static/jpg/avatars/{}b.jpg".format(userID)
                    else:
                        avatar_path = "static/jpg/avatars/{}a.jpg".format(userID)
                    os.remove(os.path.join(old_image))
                else:
                    avatar_path = "static/jpg/avatars/{}.jpg".format(userID)
                uploaded_file.save(os.path.join(avatar_path))
                cursor.execute('UPDATE buyers SET image = %s WHERE userID = %s',[avatar_path, userID])
                mysql.connection.commit()
            
            # Indicate successful update and redirect to user page
            flash('You have successfully updated your user information!')
            return redirect(url_for("user"))
    else:
        flash("You are not logged in!")
        return redirect(url_for("home"))

@app.route('/updateorg', methods =["POST","GET"])
def updateorg():
    # Access all org data stored in Sellers and pass into page rendering modify form
    cursor = mysql.connection.cursor()
    userID = session["userID"]
    cursor.execute('SELECT * FROM sellers WHERE userID = %s',[userID])
    orgdata = cursor.fetchone()
    cursor.close()
    return render_template("modifyorg.html", name = orgdata[1], descr = orgdata[3])

@app.route('/modifymyorgdata', methods = ["POST","GET"])
def modorg():
    if "user" in session:
        if request.method == 'POST':
            logvar = True
            userID = session["userID"]
            cursor = mysql.connection.cursor()
            newname = request.form['newname']
            newdescr = request.form['newdescr']
            # If nothing was input into the form, redirect to user page
            if (len(newname) == 0) and (len(newdescr) == 0):
                flash('You did not change any of your organization information.')
                return redirect(url_for("seller"))
            # Update organization name, if there exists an input
            if len(newname) != 0:
                cursor.execute('UPDATE sellers SET organization = %s WHERE userID = %s',[newname, userID])
                session["org"] = newname
                mysql.connection.commit()
            # Update organization description, if there exists an input
            if len(newdescr) != 0:
                cursor.execute('UPDATE sellers SET description = %s WHERE userID = %s',[newdescr, userID])
                session["descr"] = newdescr
                mysql.connection.commit()
            flash('You have successfully updated your organization information!')
            return redirect(url_for("seller"))
    else:
        flash("You are not logged in!")
        return redirect(url_for("home"))

@app.route('/additemspage')
def additemspage():
    if "user" in session and session["seller"] == True:
        logvar = True
        first_name = session["first_name"]
        return render_template("additems.html", logvar = logvar, first_name = first_name)
    else:
        flash("You are not logged in/a seller")
        return redirect(url_for("home"))

@app.route('/additems', methods = ['POST','GET'])
def additems():
    if "user" in session and session["seller"] == True:
        logvar = True
        first_name = session["first_name"]
        if request.method == "POST":
            sellerID = session["userID"]
            itemname = request.form['name']
            price = request.form['price']
            count = request.form['num']
            description = request.form['desc']
           
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT max(itemID) as A FROM items')
            maxID = cursor.fetchone()
            if(maxID == None): maxID = 0
            print(maxID)
            itemID = maxID["A"] + 1
             # Handle avatar upload
            uploaded_file = request.files["image"]
            filename = secure_filename(uploaded_file.filename)
            if filename != '' and allowed_file(filename):
                imageID = "{}.jpg".format(itemID)
                item_image_path = "static/jpg/item_images/{}".format(imageID)
                uploaded_file.save(os.path.join(item_image_path))
            else:
                item_image_path = "static/jpg/default_avatars/{}".format(random.choice(DEFAULT_USER_AVATARS))
            
            avg_rating = 0.00
            cursor.execute('INSERT INTO items VALUES(%s, %s, %s, %s, %s, %s, %s, %s)',[itemID, sellerID, itemname, price, avg_rating, count, description, item_image_path])
            mysql.connection.commit()
            flash("Item successfully added")
            return redirect(url_for("additemspage"))
    else:
        flash("You are not logged in/a seller")
        return redirect(url_for("home"))

@app.route('/tradehistory', methods = ['POST','GET'])
def tradehistory():
    if "user" in session and session["seller"] == True:
        logvar = True
        first_name = session["first_name"]
        sellerID = session["userID"]
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM final WHERE userID = %s', [sellerID])
        history = cursor.fetchall()
        print(history)
        return render_template('tradehistory.html',logvar = logvar, first_name = first_name, history = history)
    else:
        flash("You are not logged in/a seller")
        return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)