# app/mqtt_publisher.py
import json
import logging
import os
import socket
import threading
import uuid
from typing import Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger("mqtt_publisher")

MQTT_BROKER_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))

MQTT_USERNAME = os.getenv("MQTT_USERNAME", "Khang")

# BẮT BUỘC phải có password, không cho default (tránh lộ credential / chạy sai môi trường)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
if not MQTT_PASSWORD:
    raise RuntimeError("Missing MQTT_PASSWORD env var")

MQTT_BASE_TOPIC = os.getenv("MQTT_BASE_TOPIC", "iot_room")

_client: Optional[mqtt.Client] = None
_client_lock = threading.Lock()


def _make_client_id(prefix: str = "room_backend_publisher") -> str:
    # Unique theo host + random -> chạy nhiều instance không đá nhau
    host = socket.gethostname()
    return f"{prefix}-{host}-{uuid.uuid4().hex[:8]}"


def _create_client() -> mqtt.Client:
    client = mqtt.Client(
        client_id=_make_client_id(),
        protocol=mqtt.MQTTv311,
        clean_session=True,
    )

    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    logger.info(
        "[MQTT] Connecting publisher to %s:%s as %s ...",
        MQTT_BROKER_HOST,
        MQTT_BROKER_PORT,
        MQTT_USERNAME,
    )

    rc = client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=30)
    if rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"MQTT connect failed (rc={rc})")

    client.loop_start()
    logger.info("[MQTT] Publisher connected.")
    return client


def _get_client() -> mqtt.Client:
    global _client
    with _client_lock:
        if _client is not None and _client.is_connected():
            return _client

        if _client is not None:
            logger.warning("[MQTT] Publisher lost connection, recreating...")

        _client = _create_client()
        return _client


def publish_device_command(device_id: str, command: dict) -> None:
    client = _get_client()

    topic = f"{MQTT_BASE_TOPIC}/devices/{device_id}/commands"
    payload = json.dumps(command, ensure_ascii=False)

    logger.info('[MQTT-PUB] topic=%s payload=%s', topic, payload)

    info = client.publish(topic, payload, qos=1, retain=False)
    info.wait_for_publish(timeout=2.0)

    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"MQTT publish failed with rc={info.rc}")
