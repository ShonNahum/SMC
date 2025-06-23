from flask import Flask, render_template, request, jsonify, Response
import yaml
import logging
from logging_loki.handlers import LokiHandler
import requests
import sys
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# OpenTelemetry imports for tracing
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

app = Flask(__name__)

# Load config from env.yaml
with open('env.yaml', 'r') as f:
    config = yaml.safe_load(f)

backend_api_url = config['backend_api_url']
port = int(config['port'])
loki_url = config['loki_url']
jaeger_host = config.get('jaeger_host', 'localhost')  # add jaeger_host in your env.yaml if needed
jaeger_port = config.get('jaeger_port', 4317)

# Set up logging
logger = logging.getLogger("flask-app")
logger.setLevel(logging.INFO)
logger.propagate = False

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Loki handler
loki_handler = LokiHandler(
    url=loki_url,
    tags={"app": "smc"},
    version="1"
)
loki_handler.setFormatter(formatter)
logger.addHandler(loki_handler)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# === OpenTelemetry Tracing Setup ===
trace.set_tracer_provider(
    TracerProvider(resource=Resource.create({SERVICE_NAME: "SMC-Application"}))
)
otlp_exporter = OTLPSpanExporter(
    endpoint=f"{jaeger_host}:{jaeger_port}",
    insecure=True
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)
tracer = trace.get_tracer(__name__)

# Instrument Flask and requests (so outgoing HTTP calls are traced)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/store', methods=['POST'])
def store_key_value():
    with tracer.start_as_current_span("store_key_value"):
        data = request.get_json()
        if not data or 'key' not in data or 'value' not in data:
            logger.warning("❌ Invalid POST: missing key or value")
            return jsonify({"error": "Missing key or value"}), 400

        key = data['key']
        value = data['value']
        logger.info(f"📝 Storing: key='{key}', value='{value}'")

        try:
            res = requests.post(backend_api_url, json={"key": key, "value": value})
            res.raise_for_status()
            return jsonify(res.json()), res.status_code
        except Exception as e:
            logger.error(f"❌ Error forwarding to backend: {e}")
            return jsonify({"error": "Backend error"}), 500

@app.route('/store/<key>', methods=['GET'])
def get_value(key):
    with tracer.start_as_current_span("get_value"):
        logger.info(f"🔍 Fetching key='{key}'")
        try:
            res = requests.get(f"{backend_api_url}/{key}")
            return jsonify(res.json()), res.status_code
        except Exception as e:
            logger.error(f"❌ Error getting key='{key}': {e}")
            return jsonify({"error": "Backend error"}), 500

@app.route('/store', methods=['GET'])
def get_all():
    with tracer.start_as_current_span("get_all"):
        logger.info("📦 Getting all key-value pairs")
        try:
            res = requests.get(backend_api_url)
            return jsonify(res.json()), res.status_code
        except Exception as e:
            logger.error(f"❌ Error getting all keys: {e}")
            return jsonify({"error": "Backend error"}), 500

@app.route("/metrics", methods=['GET'])
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

def check_backend():
    logger.info(f"🔄 Checking backend API at {backend_api_url}")
    try:
        res = requests.get(backend_api_url, timeout=3)
        res.raise_for_status()
        logger.info("✅ Backend is reachable.")
    except Exception as e:
        logger.critical(f"❌ Cannot reach backend: {e}")
        sys.exit(1)

if __name__ == '__main__':
    check_backend()
    logger.info(f"🚀 Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
