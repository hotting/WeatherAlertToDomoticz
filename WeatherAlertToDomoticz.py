
import os
import sys
import ssl
import json
import logging
import requests
from time import sleep
from queue import Queue
from datetime import datetime
import xml.etree.ElementTree as ET
import paho.mqtt.client as mqtt_client
import paho.mqtt.properties as properties
from logging.handlers import RotatingFileHandler
import configparser

  
# =============================================================================
# ===================== initialize global variabelen ==========================
# ============================================================================= 
config= configparser.ConfigParser()
config.read("WeatherAlertToDomoticz.cfg")

# global variable in use for mqtt ['MQTT_settings']
BROKER_DOMAIN =config['MQTT_settings']['broker_domain'] 
CLIENT_ID =config['MQTT_settings']['client_id']
TOKEN = config['MQTT_settings']['token']
TOPIC = config['MQTT_settings']['topic']
PROTOCOL = mqtt_client.MQTTv5

# global variable in use when retrieving xml fil
API_KEY = config['dataplatform_knmi']['api_key']
DATASET_NAME = config['dataplatform_knmi']['dataset_name']
DATASET_VERSION = config['dataplatform_knmi']['dataset_version']

# variables related to domoticz
AUTORISATIE_TOKEN = config['domoticz']['autorisatie_token']
DEVICE_ID= config['domoticz']['device_id']
PROVINCE= config['domoticz']['province']
WEEKDAYS=list(config['domoticz']['weekdays'].split(" "))

# other global variables   

SCRPT_NAME = os.path.basename(sys.argv[0])[:-3]
URL_DOMOTICZ = config['global']['URL_domoticz']
OUTPUTFILE = f"{config['global']['logPath']}{SCRPT_NAME}.log"
WAIT_EXECUTION = int(config['global']['wait_execution']) # 5 MIN
# number of wait cycles before domoticz is refreshed (3600/wait time)
WAIT_CYCLES =  int(3600/WAIT_EXECUTION)-1  
 
# create a queue for the available files 
File_Q = Queue()    


# =============================================================================
# ========================== initialize logging ===============================
# =============================================================================  

logging.basicConfig(
    format='%(asctime)s: %(levelname)-8s: %(funcName)-12s:  %(lineno)-4d: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level = logging.INFO,
    )
logger = logging.getLogger(__name__)

# Define a handler witch writes INFO messages or higher to a file and rotate at max bytes
fh = RotatingFileHandler(OUTPUTFILE,maxBytes=1048576, backupCount=2) # max 1 MiB
fh.setLevel(logging.INFO)
# set a format which is for File use
ff = logging.Formatter('%(asctime)s: %(levelname)-8s: %(funcName)-12s: %(message)s','%Y-%m-%d %H:%M:%S',)
fh.setFormatter(ff)
# add the handler to the root logger
logger.addHandler(fh)

logger.info ("="*52)
logger.info (f' {SCRPT_NAME} started '.center(52,'='))
logger.info ("="*52)
logger.info (" loaded parameters  ".center(52,' '))

for x in config:
    logger.info(" "*52)
    logger.info (f"<< {x} >>".center(52))
    for y,z in config[x].items():
        logger.info (f"{y} : {z}")
logger.info ("="*52)

# Release the used memory by config
del config

# ============================================================================= 
# ================================ Classes ==================================== 
# =============================================================================
  
class Domoticz:
    """
    Class that simplifies communication with domoticz.
    The authorization requirements can be found at
    https://www.domoticz.com/wiki/Domoticz_API/JSON_URL%27s#Authorization

    __get_data provides the communication with domoticz. This function is called by
    the other functions that configure the appropriate parameters
    
    Functions:
    Status => requests the status of a device with a specified ID
    update => update the value of the specified device with the specified values
                which value is expected depends on the device and can be found at:
                https://www.domoticz.com/wiki/Domoticz_API/JSON_URL%27s#Update_devices.2Fsensors
    log     => put a message in the domoticz log
    variable=> requests the value of a domoticz variable with the specified ID
    """
    
    def __init__(self, url:str = None , id:int = None) -> None:
        self.base_url = f"{URL_DOMOTICZ}/json.htm" if not url else url
        self.headers = {"Authorization":AUTORISATIE_TOKEN}
        self.id=id
        self.type='command'
    
    def __get_data(self, url:str, params:dict=None):
        try:
            with requests.get(url, headers=self.headers, params=params) as r:
                logger.info(f"=> Domoticz: {r.url}")            
                return r.json()
        except Exception as err:
            logger.error()(f"Error handeling domoticz \n{err}")
            return"ERROR"
    
    def status(self,id:int=None):
        id = self.id if not id else id
        return self.__get_data(self.base_url,dict(
           type =self.type,
           param ='getdevices',
           rid = id
        ))
        
    def update(self,id:int= None, nvalue:float=0, svalue:str=""):
        id = self.id if not id else id        
        return self.__get_data(self.base_url,dict(
           type =self.type,
           param ='udevice',
           idx = id,
           nvalue = nvalue,
           svalue = svalue
        ))
        
    def log (self, mess, level:int = 2):
        return (self.__get_data(self.base_url,dict(
           type =self.type,
           param ='addlogmessage',
           message = mess,
           level = level
        )))
    
    def variabele (self, id:int=1):        
        return self.__get_data(self.base_url,dict(
           type =self.type,
           param ='getuservariable',
           idx = id
        ))
        
