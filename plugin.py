# Basic Python Plugin Example
#
# Author: akamming 
#
"""
<plugin key="WMPS" name="WaterMeter NPN plugin" author="akamming" version="1.0.2" wikilink="https://www.domoticz.com/wiki/Plugins" externallink="https://www.google.com/">
    <description>
        <h2>Watermeter</h2><br/>
        Plugin version of the Watermeter python script using a NPN sensor<br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Exports the pin (not necessary to do before starting domoticz)</li>
            <li>Is run from within domoticz (no need for making sure a seperate python scripts keeps up and running on your pi)</li>
            <li>Creates the watermeterdevice (no need for giving special http commands to create the needed device) </li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>WaterMeter - Counts the liters of water running through your watermeter</li>
        </ul>
        <h3>Configuration</h3>
        Configure correctly. The plugin works using the default settings, but your system might need different settings...
        <ul style="list-style-type:square">
            <li>GPIO Pin Number - The GPIO Pin (BCM!) to which your NPN sensor is connected. To avoid conflicts, make sure the GPIO pin is not managed/configured somewhere else on your system to prevent confllicts. You can still use the normal GPIO drivers in domoticz for other pins as long as you don't configure the same pins.</li>
            <li>Debounce Time - Configure the cooldown time after the interrupt to prevent interrupt flooding. A high number is recommended, but it should be less then the time it takes to have 1 liter going throught your watermeter, to prevent lost measurements. Check domoticz log to see the water rate after water is consumed.</li> 

            <br/>
            Last but not least: A normal (Dutch) watermeter measures 1 liter every pulse on the GPIO pin. The meter in domoticz is of the type M3. So in order to have this meter to show the correct amount, you have to change the RFX Meter/Counter Setup in domoticz. If this is not set correctly: <br />
            - Go to domoticz web interface<br/>
            - Click on Setup<br/>
            - Click on Settings<br/>
            - Click on Meters/Counters<br/>
            - Set the value of the water divider to 1000  (1 M3 = 1000 L ;-))<br/>
            - Click on Apply Settings  <br/><br/>
        </ul>
    </description>
    <params>
         <param field="Mode1" label="GPIO Pin Number" width="150px">
         <options>
            <option label="GPIO2" value="2" />
            <option label="GPIO3" value="3"/>
            <option label="GPIO4" value="4"/>
            <option label="GPIO5" value="5"/>
            <option label="GPIO6" value="6"/>
            <option label="GPIO7" value="7"/>
            <option label="GPIO8" value="8"/>
            <option label="GPIO9" value="9"/>
            <option label="GPIO12" value="12"/>
            <option label="GPIO13" value="13"/>
            <option label="GPIO14" value="14"/>
            <option label="GPIO15" value="15"/>
            <option label="GPIO16" value="16"/>
            <option label="GPIO17" value="17"/>
            <option label="GPIO18" value="18"/>
            <option label="GPIO19" value="19"/>
            <option label="GPIO20" value="20"/>
            <option label="GPIO21" value="21" default="true"/>
            <option label="GPIO22" value="22"/>
            <option label="GPIO23" value="23"/>
            <option label="GPIO24" value="24"/>
            <option label="GPIO25" value="25"/>
            <option label="GPIO26" value="26"/>
         </options>
         </param> 
         <param field="Mode4" label="Debounce time (s)" width="150px" required="true" default="0.350"/>
     </params>
</plugin>
"""
import Domoticz
from gpiozero import Button
import os
import time
import datetime

