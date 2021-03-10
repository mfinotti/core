from enum import Enum
from json import dump, dumps, loads
import logging
from re import escape
from typing import OrderedDict

from config.custom_components.custom_event_handler.eventMessage import (
    EntityActionMessage,
    EntityMessage,
    EventMessage,
    EventTypeEnum,
    PlatformEnum,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "custom_event_handler"

SYSTEMCODE_ENTITY = "input_text.system_code"


class CustomEventEnum(Enum):
    TOOUTBOUND_EVENT = "TO_OUTBOUND_EVENT"
    OUTBOUND_EVENT = "OUTBOUND_EVENT"
    INBOUND_EVENT = "INBOUND_EVENT"


async def async_setup(hass, config):

    conf = config[DOMAIN]

    if len(conf["entities"]) > 0:
        _LOGGER.info("configuration loaded. %s", conf["entities"])
    else:
        _LOGGER.warn("Any entity has provided in the configuration.")

    ceh = CustomEventHandler(hass, conf["entities"])
    hass.bus.async_listen(CustomEventEnum.TOOUTBOUND_EVENT.value, ceh.outboundEvent)
    hass.bus.async_listen(CustomEventEnum.INBOUND_EVENT.value, ceh.inboundEvent)

    return True


class CustomEventHandler:
    def __init__(self, hass, entities):
        """Initialize."""
        self._hass = hass
        self._entities = loads(dumps(entities))

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

        systemCodeEntityState = self._hass.states.get(SYSTEMCODE_ENTITY)
        if systemCodeEntityState == None:
            _LOGGER.error("SYSTEM CODE NOT VALID!!!! %s", systemCodeEntityState)
            return

        if "type" not in event.data or "entityId" not in event.data:
            _LOGGER.error("Invalid event provided: %s", event.data)
            return

        entityState = self._hass.states.get(event.data["entityId"])

        messageString = None
        if "message" in event.data:
            messageString = event.data["message"]

        eventMessage = EventMessage(
            {
                "eventType": event.data["type"],
                "message": messageString,
                "platform": PlatformEnum.EVENT.value,
                "systemCode": systemCodeEntityState.state,
                "entity": [
                    {
                        "entityId": event.data["entityId"],
                        "state": entityState.state,
                        "label": entityState.attributes["friendly_name"],
                    }
                ],
            }
        )

        self._processEventMessage(eventMessage)

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
            # return self._processEventTypeAlert(eventMessage) BYPASS
            return self._processEventTypeNotice(eventMessage)

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
        elif eventMessage.getPlatform() == PlatformEnum.EVENT.value:
            self._hass.bus.fire(
                eventMessage.getEntity()[0].getEntityId()
            )
            responseMessage.message = "Richiesta ricevuta, ed eseguita."

        """ Dispatching OUTBOUND event """
        if None != responseMessage:
            jsonMessage = self.toDict(responseMessage)
            self._hass.bus.fire(
                CustomEventEnum.OUTBOUND_EVENT.value,
                dumps(jsonMessage),
            )

    def _processEventTypeNotice(self, eventMessage: EventMessage):
        eventMessage2 = self.__processEvent(eventMessage)

        _LOGGER.debug("Notice Event Message: %s", eventMessage)
        try:
            jsonMessage = self.toDict(eventMessage2)
            _LOGGER.debug("messageEvent: %s", jsonMessage)

            self._hass.bus.fire(
                CustomEventEnum.OUTBOUND_EVENT.value,
                dumps(jsonMessage),
            )
        except Exception as e:
            _LOGGER.error(e)

        return eventMessage

    def _processEventTypeAlert(self, eventMessage: EventMessage):
        eventMessage = self.__processEvent(eventMessage)

        _LOGGER.info("Notice Event Message: %s", eventMessage)
        return eventMessage

    def __processEvent(self, eventMessage: EventMessage):

        if len(eventMessage.getEntity()) > 0:
            for entity in eventMessage.getEntity():
                entity: EntityMessage
                entityId = entity.getEntityId()
                try:
                    # entityConf =
                    entityEventActions = self.__getActionsByEntityEvent(
                        entityId, eventMessage.getEventType()
                    )
                    if entityEventActions and len(entityEventActions) > 0:
                        entityActions = []
                        for action in entityEventActions:
                            entityActions.append(EntityActionMessage(action))

                        entity.actions = entityActions
                except Exception as e:
                    _LOGGER.info("Error: %s", e)

        return eventMessage

    def __getActionsByEntityEvent(self, entityId, eventType):

        entityConf = None
        eventActions = None
        for config in self._entities:
            try:
                entityConf = config[entityId]
                break
            except Exception as e:
                continue

        if entityConf:
            for eventConf in entityConf:
                try:
                    eventActions = eventConf[eventType]
                    break
                except Exception as e:
                    continue

        return eventActions["actions"]

    def toDict(self, obj):
        if not hasattr(obj, "__dict__"):
            return obj
        result = {}
        for key, val in obj.__dict__.items():
            if key.startswith("_"):
                continue
            element = []
            if isinstance(val, list):
                for item in val:
                    element.append(self.toDict(item))
            else:
                element = self.toDict(val)
            result[key] = element
        return result