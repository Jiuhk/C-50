import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL(os.getenv("DATABASE_URL"))

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Get stocks profile
    stocks = db.execute("SELECT symbol, SUM(shares) AS shares FROM history WHERE user_id = ? GROUP BY symbol", session["user_id"])
    stock_total = 0

    for stock in stocks:
        stock["price"] = lookup(stock["symbol"])["price"]
        stock["name"] = lookup(stock["symbol"])["name"]
        stock["total"] = stock["price"] * stock["shares"]
        stock_total += stock["total"]

    # Get cash
    cash_list = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = cash_list[0]["cash"]

    # Get total value
    total = stock_total + cash

    return render_template("index.html", stocks=stocks, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # Query cash
    cash_list = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = cash_list[0]["cash"]

    # User reached route via POST (buying)
    if request.method == "POST":

        # Store input in variables
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Ensure symbol input not blank
        if not symbol or not shares:
            return apology("must provide symbol/shares", 403)

        # Turn shares into interger
        shares = int(shares)

        # Ensure symbol exists
        if not lookup(symbol):
            return apology("symbol not exists", 403)
        else:
            stock_price = lookup(symbol)["price"]
            stock_name = lookup(symbol)["name"]
            stock_symbol = lookup(symbol)["symbol"]

        # Build database if not exists
        db.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER, user_id INTEGER, symbol TEXT NOT NULL, stock_price NUMERIC NOT NULL, shares INTEGER NOT NULL, total_price NUMERIC NOT NULL, timestamp TEXT NOT NULL, PRIMARY KEY(id))")

        # Check if enough cash
        total_price = stock_price * shares
        if total_price > cash:
            return apology("not enough cash", 403)

        # Write into history
        # db.execute("INSERT INTO history (user_id, symbol, stock_price, shares, total_price, timestamp) VALUES (?, ?, ?, ?, ?, current_timestamp)", session["user_id"], symbol, stock_price, shares, total_price)
        # db.execute("INSERT INTO history (id, user_id, symbol, stock_price, shares, total_price, timestamp) VALUES (111, 1, 'aa', 1, 1, 1, '123')")
        db.execute("CREATE SEQUENCE test_id_seq START 10; ALTER TABLE test ALTER id SET DEFAULT NEXTVAL('test_id_seq');")
        db.execute("INSERT INTO test (user_id) VALUES (3)")
##################

        # Update cash
        cash = cash - total_price
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])

        return redirect("/")

    else:
        return render_template("buy.html", cash=cash)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])

    for history_item in history:
        if history_item["shares"] < 0:
            history_item["type"] = "Sell"
            history_item["shares"] = 0 - history_item["shares"]
        else:
            history_item["type"] = "Buy"
            history_item["total_price"] = 0 - history_item["total_price"]

    return render_template("history.html", history=history)


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
        session["user_id"] = rows[0]["id"]

        # Open new quotes list for the user
        session["quotes"] = []

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

        try:

            # Clear button
            if request.form['submit_button'] == "clear":
                session["quotes"] = []
                return render_template("quote.html", quotes=session["quotes"])

        except:

            # Lookup the input
            symbol = request.form.get('symbol')
            quote = lookup(symbol)
            if quote and quote not in session["quotes"]:
                session["quotes"].append(quote)

            # Return the quote
            return render_template("quote.html", quotes=session["quotes"])

    else:
        try:
            return render_template("quote.html", quotes=session["quotes"])
        except:
            session["quotes"] = []
            return render_template("quote.html", quotes=session["quotes"])


@app.route("/register", methods=["GET", "POST"])
def register():

    """Register user"""
    if request.method == 'POST':

        # Get values and set variables
        username = request.form.get('username')
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)

        # Ensure username did not exist
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) != 0:
            return apology("username already exists", 403)

        # Ensure passwords were submitted
        if not password or not password_confirm:
            return apology("must provide password", 403)

        # Ensure passwords match
        if password != password_confirm:
            return apology("passwords don't match", 403)

        # Store in the database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, generate_password_hash(password))

        # Auto log-in
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        session["user_id"] = rows[0]["id"]

        # Redirect to homepage
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Get stock profile
    stocks = db.execute("SELECT DISTINCT symbol FROM history WHERE user_id = ?", session["user_id"])

    if request.method == "POST":

        # Store form
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Turn shares an int
        if shares:
            shares = int(shares)

        # Ensure shares owned
        shares_owned = db.execute("SELECT SUM(shares) AS shares FROM history WHERE user_id = ? AND symbol = ? GROUP BY symbol", session["user_id"], symbol)
        if not shares_owned[0]["shares"] >= shares:
            return apology("Not enough shares", 403)

        else:

            # Write into history
            stock_price = lookup(symbol)["price"]
            total_price = stock_price * shares
##################
            # db.execute("INSERT INTO history (user_id, symbol, stock_price, shares, total_price, timestamp) VALUES (?, ?, ?, ?, ?, current_timestamp)", session["user_id"], symbol, stock_price, (0 - shares), total_price)
##################
            # Update users
            cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
            cash_new = cash[0]["cash"] + total_price
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_new, session["user_id"])


            return redirect("/")


    else:
        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
