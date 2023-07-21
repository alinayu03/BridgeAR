import asyncio
from typing import Any
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.uuids import register_uuids
import sys
import whisper
import openai
import numpy as np


UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

DATA_SERVICE_UUID = "e5700001-7bac-429a-b4ce-57ff900f479d"
DATA_RX_CHAR_UUID = "e5700002-7bac-429a-b4ce-57ff900f479d"
DATA_TX_CHAR_UUID = "e5700003-7bac-429a-b4ce-57ff900f479d"

# 8 bit wav header
WAV_HEADER = (b"\x52\x49\x46\x46\x00\x00\x00\x00\x57\x41\x56\x45\x66\x6d\x74\x20"
              b"\x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x40\x1f\x00\x00"
              b"\x01\x00\x08\x00\x64\x61\x74\x61\x00\x00\x00\x00")
AUDIO_OUTPUT_PATH = "/tmp/audio.wav"


async def get_device():
    def match_repl_uuid(_: BLEDevice, adv: AdvertisementData):
        print(f"uuids={adv.service_uuids}", file=sys.stderr)
        return UART_SERVICE_UUID.lower() in adv.service_uuids

    return await BleakScanner.find_device_by_filter(match_repl_uuid)


def handle_disconnect(_: BleakClient):
    print("Device disconnected", file=sys.stderr)
    # cancelling all tasks effectively ends the program
    for task in asyncio.all_tasks():
        task.cancel()


def transcribe(fp: str):
    model = whisper.load_model("base")
    # Ideally we would just take in a tensor of the raw audio bytes rather than
    # pass in a path.
    result = model.transcribe(fp)
    transcript = result["text"]
    return transcript


def translate(transcript: str):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
                "content": "You are a translator. Translate this into English."},
            {"role": "user", "content": transcript}
        ]
    )
    return response['choices'][0]['message']['content']


