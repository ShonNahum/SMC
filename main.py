from flask import Flask, render_template, Response
import yaml
import requests
import sys

# OpenTelemetry packages
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry import metrics
from prometheus_client import generate_latest

app = Flask(__name__)

# Load config from env.yaml
with open('env.yaml', 'r') as f:
    config = yaml.safe_load(f)

backend_api_url = config['backend_api_url']
port = config['port']

# ✅ Setup OpenTelemetry metrics
reader = PrometheusMetricReader()
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter(__name__)
ping_counter = meter.create_counter(
    name="backend_ping_attempts",
    unit="1",
    description="Number of backend API connectivity checks"
)

# Check backend API connectivity before starting server
def check_backend_api(url):
    try:
        r = requests.get(url, timeout=3)
        r.raise_for_status()
        ping_counter.add(1, {"status": "success"})
        print(f"Connected successfully to backend API at {url}")
    except requests.RequestException as e:
        ping_counter.add(1, {"status": "failure"})
        print(f"Failed to connect to backend API at {url}: {e}")
        sys.exit(1)


@app.route('/')
def index():
    return render_template('index.html', backend_api_url=backend_api_url)

# ✅ Expose /metrics endpoint
@app.route('/metrics')
def metrics_endpoint():
    return Response(generate_latest(), mimetype="text/plain")


if __name__ == '__main__':
    check_backend_api(backend_api_url)
    app.run(port=port)