class OpenDataAPI:
    def __init__(self, api_token: str):
        self.base_url = "https://api.dataplatform.knmi.nl/open-data/v1"
        self.headers = {"Authorization": api_token}

    def __get_data(self, url, params=None):
        return requests.get(url, headers=self.headers, params=params).json()

    def list_files(self, DATASET_NAME: str, DATASET_VERSION: str, params: dict):
        return self.__get_data(
            f"{self.base_url}/datasets/{DATASET_NAME}/versions/{DATASET_VERSION}/files",
            params=params,
        )

    def get_file_url(self, temp_url: str):
        return self.__get_data(
            f"{temp_url}"
        )

# =============================================================================
# ============================== Functions ====================================
# =============================================================================

def connect_mqtt() -> mqtt_client:
    logger.debug('No arguments ')
    def on_connect(c: mqtt_client, userdata, flags, rc, reason_code, props=None):
        logger.debug(f'\n\t\t\t\t userdata={userdata},\n\t\t\t\t flags = {flags},\n\t\t\t\t rc = {rc},\n\t\t\t\t reasoncode = {reason_code},\n\t\t\t\t props = {props}')
        logger.info(f"Connected using client ID: {str(c._client_id)}")
        logger.info(f"Session present: {str(flags['session present'])}")
        logger.info(f"Connection result: {str(rc)}")
        # Subscribe here so it is automatically done after disconnect
        subscribe(c, TOPIC)

    client = mqtt_client.Client(client_id=CLIENT_ID, protocol=PROTOCOL, transport="websockets")
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    connect_properties = properties.Properties(properties.PacketTypes.CONNECT)
    # Maximum is 3600
    connect_properties.SessionExpiryInterval = 3600

    # The MQTT username is not used for authentication, only the token
    username = "token"
    client.username_pw_set(username, TOKEN)
    client.on_connect = on_connect

    client.connect(host=BROKER_DOMAIN, port=443, keepalive=60, clean_start=False, properties=connect_properties) # set the clean_start to false or true. to delete previous sessions

    return client

def subscribe(client: mqtt_client, topic: str):
    logger.debug(f'\n\t\t\t\t topic= {topic}')
    def on_message(c: mqtt_client,userdata , message):
        logger.debug(f'\n\t\t\t\t userdata = {userdata},\n\t\t\t\t message = {message}')
        # NOTE: Do NOT do slow processing in this function, as this will interfere with PUBACK messages for QoS=1.
        # A couple of seconds seems fine, a minute is definitely too long.
        #logger.info(f"Received message on topic {message.topic}: {str(message.payload)}")
        load = json.loads(message.payload)        
        if 'data'in load:
            if 'xml' in load['data']['filename']:
                logger.debug(f"Added to queue : {load['data']['url']}")
                # Place the available file in a queue
                File_Q.put(load['data']['url'])
        else:
            logger.info(f"Received message on topic: {message.topic}: {str(message.payload)}")
            
    def on_subscribe(c: mqtt_client, userdata, mid, granted_qos, *other):
        logger.debug(f'\n\t\t\t\t userdata ={userdata},\n\t\t\t\t mid ={mid},\n\t\t\t\t granted_qos = {granted_qos}')
        logger.info(f"Subscribed to topic '{topic}'")

    client.on_subscribe = on_subscribe
    client.on_message = on_message
    # A qos=1 will replay missed events when reconnecting with the same client ID. Use qos=0 to disable
    client.subscribe(topic, qos=1)


