VOICES = 3

FREQ_LO = 0
FREQ_HI = 1
CTRL = 2
SYNC = 3

PULSE = 0
SAW = 1
TRIANGLE = 2
NOISE = 3

ALL_SOUND_OFF = 120
ALL_NOTES_OFF = 123

_CLOCKS_PER_VISIT = 3
_ACC_BITS = 20
_OCTAVE_PRESCALE_BITS = 7
_DIVISOR = _CLOCKS_PER_VISIT << (_ACC_BITS + _OCTAVE_PRESCALE_BITS)


def hz_to_regs(hz, clk_hz):
    for octave in range(8):
        freq = round(hz * _DIVISOR / (clk_hz * (1 << octave)))
        if freq < 4096:
            return freq, octave
    raise ValueError("frequency too high")


def regs_to_hz(freq, octave, clk_hz):
    return clk_hz * freq * (1 << octave) / _DIVISOR


def note_to_hz(note):
    return 440.0 * 2 ** ((note - 69) / 12)


class PSG:
    def __init__(self, write, clk_hz):
        self._write = write
        self.clk_hz = clk_hz

    def _reg(self, voice, reg, value):
        self._write((voice << 2) | reg, value & 0xFF)

    def set_freq(self, voice, freq, octave):
        self._reg(voice, FREQ_LO, freq)
        self._reg(voice, FREQ_HI, (octave << 4) | (freq >> 8))

    def set_hz(self, voice, hz):
        self.set_freq(voice, *hz_to_regs(hz, self.clk_hz))

    def set_ctrl(self, voice, wave=PULSE, duty=2, vol=15):
        self._reg(voice, CTRL, (wave << 6) | (duty << 4) | vol)

    def sync(self, voice):
        self._reg(voice, SYNC, 0)

    def silence(self):
        for v in range(VOICES):
            self.set_ctrl(v, vol=0)


class MidiPSG:

    DRUM_CHANNEL = 9

    def __init__(self, psg):
        self.psg = psg
        self.wave = [PULSE] * 16
        self.duty = [2] * 16
        self.notes = [None] * VOICES
        self.lru = list(range(VOICES))

    def _use(self, voice):
        self.lru.remove(voice)
        self.lru.append(voice)

    def note_on(self, channel, note, velocity):
        if velocity == 0:
            self.note_off(channel, note)
            return
        voice = None
        for v in self.lru:
            if self.notes[v] is None:
                voice = v
                break
        if voice is None:
            voice = self.lru[0]
        self._use(voice)
        self.notes[voice] = (channel, note)
        wave = NOISE if channel == self.DRUM_CHANNEL else self.wave[channel]
        self.psg.set_hz(voice, note_to_hz(note))
        self.psg.set_ctrl(voice, wave, self.duty[channel], max(1, velocity >> 3))

    def note_off(self, channel, note):
        for v in range(VOICES):
            if self.notes[v] == (channel, note):
                self.notes[v] = None
                self.psg.set_ctrl(v, vol=0)

    def program_change(self, channel, program):
        self.wave[channel] = program % 4

    def control_change(self, channel, control, value):
        if control == 1:
            self.duty[channel] = value >> 5
        elif control in (ALL_SOUND_OFF, ALL_NOTES_OFF):
            for v in range(VOICES):
                if self.notes[v] is not None and self.notes[v][0] == channel:
                    self.note_off(*self.notes[v])

    def message(self, data):
        status = data[0] & 0xF0
        channel = data[0] & 0x0F
        if status == 0x90:
            self.note_on(channel, data[1], data[2])
        elif status == 0x80:
            self.note_off(channel, data[1])
        elif status == 0xC0:
            self.program_change(channel, data[1])
        elif status == 0xB0:
            self.control_change(channel, data[1], data[2])
