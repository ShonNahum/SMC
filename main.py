from flask import Flask, render_template
import yaml
import requests
import sys

app = Flask(__name__)

# Load config from env.yaml
with open('env.yaml', 'r') as f:
    config = yaml.safe_load(f)

backend_api_url = config['backend_api_url']

# Check backend API connectivity before starting server
def check_backend_api(url):
    try:
        # Ping the backend API base URL (GET request)
        r = requests.get(url, timeout=3)
        r.raise_for_status()
        print(f"Connected successfully to backend API at {url}")
    except requests.RequestException as e:
        print(f"Failed to connect to backend API at {url}: {e}")
        sys.exit(1)  # Exit program with error


@app.route('/')
def index():
    return render_template('index.html', backend_api_url=backend_api_url)

if __name__ == '__main__':
    check_backend_api(backend_api_url)  # run connectivity check before app.run()
    app.run(port=5000)