def get_knmi_files():
    logger.debug(f'\n\t\t\t\t No arguments')
    # logger.info(f"Fetching latest file of {DATASET_NAME} version {DATASET_VERSION}")
    # download_url='https://api.dataplatform.knmi.nl/open-data/v1/datasets/waarschuwingen_nederland_48h/versions/1.0/files/knmi_waarschuwingen_202402120747.xml/url'
    download_url= File_Q.get()
    logger.info (f"Get the download URL from: {download_url}")
    api = OpenDataAPI(api_token=API_KEY)
    
    try:
        response = api.get_file_url(download_url)
        logger.debug(f"download url : {response['temporaryDownloadUrl']}")
        with requests.get(response['temporaryDownloadUrl'], stream=True) as r:
            r.raise_for_status()
            with open(f"{SCRPT_NAME}.xml", "wb") as f:
                for chunk in r.iter_content(chunk_size=8192): # kan naar 1024 voor minder mem gebruik
                    f.write(chunk)
    except Exception:
        logger.error("Unable to download file using download URL")
        sys.exit('system error. Program terminated')
 
def parse_XML_file(File):
    logger.debug(f'\n\t\t\t\t file = {File}')
    # Check if data is available
    if  not os.path.isfile(File): return (0, "No data available \nThis can take up to 5 hours")
    #get data from file
    doc= ET.parse(File)
    root = doc.getroot()
    #set local variabelen
    warningStatus = 0
    WarningList = []
    WarningText =""
    status=False
    startTime=""
    endTime=""

    # loop through the selected data and process the outcome    
    for timeslot in root.findall(".//data/cube/timeslice//"):
        # save the time of the timeslot being processed
        if timeslot.tag == "timeslice_id":
            TimeslotTime = timeslot.text
        # process all phenomena in the timeslot
        if timeslot.tag == "phenomenon":
            for phenomenon in timeslot:
                # process all locations in phenomena
                if phenomenon.tag == "location":                     
                    for locations in phenomenon:
                        # proces wanted location in locations
                        if locations.tag == "location_id" and locations.text != PROVINCE: break # if not Wanted area then exit for loop
                        if locations.tag =="location_warning_status" and int(locations.text) > 0: # if a warning is active
                            status= True # flag to mark whether text needs to be processed

                            # sets the highest warning level in warningStatus
                            if warningStatus < int(locations.text): warningStatus= int(locations.text) 

                            # proces the warning text
                        if status and locations.tag == "text": # process text
                            status = False 
                            logger.debug(f"Time slot with warning: {TimeslotTime}")
                            # manage start and end time
                            if startTime == "": startTime= datetime.fromisoformat(TimeslotTime)
                            endTime = datetime.fromisoformat(TimeslotTime)
                            # Get the desired text
                            for txt in locations:
                                if txt.tag == "text_data" and txt.text != None : WarningList.append(txt.text) # put the text in the list
    
    
    # loop through the selected data and process the outcome
    if startTime : # if a time is available, include it in the WarningText                               
        WarningText= f"Van {WEEKDAYS[datetime.weekday(startTime)]} {startTime.hour}:00 tot {WEEKDAYS[datetime.weekday(endTime)]} {endTime.hour + 1}:00 \n"

    # remove duplicates from the WarningList list
    WarningList = list(dict.fromkeys(WarningList)) 

    #transform list to a string
    if WarningList: WarningText += "\n".join(WarningList)

    if not WarningText: WarningText ="Geen waarschuwingen"
   
    return warningStatus,WarningText   


def run():
    logger.debug('\n\t\t\t\t No arguments ')
    wait_cycles = 1
    client = connect_mqtt()
    client.loop_start()
    # File_Q.put('https://api.dataplatform.knmi.nl/open-data/v1/datasets/waarschuwingen_nederland_48h/versions/1.0/files/knmi_waarschuwingen_202402261144.xml/url')
    # get_knmi_files()
    wwd=Domoticz(id=DEVICE_ID)
    Wstatus,Wtext = parse_XML_file(f"{SCRPT_NAME}.xml")
    wwd.update(nvalue=Wstatus,svalue=Wtext)
    while True:
        logger.debug(f'Loop {wait_cycles} of {WAIT_CYCLES}')
        while not File_Q.empty():# execute when new files are available
            get_knmi_files()
            wait_cycles = WAIT_CYCLES+1
        if wait_cycles >= WAIT_CYCLES:   # run once an hour or when there are new files        
            Wstatus,Wtext = parse_XML_file(f"{SCRPT_NAME}.xml")
            #convert the status to the domoticz requirements (add 1 to the status)
            Wstatus += 1
            wwd.update(nvalue=Wstatus,svalue=Wtext) # send to domoticz
            wwd.log(f'{SCRPT_NAME}: Has updated device {DEVICE_ID}')
            logger.debug(f"{Wstatus} \t {Wtext}")
            wait_cycles = 0
        else:
            wait_cycles += 1
        sleep(WAIT_EXECUTION)

if __name__ == "__main__":
    run()