class MonocleAudioServer:
    def __init__(self):
        register_uuids({
            DATA_SERVICE_UUID: "Monocle Raw Serivce",
            DATA_TX_CHAR_UUID: "Monocle Raw TX",
            DATA_RX_CHAR_UUID: "Monocle Raw RX",
        })

        self.audio_buffer = bytearray(WAV_HEADER)
        self.client: None | BleakClient = None

    async def __aenter__(self):
        device = await get_device()
        await self._connect(device)
        return self

    async def __aexit__(self, *args: Any):
        if self.client is not None:
            await self.client.disconnect()

    async def _connect(self, device: BLEDevice):
        self.client = BleakClient(device, handle_disconnect=handle_disconnect)
        await self.client.connect()

    def handle_repl_tx(self, _: BleakGATTCharacteristic, data: bytearray):
        sys.stdout.write(data.decode())
        sys.stdout.flush()

    def handle_data_tx(self, _: BleakGATTCharacteristic, data: bytearray):
        # Monocle emits 8-bit PCM audio bytes in signed format, but the WAV
        # standard expects 8-bit or smaller sized samples to be unsigned. Since
        # we manually prepend the WAV header and expect the output to be a WAV
        # file, we manually convert the signed bytes to unsigned by shifting
        # all bytes up by 0x80.
        # self.audio_buffer.extend(bytearray([(c + 0x80) & 0xff for c in data]))

        # Convert entire array at once
        signed_data = np.frombuffer(data, dtype=np.int8)
        unsigned_data = (signed_data + 0x80).astype(np.uint8)
        self.audio_buffer.extend(unsigned_data.tobytes())

    async def send_cmd(self, cmd: str, channel: BleakGATTCharacteristic, delay: float = 1.0):
        # Write cmd ending with \x04 (ctrl-d) as bytestring. ctrl-d is used
        # in place of \n as end of command in raw mode.
        # There is a hack adding a 1s sleep between commands due to issues
        # with resources not being ready if commands are sent too quickly.
        # This could be related to the bluetooth connection throughput and
        # realistically may be set to something much shorter than 1s.
        await self.client.write_gatt_char(channel, f"{cmd}\x04".encode())
        await asyncio.sleep(delay)

    async def send_payload(self):
        # A better way of doing this would probably be to separately deploy
        # this client code on the device and have it poll for a connected
        # bluetooth session - but hackathon constraints, we'll just deploy
        # the payload from this server using the repl channel.
        await self.client.start_notify(UART_TX_CHAR_UUID, self.handle_repl_tx)
        await self.client.start_notify(DATA_TX_CHAR_UUID, self.handle_data_tx)
        repl = self.client.services.get_service(UART_SERVICE_UUID)
        # data = self.client.services.get_service(DATA_SERVICE_UUID)
        repl_rx_char = repl.get_characteristic(UART_RX_CHAR_UUID)
        # data_rx_char = data.get_characteristic(DATA_RX_CHAR_UUID)

        # This sleep is needed here to wait for resources to be available,
        # but in theory there should be some way to be notified when the
        # device is ready.
        await asyncio.sleep(5)
        await self.client.write_gatt_char(repl_rx_char, b"\x03\x01")
        await self.send_cmd("print('hello world')", repl_rx_char)
        await self.send_cmd("import display, microphone, bluetooth, time", repl_rx_char)
        await self.send_cmd("initial_text = display.Text('hello world', 0, 0, display.WHITE)", repl_rx_char)
        await self.send_cmd("display.show(initial_text);", repl_rx_char)
        # We hardcode a fixed recording time of 5 seconds due to the
        # constraints of the hackathon, but this can be extended to using the
        # touch buttons on the device or to continually record and stream the
        # audio bytes to the server.
        await self.send_cmd("print('start recording')\nmicrophone.record(seconds=5.0, sample_rate=8000, bit_depth=8)", repl_rx_char, 5)
        await self.send_cmd("print('stop recording')", repl_rx_char)

        # Data may be lost without except OSError: pass
        await self.send_cmd("""
while True:
  chunk = microphone.read(100)
  if chunk == None:
    time.sleep(1)
    break
  while True:
    try:
      bluetooth.send(chunk)
      break
    except OSError:
      pass
""", repl_rx_char)
        await asyncio.sleep(1)

    def process_audio(self):
        # Rewrite data length in the wav header with the correct length.
        self.audio_buffer[4:8] = (len(self.audio_buffer) - 8).to_bytes(4)
        self.audio_buffer[40:44] = (len(self.audio_buffer) - 44).to_bytes(4)
        with open(AUDIO_OUTPUT_PATH, "wb") as f:
            f.write(self.audio_buffer)
        transcript = transcribe(AUDIO_OUTPUT_PATH)
        # translation = translate(transcript)
        print(f"TRANSCRIPTION: {transcript}")
        # print(f"TRANSLATION: {translation}")
        return transcript

    async def write_text(self, transcript: str):
        repl = self.client.services.get_service(UART_SERVICE_UUID)
        # data = self.client.services.get_service(DATA_SERVICE_UUID)
        repl_rx_char = repl.get_characteristic(UART_RX_CHAR_UUID)
        # data_rx_char = data.get_characteristic(DATA_RX_CHAR_UUID)
        await self.client.write_gatt_char(repl_rx_char, b"\x03\x01")
        await self.send_cmd("print('transcription')", repl_rx_char)
        await self.send_cmd("import display, microphone, bluetooth, time", repl_rx_char)
        await self.send_cmd(f"transcript = display.Text('{transcript}', 0, 0, display.WHITE)", repl_rx_char)
        await self.send_cmd("display.show(transcript);", repl_rx_char)

async def main():
    async with MonocleAudioServer() as audio_server:
        await audio_server.send_payload()
        transcript = audio_server.process_audio()
        await audio_server.write_text(transcript)

if __name__ == "__main__":
    asyncio.run(main())