class BasePlugin:

    enabled = False
    def __init__(self):
        return

    def onStart(self):
        self.fakereading = False        # for testing purposes. Will generate a "tick" every 20 seconds

        # Check if we have to go in debug mode
        self.debug = False #True/False  # set to true to enable debug logging

        # Used to limit write to disk
        self.busy = False
        self.delta = 0

        #Used for debouncing
        self.bouncetime = float(Parameters["Mode4"])
        self.n_interrupt = 0
        self.first_time = 0
        self.last_time = 0

        Domoticz.Log("Watermeter plugin started...")

        # Check if we have to switch on debug mode
        if os.path.exists(str(Parameters["HomeFolder"])+"DEBUG"): 
            self.debug = True
            Domoticz.Log("File "+str(Parameters["HomeFolder"])+"DEBUG"+" exists, switching on Debug mode")
        else:
            self.debug = False #True/False

        # Check if we have to switch on pulse for testin purposes
        if os.path.exists(str(Parameters["HomeFolder"])+"TESTPULSE"): 
            self.fakereading = True
            Domoticz.Log("Plugin is in testing mode, generates a tick every 20 seconds by itself!!, delete file "+str(Parameters["HomeFolder"])+"TESTPULSE to switch off")
        else:
            self.fakereading = False


        self.Debug("OnStart called")

        if self.debug == True:
            self.Debug("In Debug mode: Dumping config to log...") 
            DumpConfigToLog()

        # Get pin config from settings
        gpio_pin=int(Parameters["Mode1"])

        self.Debug("Pin "+str(gpio_pin)+" was configured")

        # Setting up GPIO
        self.Debug("Setting up GPIO")
        self.meter = Button(gpio_pin)
        self.meter.when_pressed = self.Interrupt
        #self.meter.when_released= self.Interrupt

        # Create device if needed
        if (len(Devices) == 0):
            self.Debug("Creating watermeter device")
            Domoticz.Device(Name="Water Usage", Used=1, Unit=1, Type=113, Subtype=0, Switchtype=2).Create()

    def onStop(self):
        self.Debug("onStop called")
        self.meter.close()
        del self.meter

    def onConnect(self, Connection, Status, Description):
        self.Debug("onConnect called")

    def onMessage(self, Connection, Data):
        self.Debug("onMessage called")

    def onCommand(self, Unit, Command, Level, Hue):
        self.Debug("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        self.Debug("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        self.Debug("onDisconnect called")

    def onHeartbeat(self):
        self.Debug("onHeartbeat called")
        if self.fakereading == True and self.delta == 0:
            self.Debug("FakeReading==True: Generating testpulse, not generated by watermeter itself!")
            self.Interrupt(1) #For testing purposes

        # Do not write every time. This will destroy ssd drives.
        if self.busy == True:
            self.busy = False
        elif self.delta != 0:
            # Create device if it is no longer there
            if (len(Devices) == 0):
                self.Debug("Watermeter device gone...Creating watermeter device")
                Domoticz.Device(Name="Water Usage", Used=1, Unit=1, Type=113, Subtype=0, Switchtype=2).Create()

            # Update the device with the found delta
            rate = 0
            if self.delta != 1:
                rate = round((self.last_time - self.first_time) / (self.delta - 1) * 1000) / 1000
            text = "RFXMeter/RFXMeter counter ("+Devices[1].Name+") - " + str(self.delta) + " Liter. Rate " + str(rate) + " Seconds/Liter. Interrupts " + str(self.n_interrupt)
            Domoticz.Log(text)
            if (self.debug):
                with open ("meterstand_water.log", 'a') as f:
                    f.write(str(datetime.datetime.now()) + " " + text + "\n")
            counter = Devices[1].nValue + self.delta
            self.delta = 0
            self.n_interrupt = 0
            Devices[1].Update(nValue=int(counter), sValue=str(counter))

    def Interrupt(self, channel):
        self.n_interrupt = self.n_interrupt + 1
        self.busy = True
        cur_time = time.time()
        if (cur_time - self.last_time) > self.bouncetime:
            if self.delta == 0:
                self.first_time = cur_time
            self.delta = self.delta + 1 # Add 1 liter
        self.last_time = cur_time

    def Debug(self, text):
        if (self.debug):
            Domoticz.Log(text)

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Log( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Log("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Log("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Log("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Log("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Log("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Log("Device LastLevel: " + str(Devices[x].LastLevel))
    return
