#imports
import can #for reading CAN data from battery
import websockets #for sending data to the React App
import asyncio #completes tasks when it can and moves on if waiting
import json #for packaging data to be sent to the React App
import RPi.GPIO as GPIO #for reading speed sensor data
import time #for calculating speed from sensor data

#GLOBAL VARS
cart_data = {
    "soc":0,
    "v_out": 0.0,
    "v_cells": [0.0]*16,
    "current": 0.0,
    "temp_BMS": 0,
    "temp_cell1": 0,
    "temp_cell2": 0,
    "temp_cell3": 0,
    "temp_cell4": 0,
    "speed_MPH": 0,
}
dataUpdated = False
connected_clients = set()
pulseList = []
GPIO.setmode(GPIO.BCM)
GPIO.setup(2, GPIO.IN) #speed sensor on pin 2
tire_circumference = 1.715 #fine tune this value for more accurate speed readings, in meters (0.5m per pulse)


async def read_can():
    #import global vars
    global cart_data
    global dataUpdated

    #Open CAN bus connection
    bus = can.interface.Bus(channel='can0', interface='socketcan')

    while True:
        message = await asyncio.get_event_loop().run_in_executor(None,bus.recv) #assign data to a message

        match message.arbitration_id: #identify and 
            case 0x02028100: #SOC
                new_soc = message.data[3] #decrypt SOC
                if new_soc != cart_data["soc"]:
                    cart_data["soc"] = new_soc
                    dataUpdated = True
            case 0x02018100: #Output Voltage
                new_v_out = (message.data[2] << 8| message.data[3])/10
                if new_v_out != cart_data["v_out"]:
                    cart_data["v_out"] = new_v_out
                    dataUpdated = True
            case 0x18F812F3: #Cell Temp 3&1
                new_temp_cell3 = message.data[0] - 40 # byte 0
                new_temp_cell1 = message.data[3] - 40 # byte 4
                if new_temp_cell3 != cart_data["temp_cell3"]:
                    cart_data["temp_cell3"] = new_temp_cell3
                    dataUpdated = True
                if new_temp_cell1 != cart_data["temp_cell1"]:
                    cart_data["temp_cell1"] = new_temp_cell1
                    dataUpdated = True
            case 0x18F814F3: #Cell Temp 2
                new_temp_cell2 = message.data[3] # byte 3
                if new_temp_cell2 != cart_data["temp_cell2"]:
                    cart_data["temp_cell2"] = new_temp_cell2
                    dataUpdated = True
            case 0x18FC28F4:
                new_current = message.data[4] # byte 4, no scaling needed, value in amps
                if new_current != cart_data["current"]:
                    cart_data["current"] = new_current
                    dataUpdated = True
            case _: #none
                pass
            #case: #Cell 1 Voltage
            #case: #Cell 2 Voltage
            #case: #Cell 3 Voltage
            #case: #Cell 4 Voltage...
            #case: #temp

async def handler(websocket):
    #import global vars
    global connected_clients
    
    connected_clients.add(websocket) #add
    try:
        await websocket.wait_closed() #wait till closed
    finally:
        connected_clients.remove(websocket) #remove after closed

async def broadcast():
    #import global vars
    global cart_data
    global dataUpdated
    global connected_clients

    while True:
        if dataUpdated and connected_clients:
            data = json.dumps(cart_data)
            await asyncio.gather(*[client.send(data) for client in connected_clients])
        await asyncio.sleep(0.1) #wait 100ms then check again

async def speed_calculator():
    #import global vars
    global cart_data
    global tire_circumference
    global pulseList

    while True:
        #append new pulses to list
        now = time.time()
        if GPIO.input(2) == GPIO.LOW: #if sensor is triggered
            pulseList.append(now) #add time of pulse to list
            print(f"pulse detected")
        await asyncio.sleep(0.01) #check every 10ms

        #remove old pulses
        cutoff = now - 2 #only consider pulses in the last 2 seconds
        pulseList[:] = [pulse for pulse in pulseList if pulse >= cutoff]

        #calculate speed from pulse count
        if len(pulseList) < 2:
            cart_data["speed_MPH"] = 0
        else:
            time_diff = pulseList[-1] - pulseList[0] #time between first and last pulse
            speed_mps = (len(pulseList) - 1) / time_diff * tire_circumference #calculate speed in m/s by multiplying by circumerfence
            cart_data["speed_MPH"] = speed_mps * 2.237 #convert to MPH by multiplying by 2.237


async def main():
    async with websockets.serve(handler,"localhost", 8765):
        await asyncio.gather(read_can(), broadcast(), speed_calculator())

asyncio.run(main())
