from flask import Flask, jsonify, send_from_directory, request
import base64, binascii, requests, urllib3, json, threading, time
from urllib.parse import urljoin
import pandas as pd
from threading import Lock

# --- NEW: Import waitress server ---
from waitress import serve

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, static_url_path='', static_folder='static')

READER_IP = "192.168.103.208"
USERNAME = "root"
PASSWORD = "impinj"
PRESET = "Raman01"
EXCEL_PATH = r"C:\Users\Lab220301\Pictures\product details.xlsx"

# Tag storage
scanning_enabled = False
tag_lock = Lock()
epc_tags = set()

# Load Excel
try:
    df = pd.read_excel(EXCEL_PATH)
    df.fillna("", inplace=True)
    product_data = df.set_index("Asset _ID").to_dict(orient="index")
except Exception as e:
    print(f"[Excel Load Error] {e}")
    product_data = {}

def decode_epc(epc_base64url):
    padding = '=' * (-len(epc_base64url) % 4)
    epc_base64 = epc_base64url.replace('-', '+').replace('_', '/') + padding
    try:
        epc_bytes = base64.b64decode(epc_base64)
        return binascii.hexlify(epc_bytes).decode('utf-8').upper()
    except:
        return None

def background_scan():
    """ Continuously scan and store tags """
    base = f"https://{READER_IP}"

    while True:
        try:
            requests.post(urljoin(base, 'api/v1/profiles/inventory/presets/{}/start'.format(PRESET)),
                          auth=(USERNAME, PASSWORD), verify=False, timeout=10)

            res = requests.get(urljoin(base, 'api/v1/data/stream'),
                                   auth=(USERNAME, PASSWORD),
                                   headers={'Accept': 'application/json'},
                                   verify=False, stream=True, timeout=20)

            for line in res.iter_lines():
                if line:
                    raw = line.decode('utf-8')
                    data = json.loads(raw).get('tagInventoryEvent', {})
                    epc_encoded = data.get('epc')

                    if epc_encoded:
                        epc = decode_epc(epc_encoded)
                        if epc:
                            with tag_lock:
                                epc_tags.add(epc)
        except Exception as e:
            print(f"[Background Stream Error] {e}")
            time.sleep(2)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/start-scan', methods=['POST'])
def start_scan():
    global scanning_enabled
    with tag_lock:
        epc_tags.clear()  # Clear old tags
    scanning_enabled = True
    return jsonify({"status": "started"})

@app.route('/stop-scan', methods=['POST'])
def stop_scan():
    global scanning_enabled
    scanning_enabled = False
    return jsonify({"status": "stopped"})

@app.route('/inventory')
def inventory():
    if not scanning_enabled:
        return jsonify([])

    with tag_lock:
        tags = list(epc_tags)

    enriched = []
    for epc in tags:
        product = product_data.get(epc)
        enriched.append({
            "epc": epc,
            "name": f"{product['STYLE']} - {product['COLOR']} ({product['SIZE']})" if product else "Unknown",
            "price": product["PRICE"] if product else 0,
            "url": product["URL"].strip() if product and "URL" in product and product["URL"] else ""
        })
    return jsonify(enriched)

# --- MODIFIED: Use waitress instead of app.run() ---
if __name__ == '__main__':
    # Start scanning in background thread
    threading.Thread(target=background_scan, daemon=True).start()
    
    # This will run the waitress server, which is safe for windowed executables
    serve(app, host="0.0.0.0", port=8000)