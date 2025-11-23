from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "Goblin Miner Server ÇALIŞIYOR!"

@app.route("/user/register", methods=["POST"])
def register():
    data = request.json
    return jsonify({"status": "ok", "message": "kayıt alındı", "data": data})

@app.route("/user/stats", methods=["POST"])
def stats():
    data = request.json
    return jsonify({"status": "ok", "message": "istatistik kaydedildi", "data": data})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

