from flask import Flask, jsonify, send_from_directory, request
import pandas as pd
from threading import Lock
import os # Import os module to handle file paths
from waitress import serve # Only for local testing

app = Flask(__name__, static_url_path='', static_folder='static')

# --- IMPORTANT: Configuration for the Excel file on Render ---
# Ensure your 'product details.xlsx' file is uploaded to the 'static' directory
EXCEL_FILENAME = 'product details.xlsx'
EXCEL_PATH_RENDER = os.path.join(app.static_folder, EXCEL_FILENAME)

# --- Tag storage on the Render server ---
epc_tags = set()
tag_lock = Lock()

# Load Excel data from the file that will be uploaded to Render
try:
    if os.path.exists(EXCEL_PATH_RENDER):
        df = pd.read_excel(EXCEL_PATH_RENDER)
        df.fillna("", inplace=True)
        product_data = df.set_index("Asset _ID").to_dict(orient="index")
        print(f"[Excel Load Success] Loaded {len(product_data)} product entries.")
    else:
        print(f"[Excel Load Warning] Excel file not found at: {EXCEL_PATH_RENDER}. Product data will be empty.")
        product_data = {}
except Exception as e:
    print(f"[Excel Load Error] Failed to load Excel file: {e}")
    product_data = {}

# --- Main route for the web interface ---
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# --- API endpoint to receive tags from the local scanner ---
@app.route('/api/tag_scan', methods=['POST'])
def receive_tag():
    try:
        data = request.get_json()
        tag_id = data.get('tag_id')
        
        if tag_id:
            with tag_lock:
                epc_tags.add(tag_id)
            print(f"Received new tag ID from local scanner: {tag_id}")
            return jsonify({"status": "success", "message": f"Tag {tag_id} received."}), 200
        else:
            print("[Receive Tag Error] No tag_id provided in the request.")
            return jsonify({"status": "error", "message": "No tag_id provided."}), 400
    except Exception as e:
        print(f"[Receive Tag Error] Failed to process incoming tag: {e}")
        return jsonify({"status": "error", "message": f"Internal server error: {e}"}), 500

# --- Route to get the current inventory of scanned tags ---
@app.route('/inventory')
def inventory():
    with tag_lock:
        tags = list(epc_tags)

    enriched = []
    for epc in tags:
        product = product_data.get(epc)
        enriched.append({
            "epc": epc,
            "name": f"{product['STYLE']} - {product['COLOR']} ({product['SIZE']})" if product else "Unknown Product",
            "price": product["PRICE"] if product else 0,
            "url": product["URL"].strip() if product and "URL" in product and product["URL"] else ""
        })
    return jsonify(enriched)

# --- Routes for controlling scanning (now primarily for clearing tags on the server) ---
@app.route('/start-scan', methods=['POST'])
def start_scan():
    with tag_lock:
        epc_tags.clear()
    print("Server: Cleared collected tags.")
    return jsonify({"status": "started_and_tags_cleared", "message": "Server tag list cleared. Local scanner should be running."})

@app.route('/stop-scan', methods=['POST'])
def stop_scan():
    print("Server: Received stop scan request (local scanner controls actual scanning).")
    return jsonify({"status": "stopped_locally", "message": "Server is ready, but local scanner controls actual scanning."})

# --- Entry point for the Flask application ---
if __name__ == '__main__':
    print("Starting Flask app with Waitress server for local development/testing...")
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
