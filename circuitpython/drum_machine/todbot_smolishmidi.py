# The MIT License (MIT)
#
# Copyright (c) 2023 Tod Kurt
# Copyright (c) 2019 Alethea Flowers for Winterbloom
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


"""A minimalist MIDI library. Copied from Winterbloom SmolMIDI but reduced and made to work w/ UARTs."""

# Message type constants.
NOTE_OFF = 0x80
NOTE_ON = 0x90
AFTERTOUCH = 0xA0
CONTROLLER_CHANGE = CC = 0xB0
PROGRAM_CHANGE = 0xC0
CHANNEL_PRESSURE = 0xD0
PITCH_BEND = 0xE0
SYSTEM_EXCLUSIVE = SYSEX = 0xF0
SONG_POSITION = 0xF2
SONG_SELECT = 0xF3
BUS_SELECT = 0xF5
TUNE_REQUEST = 0xF6
SYSEX_END = 0xF7
CLOCK = 0xF8
TICK = 0xF9
START = 0xFA
CONTINUE = 0xFB
STOP = 0xFC
ACTIVE_SENSING = 0xFE
SYSTEM_RESET = 0xFF

_LEN_0_MESSAGES = set(
    [
        TUNE_REQUEST,
        SYSEX,
        SYSEX_END,
        CLOCK,
        TICK,
        START,
        CONTINUE,
        STOP,
        ACTIVE_SENSING,
        SYSTEM_RESET,
    ]
)
_LEN_1_MESSAGES = set([PROGRAM_CHANGE, CHANNEL_PRESSURE, SONG_SELECT, BUS_SELECT])
_LEN_2_MESSAGES = set([NOTE_OFF, NOTE_ON, AFTERTOUCH, CC, PITCH_BEND, SONG_POSITION])


def _is_channel_message(status_byte):
    return status_byte >= NOTE_OFF and status_byte <= PITCH_BEND + 0x0F

class Message:
    def __init__(self):
        self.type = None
        self.channel = None
        self.data = None

    def __bytes__(self):
        status_byte = self.type
        if self.channel:
            status_byte |= self.channel

        return bytes([status_byte] + list(self.data if self.data else []))


class MidiIn:
    def __init__(self, port, enable_running_status=False):
        self._port = port
        self._read_buf = bytearray(1)
        self._running_status_enabled = enable_running_status
        self._running_status = None
        self._outstanding_sysex = False
        self._error_count = 0

    @property
    def error_count(self):
        return self._error_count

    def receive(self):
        # Before we do anything, check and see if there's an unprocessed
        # sysex message pending. If so, throw it away. The caller has
        # to call receive_sysex if they care about the bytes.
        #if self._outstanding_sysex:
        #    self.receive_sysex(0)

        # Read the status byte for the next message, and perhaps whole message
        #result = self._port.readinto(self._read_buf, 1)
        result = self._port.readinto(self._read_buf)

        # No message ready.
        if not result:
            return None

        print("smol result:",result)
        message = Message()
        data_bytes = bytearray(2)

        # Is this a status byte?
        status_byte = self._read_buf[0]
        is_status = status_byte & 0x80

        # If not, see if we have a running status byte.
        if not is_status:
            if self._running_status_enabled and self._running_status:
                #data_bytes = [status_byte]
                status_byte = self._running_status
            # If not a status byte and no running status, this is
            # invalid data.
            else:
                self._error_count += 1
                return None

        # Is this a channel message, if so, let's figure out the right
        # message type and set the message's channel property.
        if _is_channel_message(status_byte):
            # Only set the running status byte for channel messages.
            self._running_status = status_byte
            # Mask off the channel nibble.
            message.type = status_byte & 0xF0
            message.channel = status_byte & 0x0F
        else:
            message.type = status_byte

        # Read the appropriate number of bytes for each message type.
        if message.type in _LEN_2_MESSAGES:
            #_read_n_bytes(self._port, self._read_buf, data_bytes, 2 - len(data_bytes))
            data_bytes = bytearray(2)
            self._port.readinto(data_bytes)
            message.data = data_bytes
        elif message.type in _LEN_1_MESSAGES:
            #_read_n_bytes(self._port, self._read_buf, data_bytes, 1 - len(data_bytes))
            data_bytes = bytearray(1)
            self._port.readinto(data_bytes)
            message.data = data_bytes

        # If this is a sysex message, set the pending sysex flag so we
        # can throw the message away if the user doesn't process it.
        if message.type == SYSEX:
            self._outstanding_sysex = True

        # Check the data bytes for corruption. If the data bytes have any status bytes
        # embedded, it probably means the buffer overflowed. Either way, discard the
        # message.
        # TODO: Figure out a better way to detect and deal with this upstream.
        for b in data_bytes:
            if b & 0x80:
                self._error_count += 1
                return None

        return message
