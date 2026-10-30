import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "driver"))
import psg

CLK_HZ = 10_000_000


class Regs:
    def __init__(self):
        self.writes = []
        self.ctrl = [0] * psg.VOICES
        self.freq = [None] * psg.VOICES
        self.freq_lo = 0

    def __call__(self, addr, value):
        self.writes.append((addr, value))
        voice, reg = addr >> 2, addr & 3
        if reg == psg.FREQ_LO:
            self.freq_lo = value
        elif reg == psg.FREQ_HI:
            self.freq[voice] = ((value & 0xF) << 8 | self.freq_lo, value >> 4)
        elif reg == psg.CTRL:
            self.ctrl[voice] = value

    def vol(self, voice):
        return self.ctrl[voice] & 0xF

    def wave(self, voice):
        return self.ctrl[voice] >> 6

    def hz(self, voice):
        return psg.regs_to_hz(*self.freq[voice], CLK_HZ)


@pytest.mark.parametrize("note", range(21, 109))
def test_every_piano_note_is_in_tune(note):
    freq, octave = psg.hz_to_regs(psg.note_to_hz(note), CLK_HZ)
    assert 0 < freq < 4096
    error = psg.regs_to_hz(freq, octave, CLK_HZ) / psg.note_to_hz(note)
    cents = 1200 * abs(math.log2(error))
    assert cents < 2


def make():
    regs = Regs()
    return regs, psg.MidiPSG(psg.PSG(regs, CLK_HZ))


def test_notes_take_free_voices_then_steal_the_oldest():
    regs, midi = make()
    for note in (60, 64, 67):
        midi.message(bytes([0x90, note, 127]))
    assert [round(regs.hz(v)) for v in range(3)] == [262, 330, 392]
    assert all(regs.vol(v) == 15 for v in range(3))

    midi.message(bytes([0x90, 72, 127]))
    assert round(regs.hz(0)) == 523


def test_note_off_frees_the_voice():
    regs, midi = make()
    midi.message(bytes([0x90, 60, 127]))
    midi.message(bytes([0x90, 64, 127]))
    midi.message(bytes([0x80, 60, 0]))
    assert regs.vol(0) == 0 and regs.vol(1) == 15
    midi.message(bytes([0x90, 67, 127]))
    midi.message(bytes([0x90, 71, 127]))
    assert round(regs.hz(2)) == 392 and round(regs.hz(0)) == 494


def test_velocity_zero_is_note_off():
    regs, midi = make()
    midi.message(bytes([0x90, 60, 127]))
    midi.message(bytes([0x90, 60, 0]))
    assert regs.vol(0) == 0


def test_program_and_drum_channel_pick_the_wave():
    regs, midi = make()
    midi.message(bytes([0xC0, psg.TRIANGLE]))
    midi.message(bytes([0x90, 60, 64]))
    midi.message(bytes([0x99, 36, 64]))
    assert regs.wave(0) == psg.TRIANGLE
    assert regs.wave(1) == psg.NOISE
    assert regs.vol(0) == 8
