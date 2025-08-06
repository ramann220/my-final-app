import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

reader_url = "https://192.168.103.208/api/v1"
username = "root"
password = "impinj"

endpoint = f"{reader_url}/profiles/inventory/presets"

response = requests.get(
    endpoint,
    auth=(username, password),
    verify=False
)

if response.status_code == 200:
    presets = response.json()
    print("Available presets on reader:")
    for preset_name in presets:
        print(f" - {preset_name}")
else:
    print(f"Failed to get presets: {response.status_code} - {response.text}")
