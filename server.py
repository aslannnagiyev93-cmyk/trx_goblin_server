from flask import Flask, request, jsonify

app = Flask(__name__)

# Basit bellek içi kullanıcı listesi (sonra gerçek DB bağlarız)
users = []

@app.route("/")
def home():
    return "TRX Goblin Server Çalışıyor!"

@app.route("/get_users", methods=["GET"])
def get_users():
    return jsonify(users)

@app.route("/update_stats", methods=["POST"])
def update_stats():
    data = request.json

    username = data.get("username")
    hashrate = data.get("hashrate")
    threads = data.get("threads")

    if not username:
        return jsonify({"error": "username missing"}), 400

    # Kullanıcı var mı kontrol et
    found = False
    for u in users:
        if u["username"] == username:
            u["hashrate"] = hashrate
            u["threads"] = threads
            found = True
            break

    # Yoksa yeni ekle
    if not found:
        users.append({
            "username": username,
            "hashrate": hashrate,
            "threads": threads
        })

    return jsonify({"status": "ok"})
    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

