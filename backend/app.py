from flask import Flask, jsonify, request

app = Flask(__name__)
latest = {}
history = {}

@app.post("/api/telemetry")
def telemetry():
    r = request.get_json()
    uid = r["unit_id"]
    latest[uid] = r
    history.setdefault(uid, []).append(r)
    history[uid] = history[uid][-300:]
    return jsonify(ok=True)

@app.get("/api/units")
def units():
    return jsonify(list(latest.values()))

@app.get("/api/history/<uid>")
def hist(uid):
    return jsonify(history.get(uid, []))

if __name__ == "__main__":
    app.run(port=5000)