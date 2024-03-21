
# Summary

A python script that displays the weather warnings for the Netherlands issued by the KNMI in domoticz.
Since November 2023, the KNMI has stopped using the RSS feed to publish weather warnings. I used this RSS feed to display the weather warnings in domoticz. As an alternative, the KNMI also offered this information via an API. This inspired me to create this script.
This script receives a message from the KNMI via MQTT that new data files are available. These files are then downloaded and saved. Each new file replaces the old one so that only the current file remains available locally.
A loop checks every 5 minutes whether there is a new file locally and if so, this file is processed and displayed in Domoticz. If there is no new data file, the device in Domoticz will be updated once an hour. This is to prevent the device from showing a red bar

# Explanation
The weather warnings are displayed in Domoticz in an alert device (general alert). It is necessary that this device is present before starting the script. You must enter the ID of this device in the cfg file.

Place the files WeatherAlertToDomoticz.py and WeatherAlertToDomoticz.cfg in the same directory and then run the script.
By default, the log file is placed in the same directory as the script. If you want to place this log file in the common log directory, you can specify this in the cfg file. This is necessary when you use the log2ram program

The necessary information for the script to work is specified in the cfg file
“WeatherAlertToDomoticz.cfg”

The cfg file indicates what must be entered and how to arrive at this value
Only when “your own value” is stated is it necessary to adjust this value. For all other values, the program works with the value already specified and adjustments can lead to different behavior. It is therefore recommended to leave this unchanged
The script requires Python 3.9 or higher

# cfg file
### [global]
+ waiting time between script executions in seconds default 300 (5 min)

    `wait_execution = 300`

+ The url for domoticz, don't forget the port number

    `URL_domoticz = http://your own url:port`

+ logPath is the complete path to the location of the log file without the name. 
For the active dir as path this can be left empty. 
the default path for log files on the raspberry is /var/log/
    
    `logPath = `

### [MQTT_settings]
+ Address of the mqtt broker

    `broker_domain = mqtt.dataplatform.knmi.nl`

+ Client ID should be made static, it is used to identify your session, so that
 missed events can be replayed after a disconnect. Create your own unique ID  on: 
 [https://www.uuidgenerator.net/version4](https://www.uuidgenerator.net/version4)

    `client_id = your own value`

+ A token is required to gain access to the mqtt broker. Obtain your token at: [https://developer.dataplatform.knmi.nl/notification-service#access](https://developer.dataplatform.knmi.nl/notification-service#access)

    `token = your own value`

+ The topic to be subscribed to. This will listen to both file creation and update events of this dataset
 [https://dataplatform.knmi.nl/dataset/waarschuwingen-nederland-48h-1-0](https://dataplatform.knmi.nl/dataset/waarschuwingen-nederland-48h-1-0)

    `topic = dataplatform/file/v1/waarschuwingen_nederland_48h/1.0/#`

+ Protocol used by mqtt client. Version 3.1.1 also supported

    `PROTOCOL = mqtt_client.MQTTv5`

### [dataplatform_knmi]
+ A token is required to gain access to the dataplatform. Obtain your token at: [https://developer.dataplatform.knmi.nl/open-data-api#token](https://developer.dataplatform.knmi.nl/open-data-api#token)

    `api_key = your own value`

+ only adjust the next two variables if the name and version of the dataset has changed

    `dataset_name = waarschuwingen_nederland_48h`

    `dataset_version = 1.0`

### [domoticz]
+ The authorization requirements can be found at
 [https://www.domoticz.com/wiki/Domoticz_API/JSON_URL%27s#Authorization](https://www.domoticz.com/wiki/Domoticz_API/JSON_URL%27s#Authorization)
 if you create a user **domoticz** in domoticz with the password **class**. Then you can enter the following authentication token => "Basic ZG9tb3RpY3o6Y2xhc3M="

    `autorisatie_token = your own value`

+ Id number of the alert device in domoticz

    `device_id = 208`

+ For province you can choose between: WAE, GR, FR, DR, NH, FL, OV, GL, UT, ZH, ZE, NB, LB, WAB

    `province = ZH`

+ 7 Names of the Weekdays. These must be separated by a space. Start with Monday

    `weekdays = ma di wo do vr za zo`
