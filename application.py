from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from datetime import datetime


from helpers import *

# configure application
app = Flask(__name__)
# hash = pwd_context.hash("toomanystocks")
# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    if request.method == "GET":
    
        user_id = int(session.get('user_id'))
        user_data = db.execute('''SELECT * FROM portfolio WHERE user_id = :user_id''', user_id = user_id)
        
        if not user_data:
            return render_template('quote.html')
        
        #create lists of values for sake of returning them to F2E

        portfolio = []
        
        for i in user_data:
            #getting data from table
            symbol = i.get('symbol')
            quantity = i.get('quantity')
            """default_data.update({'item3': 3}"""
            #getting live data
            stock_data = lookup(symbol)
            name = stock_data.get('name')
            price = float(stock_data.get('price'))
            combined_price = round(price * quantity, 2)
            
            #inserting data into a list
            a_dict = {
                    'symbol': symbol, 'name': name,
                    'price': price, 'quantity': quantity, 
                    'combined_price': combined_price
            }
            portfolio.append(a_dict)
        
        #get user's cash and total cost of given shares    
        data_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = user_id)
        cash = float(data_cash[0].get('cash'))
        total_cost = 0
        for i in portfolio:
            p = i.get('combined_price')
            total_cost += p
        
        return render_template('index.html',
                                portfolio=portfolio,
                                cash=round(cash, 2),
                                total_cost=round(total_cost, 2))
    else:
        return render_template('index.html')

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    
    if request.method == "POST":
        
        time = str(datetime.now())
        
        quantity = int(request.form.get("quantity"))
        
        if quantity < 1:
            return apology("you need to provide right quantity")
        
        # get user's cash
        user_id = int(session.get('user_id'))
        
        data_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = user_id)
        
        convert = data_cash[0]
        cash = convert.get('cash')
        
        # getting stock request data
        quote = session['quote']
        
        symbol, name, price = quote['symbol'], quote['name'], float(quote['price'])
        total = price * quantity
        
        #check if user can afford so much stock
        
        if total > cash:
            return apology('you don\'t have enough money')
        
        #INSERT bought stock into history table
        db.execute('''INSERT INTO history (date, user_id, stock_name, symbol, quantity, price, deal) 
                    VALUES (:date, :user_id, :stock_name, :symbol, :quantity, :price, :deal)''',
                    date = time,
                    user_id = user_id,
                    stock_name = name,
                    symbol = symbol,
                    quantity = quantity,
                    price = total,
                    deal = 'buy')
        #update portfolio
        #check if user has bought this stock before
        symbol_check = db.execute('''SELECT symbol FROM portfolio WHERE user_id = :user_id''',
                        user_id = user_id)
    
        if [x for x in symbol_check if x['symbol'] == symbol]:
            #update stock if user has bought such shares before
            db.execute('''UPDATE portfolio 
                        SET quantity = quantity + :quantity 
                        WHERE (user_id = :user_id AND symbol = :symbol)''', 
                        quantity = quantity, user_id = user_id, symbol = symbol)
                        
        else:
            #add new shares to portfolio
            db.execute('''INSERT INTO portfolio VALUES (:user_id, :symbol, :quantity)''',
                        user_id = user_id, symbol = symbol, quantity = quantity)
            
        #update cash
        db.execute('UPDATE users SET cash = cash - :total WHERE id = :user_id', total = total, user_id = user_id)
        
        return redirect(url_for("index"))
        
    else:
       return redirect(url_for("quote"))

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    if request.method == "GET":
    
        user_id = int(session.get('user_id'))
        user_data = db.execute('''SELECT * FROM history WHERE user_id = :user_id''', user_id = user_id)
        
        if not user_data:
            return render_template('quote.html')
        
        #create lists of values for sake of returning them to F2E
        portfolio = []
        
        for i in user_data:
            #getting data from table
            date = i.get('date')
            symbol = i.get('symbol')
            name = i.get('stock_name')
            quantity = i.get('quantity')
            price = round(float(i.get('price')), 2)
            action = str(i.get('deal'))
            
            #inserting data into a list
            a_dict = {
                    'date': date, 'symbol': symbol, 
                    'name': name, 'price': price, 
                    'quantity': quantity, 'action': action
            }
            portfolio.append(a_dict)
        
        return render_template('history.html',
                                portfolio=portfolio)
    else:
        return render_template('index.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["user_name"] = request.form.get("username")

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    if request.method == "POST":
        #ensure that quote fields is not empty
        if not request.form.get("quote"):
            return apology("You need to put a valid stock name")
        #ensure that quote name is valid
        rslt = lookup(request.form.get("quote"))
        if rslt == None:    
            return apology("You need to put a valid stock name")
        else:
            session['quote'] = rslt
            return render_template("buy.html", 
                                    symbol=rslt['symbol'], 
                                    price=rslt['price'], 
                                    name=rslt['name'])
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    session.clear()
    
    if request.method == "POST":
        
        if not request.form.get("username"):
            return apology("must provide username")
        
        elif not request.form.get("password"):
            return apology("must provide password")
        
        elif not request.form.get("repeat-password"):
            return apology("passwords should match")
            
        elif not request.form.get("password") == request.form.get("repeat-password"):
            return apology("passowrds should match")
        
        rows = db.execute("SELECT username FROM users WHERE username = :username", username=request.form.get("username"))
        
        if len(rows) != 0:
            if request.form.get("username") == rows[0]["username"]:
                return apology("user with this name already exists")
                
        pwd = request.form.get("password")
        hashed_pwd = pwd_context.hash(pwd)
        
        db.execute("""INSERT INTO users (username, hash) VALUES(:username,
        :hash)""", username = request.form.get("username"), hash=hashed_pwd)
        
        rows = db.execute("SELECT id FROM users WHERE username = :username", username=request.form.get("username"))
        
        # remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["user_name"] = request.form.get("username")

        # redirect user to home page
        return redirect(url_for("index"))

        # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
        
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = int(session.get('user_id'))
    if request.method == "GET":
        
        user_data = db.execute('''SELECT * FROM portfolio WHERE user_id = :user_id''', user_id = user_id)
        
        if not user_data:
            return render_template('quote.html')
        
        #create lists of values for sake of returning them to F2E
        symbols, names, prices, quantities = [], [], [], []
        portfolio = []
        
        for i in user_data:
            #getting data from table
            symbol = i.get('symbol')
            quantity = i.get('quantity')
            """default_data.update({'item3': 3}"""
            #getting live data
            stock_data = lookup(symbol)
            name = stock_data.get('name')
            price = float(stock_data.get('price'))
            combined_price = round(price * quantity, 2)
            
            #inserting data into a list
            a_dict = {
                    'symbol': symbol, 'name': name,
                    'price': price, 'quantity': quantity, 
                    'combined_price': combined_price
            }
            portfolio.append(a_dict)
        
        #get user's cash and total cost of given shares    
        data_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = user_id)
        cash = float(data_cash[0].get('cash'))
        total_cost = 0
        for i in portfolio:
            p = i.get('combined_price')
            total_cost += p
        
        return render_template('sell.html',
                                portfolio=portfolio,
                                cash=round(cash, 2),
                                total_cost=round(total_cost, 2))
    if request.method == "POST":
        time = str(datetime.now())
        
        user_stock = db.execute("SELECT symbol, quantity FROM portfolio WHERE user_id = :user_id", user_id = user_id)
        print(user_id)
        print(user_stock)
        
        for stock in user_stock:
            symbol = str(stock.get("symbol"))
            quantity = int(stock.get("quantity"))
            to_sell = int(request.form.get(symbol))
            if to_sell < 1:
                continue
            if to_sell > quantity:
                return apology("You don't have enough of \"{}\" stocks".format(symbol))
            #update portfolio
            elif to_sell == quantity:
                db.execute('''DELETE FROM portfolio WHERE (user_id = :user_id AND symbol = :symbol)''', 
                            user_id = user_id, symbol = symbol)
            else:
                db.execute('''UPDATE portfolio 
                        SET quantity = quantity - :quantity 
                        WHERE (user_id = :user_id AND symbol = :symbol)''', 
                        quantity = to_sell, user_id = user_id, symbol = symbol)
        
            #update history
            #getting stock request data
            quote = lookup(symbol)
            name, price = quote['name'], float(quote['price'])
            total = price * to_sell
            #INSERT bought stock into history table
            db.execute('''INSERT INTO history (date, user_id, stock_name, symbol, quantity, price, deal) 
                        VALUES (:date, :user_id, :stock_name, :symbol, :quantity, :price, :deal)''',
                        date = time,
                        user_id = user_id,
                        stock_name = name,
                        symbol = symbol,
                        quantity = to_sell,
                        price = total,
                        deal = 'sell')

            #update cash
            db.execute('UPDATE users SET cash = cash + :total WHERE id = :user_id', total = total, user_id = user_id)
            
            return redirect(url_for("sell"))