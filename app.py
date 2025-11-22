from flask import Flask, request, jsonify
import os, json, time

DB = "/opt/render/project/src/users.json"  # Render'ın gerçek path'i

app = Flask(__name__)

# Kullanıcı veritabanı yoksa oluştur
if not os.path.exists(DB):
    with open(DB, "w") as f:
        json.dump([], f)

def load_users():
    with open(DB, "r") as f:
        return json.load(f)

def save_users(data):
    with open(DB, "w") as f:
        json.dump(data, f, indent=4)

@app.route("/api/register", methods=["POST"])
def register_user():
    data = request.json
    users = load_users()

    # Kullanıcı adı veya email zaten var mı?
    for u in users:
        if u["username"] == data["username"]:
            return jsonify({"ok": False, "msg": "username_exists"})
        if u["email"] == data["email"]:
            return jsonify({"ok": False, "msg": "email_exists"})

    data["id"] = int(time.time())
    data["last_seen"] = 0
    data["threads"] = 0
    data["last_hashrate"] = 0

    users.append(data)
    save_users(users)

    return jsonify({"ok": True, "msg": "registered"})

@app.route("/api/login", methods=["POST"])
def login_user():
    data = request.json
    users = load_users()

    for u in users:
        if u["username"] == data["user"] or u["email"] == data["user"]:
            if u["password"] == data["password"]:
                u["last_seen"] = time.time()
                save_users(users)
                return jsonify({"ok": True, "msg": "login_ok"})

    return jsonify({"ok": False, "msg": "login_fail"})

@app.route("/api/update_stats", methods=["POST"])
def update_stats():
    data = request.json
    users = load_users()

    for u in users:
        if u["username"] == data["username"]:
            u["last_hashrate"] = data["hashrate"]
            u["threads"] = data["threads"]
            u["last_seen"] = time.time()

    save_users(users)
    return jsonify({"ok": True})

@app.route("/")
def home():
    return "Goblin Server Online"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

