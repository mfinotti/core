"""Support for Apache Kafka."""
from datetime import datetime
import json
import logging

from aiokafka import AIOKafkaProducer
import voluptuous as vol

from config.custom_components.custom_event_handler import CustomEventEnum
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.util import ssl as ssl_util

KAFKA_PRODUCER_EVENT = "kafka_produce"

_LOGGER = logging.getLogger(__name__)

DOMAIN = "kafka_producer"

CONF_TOPIC = "topic"
CONF_SECURITY_PROTOCOL = "security_protocol"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Required(CONF_TOPIC): cv.string,
                vol.Optional(CONF_SECURITY_PROTOCOL, default="PLAINTEXT"): vol.In(
                    ["PLAINTEXT", "SASL_SSL"]
                ),
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Activate the Apache Kafka integration."""
    conf = config[DOMAIN]

    kafka = hass.data[DOMAIN] = KafkaProducer(
        hass,
        conf[CONF_IP_ADDRESS],
        conf[CONF_PORT],
        conf[CONF_TOPIC],
        conf[CONF_SECURITY_PROTOCOL],
        conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD),
    )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, kafka.shutdown)
    # OUTBOUND EVENT SUBSCRIPTION
    hass.bus.async_listen(CustomEventEnum.OUTBOUND_EVENT.name, kafka.write)
    await kafka.start()

    return True


class DateTimeJSONEncoder(json.JSONEncoder):
    """Encode python objects.

    Additionally add encoding for datetime objects as isoformat.
    """

    def default(self, o):
        """Implement encoding logic."""
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


class KafkaProducer:
    """Define a manager to buffer events to Kafka."""

    def __init__(
        self,
        hass,
        ip_address,
        port,
        topic,
        security_protocol,
        username,
        password,
    ):
        """Initialize."""
        self._encoder = DateTimeJSONEncoder()
        self._hass = hass
        ssl_context = ssl_util.client_context()
        self._producer = AIOKafkaProducer(
            loop=hass.loop,
            bootstrap_servers=f"{ip_address}:{port}",
            compression_type="gzip",
            security_protocol=security_protocol,
            ssl_context=ssl_context,
            sasl_mechanism="PLAIN",
            sasl_plain_username=username,
            sasl_plain_password=password,
        )
        self._topic = topic

    def _encode_event(self, event):
        """Translate events into a binary JSON payload."""

        _LOGGER.info("Event %s ", event.data)
        return json.dumps(obj=event.data, default=self._encoder.encode).encode("utf-8")

    async def start(self):
        """Start the Kafka manager."""
        _LOGGER.info("Starting Kafka Producer...")
        # KAFKA OWN WRITE EVENT
        self._hass.bus.async_listen(KAFKA_PRODUCER_EVENT, self.write)
        await self._producer.start()

    async def shutdown(self, _):
        """Shut the manager down."""
        await self._producer.stop()

    async def write(self, event):
        """Write a binary payload to Kafka."""
        # payload = self._encode_event(event)
        _LOGGER.info("producing payload: %s", event.data)
        payload = bytearray(event.data, "utf-8")
        if payload:
            await self._producer.send_and_wait(self._topic, payload)
