from enum import Enum
import json


class EventTypeEnum(Enum):
    REQUEST = "REQUEST"
    NOTICE = "NOTICE"
    ALERT = "ALERT"


class PlatformEnum(Enum):
    STATE = "STATE"


class EntityMessage:

    type: str
    entityId: str
    label: str
    state: str

    def __init__(self, data=None):
        if None == data:
            return

        self.entityId = data["entityId"]
        self.type = self.entityId.split(".")[0]
        if "label" in data:
            self.label = data["label"]

        if "state" in data:
            self.state = data["state"]

    def __str__(self):
        return str(self.__dict__)

    def getType(self):
        return self.type

    def getEntityId(self):
        return self.entityId

    def getLabel(self):
        return self.label

    def getState(self):
        return self.state


class EventMessage:

    sender: str
    message: str
    eventType: str
    systemCode: str
    platform: str
    entity = []

    def __init__(self, data=None):
        if None == data:
            return

        if type(data) == str:
            jsonData = json.loads(data)
        else:
            jsonData = data

        if "sender" in data:
            self.sender = jsonData["sender"]
        if "message" in data:
            self.message = jsonData["message"]
        self.eventType = EventTypeEnum(jsonData["eventType"]).value
        self.platform = PlatformEnum(jsonData["platform"]).value
        self.systemCode = jsonData["systemCode"]
        if "entity" in data:
            if type(jsonData["entity"]) is list:
                self.entity = None
                self.entity = []
                for data in jsonData["entity"]:
                    self.entity.append(EntityMessage(data))
            else:
                self.entity.append(EntityMessage(jsonData["entity"]))

    def __str__(self):
        return str(self.__dict__)

    def toJsonString(self):
        stringToReturn = "{"
        for key in self.__dict__.keys():
            if len(stringToReturn) > 1:
                stringToReturn += ","

            if type(self.__getattribute__(key)) == list:
                listStringToReturn = ""
                for e in self.__getattribute__(key):
                    if len(listStringToReturn) > 0:
                        listStringToReturn += ","

                    listStringToReturn += e.__str__()
                stringToReturn += '"' + key + '"' + ":[" + listStringToReturn + "]"
            else:
                stringToReturn += '"' + key + '"' + ":" + '"' + self.__dict__[key] + '"'
        stringToReturn += "}"

        return stringToReturn.replace("'", '"')

    def getEventType(self):
        return self.eventType

    def getSender(self):
        return self.sender

    def getMessage(self):
        return self.message

    def getSystemCode(self):
        return self.systemCode

    def getPlatform(self):
        return self.platform

    def getEntity(self):
        return self.entity
