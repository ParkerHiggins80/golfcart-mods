#imports
import can #for reading CAN data from battery
import websockets #for sending data to the React App
import asyncio #completes tasks when it can and moves on if waiting
import json #for packaging data to be sent to the React App

#GLOBAL VARS
battery_data = {
    "soc":0,
    "v_out": 0.0,
    "v_cells": [0.0]*16,
    "current": 0.0,
    "temp_BMS": 0,
    "temp_cell1": 0,
    "temp_cell2": 0,
    "temp_cell3": 0,
    "temp_cell4": 0,
}
dataUpdated = False
connected_clients = set()

async def read_can():
    #import global vars
    global battery_data
    global dataUpdated

    #Open CAN bus connection
    bus = can.interface.Bus(channel='can0', bustype='socketcan') 

    while True:
        message = await asyncio.get_event_loop().run_in_executor(None,bus.recv) #assign data to a message

        match message.arbitration_id: #identify and 
            case 0x02028100: #SOC
                new_soc = message.data[3] #decrypt SOC
                if new_soc != battery_data["soc"]:
                    battery_data["soc"] = new_soc
                    dataUpdated = True
            case 0x02018100: #Output Voltage
                new_v_out = (message.data[2] << 8| message.data[3])/10
                if new_v_out != battery_data["v_out"]:
                    battery_data["v_out"] = new_v_out
                    dataUpdated = True
            case 0x18F812F3: #Cell Temp 3&1
                new_temp_cell3 = message.data[0] - 40 # byte 0
                new_temp_cell1 = message.data[3] - 40 # byte 4
                if new_temp_cell3 != battery_data["temp_cell3"]:
                    battery_data["temp_cell3"] = new_temp_cell3
                    dataUpdated = True
                if new_temp_cell1 != battery_data["temp_cell1"]:
                    battery_data["temp_cell1"] = new_temp_cell1
                    dataUpdated = True
            case 0x18F814F3: #Cell Temp 2
                new_temp_cell2 = message.data[3] # byte 3
                if new_temp_cell2 != battery_data["temp_cell2"]:
                    battery_data["temp_cell2"] = new_temp_cell2
                    dataUpdated = True
            case 0x18FC28F4:
                new_current = message.data[4] # byte 4, no scaling needed, value in amps
                if new_current != battery_data["current"]:
                    battery_data["current"] = new_current
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
    global battery_data
    global dataUpdated
    global connected_clients

    while True:
        if dataUpdated and connected_clients:
            data = json.dumps(battery_data)
            await asyncio.gather(*[client.send(data) for client in connected_clients])
        await asyncio.sleep(0.1) #wait 100ms then check again

async def main():
    async with websockets.serve(handler,"localhost", 8765):
        await asyncio.gather(read_can(), broadcast())

asyncio.run(main())
