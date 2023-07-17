import asyncio
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.uuids import register_uuids
import sys


UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

DATA_SERVICE_UUID = "e5700001-7bac-429a-b4ce-57ff900f479d"
DATA_RX_CHAR_UUID = "e5700002-7bac-429a-b4ce-57ff900f479d"
DATA_TX_CHAR_UUID = "e5700003-7bac-429a-b4ce-57ff900f479d"

register_uuids({
    DATA_SERVICE_UUID: "Monocle Raw Serivce",
    DATA_TX_CHAR_UUID: "Monocle Raw TX",
    DATA_RX_CHAR_UUID: "Monocle Raw RX",
})


def match_repl_uuid(device: BLEDevice, adv: AdvertisementData):
    sys.stderr.write(f"uuids={adv.service_uuids}\n")
    return UART_SERVICE_UUID.lower() in adv.service_uuids


async def get_device():
 return await BleakScanner.find_device_by_filter(match_repl_uuid)


def handle_disconnect(_: BleakClient):
    sys.stderr.write("\r\nDevice was disconnected.\r\n")
    # cancelling all tasks effectively ends the program
    for task in asyncio.all_tasks():
        task.cancel()


def handle_repl_rx(_: BleakGATTCharacteristic, data: bytearray):
    sys.stdout.write(data.decode())
    sys.stdout.flush()


def handle_data_rx(_: BleakGATTCharacteristic, data: bytearray):
    hex = data.hex(' ', 1)
    sys.stderr.write(f'RX: {hex} {data.decode()}\r\n')
    sys.stderr.flush()


async def send_cmd(cmd: str, client: BleakClient, channel: BleakGATTCharacteristic):
    await client.write_gatt_char(channel, f"{cmd}\x04".encode())
    await asyncio.sleep(1)


async def connect(device):
    async with BleakClient(device, handle_disconnect=None) as client:
        await client.start_notify(UART_TX_CHAR_UUID, handle_repl_rx)
        await client.start_notify(DATA_TX_CHAR_UUID, handle_data_rx)
        # loop = asyncio.get_running_loop()
        repl = client.services.get_service(UART_SERVICE_UUID)
        data = client.services.get_service(DATA_SERVICE_UUID)
        repl_rx_char = repl.get_characteristic(UART_RX_CHAR_UUID)
        data_rx_char = data.get_characteristic(DATA_RX_CHAR_UUID)
        await asyncio.sleep(7)
        await client.write_gatt_char(repl_rx_char, b"\x03\x01")
        await send_cmd("print('hello world')", client, repl_rx_char)
        await send_cmd("import display", client, repl_rx_char)
        await send_cmd("initial_text = display.Text('hello world', 0, 0, display.WHITE)", client, repl_rx_char)
        await send_cmd("display.show(initial_text);", client, repl_rx_char)
        await send_cmd("bluetooth.connected()")
        await send_cmd("len = bluetooth.max_length()")
        await send_cmd("str = 'world hello!'")
        
        await asyncio.sleep(3)


async def get_device_and_connect():
    device = await get_device()
    await connect(device)


asyncio.run(get_device_and_connect())
