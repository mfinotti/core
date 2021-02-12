"""Support for Apache Kafka."""
from datetime import datetime
import json
import logging

from aiokafka import AIOKafkaConsumer
import voluptuous as vol

from config.custom_components.custom_event_handler import CustomEventEnum
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.util import ssl as ssl_util

KAFKA_CONSUMER_EVENT = "kafka_consume"
KAFKA_CONSUMER_START = "kafka_start_consuming"

_LOGGER = logging.getLogger(__name__)

DOMAIN = "kafka_consumer"

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

    kafka = hass.data[DOMAIN] = KafkaConsumer(
        hass,
        conf[CONF_IP_ADDRESS],
        conf[CONF_PORT],
        conf[CONF_TOPIC],
        conf[CONF_SECURITY_PROTOCOL],
        conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD),
    )

    hass.bus.async_listen_once(KAFKA_CONSUMER_START, kafka.startConsuming)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, kafka.shutdown)

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


class KafkaConsumer:
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
        self._consumer = AIOKafkaConsumer(
            topic,
            loop=hass.loop,
            bootstrap_servers=f"{ip_address}:{port}",
            security_protocol=security_protocol,
            ssl_context=ssl_context,
            sasl_mechanism="PLAIN",
            sasl_plain_username=username,
            sasl_plain_password=password,
            group_id="hassio",
        )
        self._topic = topic

    async def start(self):
        """Start the Kafka manager."""
        _LOGGER.info("Starting Kafka Consumer...")

        # self._hass.bus.async_listen(KAFKA_CONSUMER_EVENT, self.write)
        await self._consumer.start()

    async def startConsuming(self, _):

        _LOGGER.info("Start consuming on the given topic: %s", self._topic)

        try:
            async for msg in self._consumer:
                try:
                    _LOGGER.info("Consumed message: %s", msg.value.decode("utf-8"))
                    self._hass.bus.fire(
                        CustomEventEnum.INBOUND_EVENT.value, msg.value.decode("utf-8")
                    )
                except:
                    _LOGGER.error("bad message: %s", msg.value.decode("utf-8"))

        except:
            _LOGGER.error("error given in consuming message")

    async def shutdown(self, _):
        """Shut the manager down."""
        await self._consumer.stop()
