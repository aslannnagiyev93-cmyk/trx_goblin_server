from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

# --- VERİ DOSYASI ---
DATA_FILE = "/home/leon/trx_goblin/app/users.json"
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)


def load_users():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_users(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# =========================================
#   KULLANICI LİSTELEME  (ADMIN PANEL)
# =========================================
@app.route("/get_users", methods=["GET"])
def get_users():
    users = load_users()
    return jsonify({"status": "ok", "users": users})


# =========================================
#   MINER İSTATİSTİK GÜNCELLEME
# =========================================
@app.route("/update_stats", methods=["POST"])
def update_stats():
    try:
        data = request.get_json()
        username = data["username"]
        hashrate = data["hashrate"]
        threads = data["threads"]

        users = load_users()
        found = False

        for u in users:
            if u["username"] == username:
                u["last_hashrate"] = hashrate
                u["threads"] = threads
                found = True

        if not found:
            return jsonify({"status": "error", "message": "user not found"})

        save_users(users)
        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# =========================================
#   ROOT TEST
# =========================================
@app.route("/")
def home():
    return "Goblin Server Çalışıyor!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
