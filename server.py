import asyncio
import json
import time
import serial
from foxglove_websocket import run_cancellable
from foxglove_websocket.server import FoxgloveServer, FoxgloveServerListener
from foxglove_websocket.types import (
    ChannelId,
    ClientChannel,
    ClientChannelId,
    ServiceId,
)

SERIAL_PORT = "/dev/cu.usbserial-210"
SERIAL_BAUDRATE = 115200
ser = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE)
def read_from_xbee():
    while True:
        line = ser.readline().decode().strip()
        #print(f"Raw line from serial: {line}")  # Debug print
        data = parse_imu_data(line)
        if data:
            #print(f"Parsed data: {data}")  # Debug print
            yield data
def parse_imu_data(line):
    try:
        parts = line.split(',')
        # If the data doesn't have the expected number of columns, return None
        if len(parts) != 14:
            print(f"Invalid data: {line}")  # Debug print
            ser.flushInput()
            return None

        data = {
            "rtcDate": parts[0],
            "rtcTime": parts[1],
            "aX": float(parts[2]),
            "aY": float(parts[3]),
            "aZ": float(parts[4]),
            "gX": float(parts[5]),
            "gY": float(parts[6]),
            "gZ": float(parts[7]),
            "mX": float(parts[8]),
            "mY": float(parts[9]),
            "mZ": float(parts[10]),
            "imu_degC": float(parts[11]),
            "output_Hz": float(parts[12]),
        }

        return data
    except:
        return None

async def main():
    class Listener(FoxgloveServerListener):
        async def on_subscribe(self, server: FoxgloveServer, channel_id: ChannelId):
            print("First client subscribed to", channel_id)

        async def on_unsubscribe(self, server: FoxgloveServer, channel_id: ChannelId):
            print("Last client unsubscribed from", channel_id)

        async def on_client_advertise(
            self, server: FoxgloveServer, channel: ClientChannel
        ):
            print("Client advertise:", json.dumps(channel))

        async def on_client_unadvertise(
            self, server: FoxgloveServer, channel_id: ClientChannelId
        ):
            print("Client unadvertise:", channel_id)

        async def on_client_message(
            self, server: FoxgloveServer, channel_id: ClientChannelId, payload: bytes
        ):
            msg = json.loads(payload)
            print(f"Client message on channel {channel_id}: {msg}")

        async def on_service_request(
            self,
            server: FoxgloveServer,
            service_id: ServiceId,
            call_id: str,
            encoding: str,
            payload: bytes,
        ) -> bytes:
            if encoding != "json":
                return json.dumps(
                    {"success": False, "error": f"Invalid encoding {encoding}"}
                ).encode()

            request = json.loads(payload)
            if "data" not in request:
                return json.dumps(
                    {"success": False, "error": f"Missing key 'data'"}
                ).encode()

            print(f"Service request on service {service_id}: {request}")
            return json.dumps(
                {"success": True, "message": f"Received boolean: {request['data']}"}
            ).encode()

    async with FoxgloveServer(
        "0.0.0.0",
        8765,
        "example server",
        capabilities=["clientPublish", "services"],
        supported_encodings=["json"],
    ) as server:
        server.set_listener(Listener())
        chan_id = await server.add_channel(
            {
                "topic": "imu_data",
                "encoding": "json",
                "schemaName": "IMUData",
                "schema": json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "rtcDate": {"type": "string"},
                            "rtcTime": {"type": "string"},
                            "aX": {"type": "number"},
                            "aY": {"type": "number"},
                            "aZ": {"type": "number"},
                            "gX": {"type": "number"},
                            "gY": {"type": "number"},
                            "gZ": {"type": "number"},
                            "mX": {"type": "number"},
                            "mY": {"type": "number"},
                            "mZ": {"type": "number"},
                            "imu_degC": {"type": "number"},
                            "output_Hz": {"type": "number"},
                        },
                    }
                ),
                "schemaEncoding": "jsonschema",
            }
        )
        await server.add_service(
            {
                "name": "example_set_bool",
                "requestSchema": json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "data": {"type": "boolean"},
                        },
                    }
                ),
                "responseSchema": json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "message": {"type": "string"},
                        },
                    }
                ),
                "type": "example_set_bool",
            }
        )
        await asyncio.sleep(10)
        while True:
            print("Attempting to get next data...")  # Debug print
            try:
                data = next(read_from_xbee())
                print(f"Received data: {data}")  # Debug print
                await asyncio.sleep(0.01)
                await server.send_message(
                    chan_id,
                    time.time_ns(),
                    json.dumps(data).encode("utf8"),
                )
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(1)
    

if __name__ == "__main__":
    run_cancellable(main())