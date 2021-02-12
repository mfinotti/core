from enum import Enum
import json
import logging
from re import escape

from config.custom_components.custom_event_handler.eventMessage import (
    EntityMessage,
    EventMessage,
    EventTypeEnum,
    PlatformEnum,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "custom_event_handler"


class CustomEventEnum(Enum):
    TOOUTBOUND_EVENT = "TO_OUTBOUND_EVENT"
    OUTBOUND_EVENT = "OUTBOUND_EVENT"
    INBOUND_EVENT = "INBOUND_EVENT"


async def async_setup(hass, config):

    ceh = CustomEventHandler(hass)
    hass.bus.async_listen(CustomEventEnum.TOOUTBOUND_EVENT.value, ceh.outboundEvent)
    hass.bus.async_listen(CustomEventEnum.INBOUND_EVENT.value, ceh.inboundEvent)

    return True


class CustomEventHandler:
    def __init__(self, hass):
        """Initialize."""
        self._hass = hass

    async def inboundEvent(self, event):

        if event.data != "":
            try:
                _LOGGER.debug("event data: %s", event.data)
                eventMessage = self.parseEvent(event.data)

                self._processEventMessage(eventMessage)
            except Exception as e:
                _LOGGER.error("error in handling inbount event Exception: %s", e)

        return

    async def outboundEvent(self, event):

        _LOGGER.debug("To OutBound Event Message: %s", event.data)
        # TODO: event enrich with possible actions
        self._hass.bus.fire(CustomEventEnum.OUTBOUND_EVENT.value, event.data)

        return

    def parseEvent(self, eventData):
        eventMessage = None

        try:
            eventMessage = EventMessage(eventData)
        except:
            _LOGGER.error("Error parsing message: %s", eventData)

        return eventMessage

    def _processEventMessage(self, eventMessage: EventMessage):

        # detect event type
        if eventMessage.getEventType() == EventTypeEnum.REQUEST.value:
            return self._processEventTypeRequest(eventMessage)
        elif eventMessage.getEventType() == EventTypeEnum.NOTICE.value:
            return self._processEventTypeNotice(eventMessage)
        elif eventMessage.getEventType() == EventTypeEnum.ALERT.value:
            return self._processEventTypeAlert(eventMessage)

        return None

    def _processEventTypeRequest(self, eventMessage: EventMessage):

        responseMessage = EventMessage()
        responseMessage.sender = eventMessage.getSender()
        responseMessage.message = "RESPONSE"
        responseMessage.eventType = EventTypeEnum.NOTICE.value
        responseMessage.systemCode = eventMessage.getSystemCode()
        responseMessage.platform = eventMessage.getPlatform()
        responseMessage.entity = []

        if eventMessage.getPlatform() == PlatformEnum.STATE.value:
            if len(eventMessage.getEntity()) > 0:
                for e in eventMessage.getEntity():
                    eState = self._hass.states.get(e.getEntityId())

                    currentEntityMessage = EntityMessage()
                    currentEntityMessage.entityId = e.getEntityId()
                    currentEntityMessage.label = eState.attributes["friendly_name"]
                    currentEntityMessage.state = eState.state

                    responseMessage.getEntity().append(currentEntityMessage)
            else:
                responseMessage = None

        """ Dispatching OUTBOUND event """
        if None != responseMessage:
            self._hass.bus.fire(
                CustomEventEnum.TOOUTBOUND_EVENT.value,
                responseMessage.toJsonString(),
            )

    def _processEventTypeNotice(self, eventMessage: EventMessage):
        return eventMessage

    def _processEventTypeAlert(self, eventMessage: EventMessage):
        return eventMessage