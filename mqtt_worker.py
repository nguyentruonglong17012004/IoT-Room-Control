import json
import logging
import ssl
import time
from typing import Optional

import paho.mqtt.client as mqtt
import requests
from requests.exceptions import RequestException

# ===== CONFIG =====
MQTT_HOST = "localhost"
MQTT_PORT = 8883
MQTT_USERNAME = "iot_worker"
MQTT_PASSWORD = "Tiramixu17012004"  # không có dấu ngoặc

# Topic: doctorx/devices/<device_id>/telemetry
MQTT_TOPIC = "doctorx/devices/+/telemetry"

CA_CERT_PATH = "certs_https/mqtt_certs/ca.crt"

BACKEND_BASE_URL = "https://127.0.0.1:8443"
INGEST_PATH = "/ingest/telemetry"

# API key mặc định nếu payload không gửi kèm api_key
# Bạn có thể để trống nếu muốn device tự gửi api_key trong payload.
DEFAULT_DEVICE_API_KEY = "567b73411887e261fa66201905a71f96"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

INGEST_URL = f"{BACKEND_BASE_URL}{INGEST_PATH}"

# Tắt warning verify self-signed cert local
requests.packages.urllib3.disable_warnings()


def extract_device_id_from_topic(topic: str) -> Optional[str]:
    """
    Topic mặc định: doctorx/devices/<device_id>/telemetry
    → Lấy <device_id> ra từ topic.
    """
    parts = topic.split("/")
    try:
        idx = parts.index("devices")
    except ValueError:
        return None

    if idx + 1 < len(parts):
        return parts[idx + 1]
    return None


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info("Connected to TLS MQTT broker %s:%s ...", MQTT_HOST, MQTT_PORT)
        client.subscribe(MQTT_TOPIC)
        logging.info("Subscribed to %s", MQTT_TOPIC)
    else:
        logging.error("Connect failed, rc=%s", rc)


def on_message(client, userdata, msg):
    payload_str = msg.payload.decode("utf-8", errors="ignore")
    logging.info("Received MQTT message on %s: %s", msg.topic, payload_str)

    try:
        data = json.loads(payload_str)
    except json.JSONDecodeError as e:
        logging.error("Bad JSON from MQTT: %s", e)
        return

    # Lấy device_id từ payload hoặc từ topic
    device_id = data.get("device_id") or extract_device_id_from_topic(msg.topic)
    if not device_id:
        logging.error("Cannot determine device_id from topic or payload, skip.")
        return

    metric_type = data.get("metric_type")
    if not metric_type:
        logging.error("Missing metric_type in MQTT payload, skip.")
        return

    api_key = data.get("api_key") or DEFAULT_DEVICE_API_KEY
    if not api_key:
        logging.error("No api_key provided (payload + DEFAULT_DEVICE_API_KEY đều trống), skip.")
        return

    telemetry_payload = {
        "device_id": device_id,
        "api_key": api_key,
        "metric_type": metric_type,
        "value": data.get("value"),
        "payload": data.get("payload"),
    }

    try:
        resp = requests.post(
            INGEST_URL,
            json=telemetry_payload,
            timeout=5,
            verify=False,  # vì đang dùng self-signed cert local
        )
        logging.info("Forwarded telemetry to backend: %s", resp.status_code)
        if resp.status_code >= 400:
            logging.error("Backend response: %s - %s", resp.status_code, resp.text)
    except RequestException as e:
        logging.error("Error calling backend: %s", e)


def main():
    client = mqtt.Client(client_id="room_iot_mqtt_ingestor")

    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.tls_set(
        ca_certs=CA_CERT_PATH,
        certfile=None,
        keyfile=None,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    client.tls_insecure_set(False)

    client.on_connect = on_connect
    client.on_message = on_message

    logging.info("Connecting to TLS MQTT broker %s:%s ...", MQTT_HOST, MQTT_PORT)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    client.loop_start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Stopping...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
