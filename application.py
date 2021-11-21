import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, ok

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set

if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # user cash balance
    balance = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
    
    # update 'tickers' table with the current prices
    selection = db.execute("SELECT symbol FROM tickers")

    for item in selection:
        stockInfo = lookup(item['symbol'])
        price = stockInfo['price']
        symbol = item['symbol']

        db.execute("UPDATE tickers SET price = ? WHERE symbol = ?", price, symbol)
        
    # ======= temporary code for debagging ==========
    # return ok("this is break point")
    
    # select portfolio data
    selection = db.execute(
        "SELECT portfolio.symbol, tickers.name, portfolio.shares, tickers.price, portfolio.shares * tickers.price AS 'total' FROM portfolio LEFT JOIN tickers ON portfolio.symbol = tickers.symbol WHERE portfolio.user_id = :user_id", user_id=session["user_id"])

    cash = balance[0]['cash']
    total = cash
    for item in selection:
        total += item["total"]
        
    return render_template("index.html", cash=usd(cash), data=selection, total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Ensure stockID was submitted
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol")
        symbol = symbol.upper()      
        
        # Ensure shares was submited            
        shares_str = request.form.get("shares")     
        if not shares_str:
            return apology("missing shares")
            
        if not shares_str.isdigit():
            return apology("shares should be digit")
            
        shares = float(shares_str)   
        if shares - int(shares) != 0:
            return apology("shares should be solid digit")
        
        if shares < 1:
            return apology("shares should be > 0")
        
        # Ensure symbol is correct
        stockInfo = lookup(symbol)
        if not stockInfo:
            return apology("Invalid symbol", 400)
            
        # Ensure user has enough money
        balance = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        
        if balance[0]['cash'] < stockInfo['price']*shares:
            return apology("Not enough money")
        # update available cash amount for user
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id ",
                   cash=balance[0]['cash'] - stockInfo['price']*shares, user_id=session["user_id"])
        
        # Ensure 'symbol' is in the 'tickers' table and update 'tickers' table with current price
        cursor = db.execute("SELECT symbol FROM tickers WHERE symbol = :symbol", symbol=symbol)
        if not cursor:
            db.execute("INSERT INTO tickers (symbol, name, price) VALUES (:symbol, :name, :price)",
                       symbol=symbol, name=stockInfo['name'], price=stockInfo['price'])
        else:
            db.execute("UPDATE tickers SET price = :price WHERE symbol = :symbol", symbol=symbol, price=stockInfo['price'])
        
        # keep transaction log
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)",
                   user_id=session["user_id"], symbol=symbol, shares=shares, price=stockInfo['price'])
        
        # update portfiolio
        oldShares = db.execute("SELECT shares FROM portfolio WHERE symbol = :symbol AND user_id = :user_id",
                               symbol=symbol, user_id=session["user_id"])
        if not oldShares:
            db.execute("INSERT INTO portfolio (user_id, symbol, shares) VALUES (:user_id, :symbol, :shares)",
                       user_id=session["user_id"], symbol=symbol, shares=shares)
        else:
            db.execute("UPDATE portfolio SET shares = :shares WHERE symbol = :symbol AND user_id = :user_id",
                       shares=oldShares[0]['shares']+shares, symbol=symbol, user_id=session["user_id"])
        
        # Flash message and redirect user to home page
        flash('Bought !')
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    selection = db.execute("SELECT symbol, shares, price, created FROM transactions WHERE user_id = :user", user=session["user_id"])
    return render_template("history.html", data=selection)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        #session["user_id"] = rows[0]["id"]
        session["user_id"] = rows[0].get("id")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol", 400)
        
        stockInfo = lookup(symbol)
        try:
            return render_template("quoted.html", text=stockInfo["name"]+" ("+stockInfo['symbol']+")", price=usd(stockInfo['price']))
        except:
            return apology("invalid symbol", 400)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)
            
        # Ensure password was submitted
        elif not password:
            return apology("missing password", 400)
            
        # Ensure passwords are same
        elif password != confirmation:
            return apology("passwords don't macth", 400)      

        # Ensure username are available
        if len(db.execute("SELECT * FROM users WHERE username = :username", username=username)) != 0:
            return apology("username is not available", 400)
        
        # Create new user
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",
                   username, generate_password_hash(password))
        
        # Remember which user has logged in
        #rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        #session["user_id"] = rows[0]["id"]
        
       # Flash message and redirect user to home page
        flash('Registered !')
        return redirect("/")
    else:        
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # choose all tickers symbols available in the users portfolio to give them in to sell.html template
    selection = db.execute("SELECT symbol FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])
    options = []
    for pair in selection:
        options.append(pair['symbol'])
        
    if request.method == "POST":
        # Ensure stockID was submitted
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol")
        symbol = symbol.upper()      

        # Ensure shares was submited            
        shares_str = request.form.get("shares")    
        if not shares_str:
            return apology("missing shares")
        shares = int(shares_str)

        # Ensure symbol is correct
        stockInfo = lookup(symbol)
        if not stockInfo:
            return apology("Invalid symbol", 400)

        balance = db.execute("SELECT cash FROM users WHERE id = :user_id ", user_id=session["user_id"])

        # Ensure user has enough shares
        portfolio = db.execute("SELECT shares FROM portfolio WHERE user_id = :user_id AND symbol = :symbol",
                               user_id=session["user_id"], symbol=symbol)
        if not portfolio:
            return apology("You have no shares of this company", 400)
            
        if portfolio[0]['shares'] < shares:
            return apology("Not enough shares to sell")
            
        # update available cash amount for user
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id ",
                   cash=balance[0]['cash'] + stockInfo['price']*shares, user_id=session["user_id"])
        
        # update 'tickers' table with current price
        db.execute("UPDATE tickers SET price = :price WHERE symbol = :symbol",
                   symbol=symbol, price=stockInfo['price'])
        
        # keep transaction log
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)",
                   user_id=session["user_id"], symbol=symbol, shares=-shares, price=stockInfo['price'])
        
        # update portfiolio
        newShares = portfolio[0]['shares'] - shares
        if newShares == 0:
            db.execute("DELETE FROM portfolio WHERE symbol = :symbol AND user_id = :user_id",
                       symbol=symbol, user_id=session["user_id"])
        else:
            db.execute("UPDATE portfolio SET shares = :shares WHERE symbol = :symbol AND user_id = :user_id",
                       shares=portfolio[0]['shares'] - shares, symbol=symbol, user_id=session["user_id"])
        
        # Flash message and redirect user to home page
        flash('Sold !')
        return redirect("/")

    else:
        return render_template("sell.html", options=options)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
