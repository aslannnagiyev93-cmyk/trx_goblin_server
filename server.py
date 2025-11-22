from flask import Flask, request, jsonify
import json
import os

DB = "users.json"

app = Flask(__name__)


# ------------------ DB OKU/YAZ ------------------

def load_users():
    if not os.path.exists(DB):
        with open(DB, "w") as f:
            json.dump([], f)
    with open(DB, "r") as f:
        return json.load(f)


def save_users(users):
    with open(DB, "w") as f:
        json.dump(users, f, indent=4)


# ------------------ API: KULLANICI KAYDET ------------------

@app.post("/register")
def register():
    data = request.json

    firstname = data.get("firstname")
    lastname = data.get("lastname")
    email = data.get("email")
    username = data.get("username")
    password = data.get("password")

    if not all([firstname, lastname, email, username, password]):
        return jsonify({"ok": False, "msg": "Eksik bilgi"}), 400

    users = load_users()

    # benzersiz email & username kontrol
    for u in users:
        if u["email"] == email:
            return jsonify({"ok": False, "msg": "Bu e-posta kayıtlı"}), 400
        if u["username"] == username:
            return jsonify({"ok": False, "msg": "Bu kullanıcı adı kayıtlı"}), 400

    new_user = {
        "id": len(users) + 1,
        "firstname": firstname,
        "lastname": lastname,
        "email": email,
        "username": username,
        "password": password,   # ileride hash yapacağız
        "threads": 0,
        "last_hashrate": 0,
        "last_seen": 0
    }

    users.append(new_user)
    save_users(users)

    return jsonify({"ok": True, "msg": "Kayıt başarılı"}), 200


# ------------------ API: GİRİŞ ------------------

@app.post("/login")
def login():
    data = request.json

    user = data.get("username")
    pw = data.get("password")

    users = load_users()

    for u in users:
        if (u["username"] == user or u["email"] == user) and u["password"] == pw:
            return jsonify({"ok": True, "user": u})

    return jsonify({"ok": False, "msg": "Giriş hatalı"}), 400


# ------------------ API: İSTATİSTİK GÜNCELLE ------------------

@app.post("/update")
def update_stats():
    data = request.json
    username = data.get("username")
    hashrate = data.get("hashrate")
    threads = data.get("threads")

    users = load_users()

    for u in users:
        if u["username"] == username:
            u["last_hashrate"] = hashrate
            u["threads"] = threads
            u["last_seen"] = int(__import__("time").time())
            save_users(users)
            return jsonify({"ok": True})

    return jsonify({"ok": False}), 400


# ------------------ API: TÜM KULLANICILARI VER ------------------

@app.get("/users")
def get_users():
    return jsonify(load_users())


# ------------------ MAIN ------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
