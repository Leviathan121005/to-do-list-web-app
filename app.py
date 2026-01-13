import os
import json

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session.__init__ import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from helpers import login_required

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use system file
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 library to use SQLite database
db = SQL("sqlite:///project.db")


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    lists = db.execute("SELECT * FROM data WHERE id = ?", session["user_id"])
    for x in range(len(lists)):
        lists[x]["progress"] = db.execute(
            "SELECT COUNT(*) FROM done WHERE id = ? AND title = ? AND done = 1",
            session["user_id"],
            lists[x]["title"],
        )[0]["COUNT(*)"]
        lists[x]["from"] = db.execute(
            "SELECT COUNT(*) FROM done WHERE id = ? AND title = ?",
            session["user_id"],
            lists[x]["title"],
        )[0]["COUNT(*)"]
        lists[x]["percentage"] = round(100 * lists[x]["progress"] / lists[x]["from"])

    return render_template("index.html", lists=lists)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register new user"""
    if request.method == "GET":
        return render_template("register.html")

    else:
        # Get user input
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Check user input
        if not username or not password:
            return render_template(
                "error.html", message="Fill username and password", code=400
            )

        # Check username availability in database
        if db.execute("SELECT * FROM users WHERE username = ?", username):
            return render_template(
                "error.html", message="Username unavailable", code=400
            )

        # Password confirmation
        if password != confirmation:
            return render_template(
                "error.html", message="Confirmation differs from password"
            )

        # Insert data to project.db
        db.execute(
            "INSERT INTO users (username, hash) VALUES(?, ?)",
            username,
            generate_password_hash(password),
        )

        return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template(
                "error.html", message="Must provide username", code=400
            )

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template(
                "error.html", message="Must provide password", code=400
            )

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return render_template(
                "error.html", message="Invalid username and/or password", code=400
            )

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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


@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "GET":
        listinfo = [None]
        tasks = [None]

        return render_template("create.html", listinfo=listinfo, tasks=tasks)

    else:
        # Get list's data
        title = request.form.get("title").strip()

        if db.execute(
            "SELECT * FROM data WHERE id = ? AND title = ?", session["user_id"], title
        ):
            return render_template(
                "error.html", message="Username unavailable", code=400
            )

        subtext = request.form.get("subtext")
        count = int(request.form.get("count"))
        indicator = request.form.get("indicator")

        # Save image file or link into static folder
        if indicator == "image":
            image = request.files["image"]
            if image:
                filename = "{}{}{}".format(
                    session["user_id"], title, secure_filename(image.filename)
                )
                image.save("static/images/" + filename)
                db.execute(
                    "INSERT INTO data (id, title, subtext, image) VALUES (?, ?, ?, ?)",
                    session["user_id"],
                    title,
                    subtext,
                    filename,
                )
            else:
                db.execute(
                    "INSERT INTO data (id, title, subtext) VALUES (?, ?, ?)",
                    session["user_id"],
                    title,
                    subtext,
                )
        elif indicator == "link":
            link = request.form.get("link")
            if link:
                db.execute(
                    "INSERT INTO data (id, title, subtext, image) VALUES (?, ?, ?, ?)",
                    session["user_id"],
                    title,
                    subtext,
                    link,
                )
            else:
                db.execute(
                    "INSERT INTO data (id, title, subtext) VALUES (?, ?, ?)",
                    session["user_id"],
                    title,
                    subtext,
                )

        # Get list's task list
        for number in range(count):
            task = request.form.get("task" + str(number + 1))
            db.execute(
                "INSERT INTO done (id, title, number, task, done) VALUES (?, ?, ?, ?, ?)",
                session["user_id"],
                title,
                number + 1,
                task,
                0,
            )

        return redirect("/")


@app.route("/list/<title>", methods=["GET", "POST"])
@login_required
def list(title):
    if request.method == "GET":
        tasks = []

        listinfo = db.execute(
            "SELECT * FROM data WHERE id = ? AND title = ?", session["user_id"], title
        )

        tasks = db.execute(
            "SELECT * FROM done WHERE id = ? AND title = ?", session["user_id"], title
        )

        return render_template("list.html", listinfo=listinfo, tasks=tasks)


@app.route("/check", methods=["POST"])
@login_required
def check():
    position = request.get_json()

    db.execute(
        "UPDATE done SET done = 1 WHERE id = ? AND title = ? AND number = ?",
        session["user_id"],
        position[0],
        position[1],
    )
    return "", 200


@app.route("/uncheck", methods=["POST"])
@login_required
def uncheck():
    position = request.get_json()

    db.execute(
        "UPDATE done SET done = 0 WHERE id = ? AND title = ? AND number = ?",
        session["user_id"],
        position[0],
        position[1],
    )
    return "", 200


@app.route("/edit/<title>", methods=["GET", "POST"])
@login_required
def edit(title):
    if request.method == "GET":
        # Get data to be edited
        listinfo = db.execute(
            "SELECT * FROM data WHERE id = ? AND title = ?", session["user_id"], title
        )
        tasks = db.execute(
            "SELECT * FROM done WHERE id = ? AND title = ?", session["user_id"], title
        )

        return render_template("create.html", listinfo=listinfo, tasks=tasks)

    if request.method == "POST":
        title2 = request.form.get("title").strip()
        subtext = request.form.get("subtext")

        # Update new data relentlessly
        db.execute(
            "DELETE FROM done WHERE id = ? AND title = ?", session["user_id"], title
        )
        db.execute(
            "UPDATE data SET title = ?, subtext = ? WHERE id = ? AND title = ?",
            title2,
            subtext,
            session["user_id"],
            title,
        )

        # Check if image is removed
        signal = request.form.get("signal")
        if signal == "true":
            db.execute(
                "UPDATE data SET image = '' WHERE id = ? AND title = ?",
                session["user_id"],
                title,
            )
        # Edit image
        indicator = request.form.get("indicator")
        if indicator == "image":
            image = request.files["image"]
            if image:
                filename = "{}{}{}".format(
                    session["user_id"], title2, secure_filename(image.filename)
                )
                image.save("static/images/" + filename)
                db.execute(
                    "UPDATE data SET image = ? WHERE id = ? AND title = ?",
                    filename,
                    session["user_id"],
                    title2,
                )
        elif indicator == "link":
            link = request.form.get("link")
            if link:
                db.execute(
                    "UPDATE data SET image = ? WHERE id = ? AND title = ?",
                    link,
                    session["user_id"],
                    title2,
                )

        # Recount number of tasks
        count = int(request.form.get("count"))

        # Get list's task list
        for number in range(count):
            task = request.form.get("task" + str(number + 1))
            db.execute(
                "INSERT INTO done (id, title, number, task, done) VALUES (?, ?, ?, ?, ?)",
                session["user_id"],
                title2,
                number + 1,
                task,
                0,
            )

        return redirect("/")


@app.route("/reset/<title>", methods=["GET"])
def reset(title):
    # Reset all done boolean value to false
    db.execute(
        "UPDATE done SET done = 0 WHERE id = ? AND title = ?", session["user_id"], title
    )

    return "", 200


@app.route("/trash/<title>", methods=["GET"])
def trash(title):
    # Delete list
    db.execute("DELETE FROM data WHERE id = ? AND title = ?", session["user_id"], title)
    db.execute("DELETE FROM done WHERE id = ? AND title = ?", session["user_id"], title)

    return "", 200