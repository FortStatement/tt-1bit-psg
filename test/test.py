import os
import sys
import wave

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Edge, RisingEdge
from cocotb.utils import get_sim_time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "driver"))
import psg

CLK_HZ = 10_000_000
CLK_NS = 1e9 / CLK_HZ


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)
    return psg.PSG(Writer(dut), CLK_HZ)


class Writer:
    def __init__(self, dut):
        self.dut = dut
        self.pending = []

    def __call__(self, addr, value):
        self.pending.append((addr, value))

    async def flush(self):
        dut = self.dut
        for addr, value in self.pending:
            dut.ui_in.value = value
            dut.uio_in.value = addr
            await ClockCycles(dut.clk, 1)
            dut.uio_in.value = addr | 0x10
            await ClockCycles(dut.clk, 4)
            dut.uio_in.value = addr
            await ClockCycles(dut.clk, 3)
        self.pending.clear()


async def flush(chip):
    await chip._write.flush()


async def period_clocks(dut, signal, periods):
    await RisingEdge(signal)
    t0 = get_sim_time("ns")
    for _ in range(periods):
        await RisingEdge(signal)
    return (get_sim_time("ns") - t0) / CLK_NS / periods


async def count_ones(dut, signal, clocks):
    ones = 0
    for _ in range(clocks):
        await RisingEdge(dut.clk)
        ones += int(signal.value)
    return ones


@cocotb.test()
async def test_reset_is_silent(dut):
    await start(dut)
    assert dut.uio_oe.value == 0x80
    assert await count_ones(dut, dut.audio, 2000) == 0
    assert int(dut.uo_out.value) & 0x0F == 0


@cocotb.test()
async def test_frequency(dut):
    chip = await start(dut)
    chip.set_ctrl(0, psg.PULSE, duty=2, vol=15)
    for freq, octave in [(4095, 7), (3000, 7), (2048, 6), (1000, 5)]:
        chip.set_freq(0, freq, octave)
        await flush(chip)
        expected = (3 << 27) / (freq * (1 << octave))
        measured = await period_clocks(dut, dut.voice0, 4)
        dut._log.info(f"freq={freq} oct={octave}: {measured:.1f} clocks, expected {expected:.1f}")
        assert abs(measured - expected) / expected < 0.005


@cocotb.test()
async def test_note_a4(dut):
    chip = await start(dut)
    chip.set_hz(0, psg.note_to_hz(69))
    chip.set_ctrl(0, vol=15)
    await flush(chip)
    hz = CLK_HZ / await period_clocks(dut, dut.voice0, 3)
    dut._log.info(f"A4: {hz:.2f} Hz")
    assert abs(hz - 440) < 0.5


@cocotb.test()
async def test_duty(dut):
    chip = await start(dut)
    chip.set_freq(0, 4096 - 1, 7)
    for duty, fraction in enumerate([0.125, 0.25, 0.5, 0.75]):
        chip.set_ctrl(0, psg.PULSE, duty=duty, vol=15)
        await flush(chip)
        await RisingEdge(dut.voice0)
        high = await count_ones(dut, dut.voice0, 4 * 768)
        assert abs(high / (4 * 768) - fraction) < 0.01


@cocotb.test()
async def test_sigma_delta_density(dut):
    chip = await start(dut)
    for vols in [(15, 0, 0), (7, 0, 0), (1, 0, 0), (15, 15, 15), (3, 9, 12)]:
        for v, vol in enumerate(vols):
            chip.set_freq(v, 0, 0)
            chip.sync(v)
            chip.set_ctrl(v, psg.PULSE, duty=0, vol=vol)
        await flush(chip)
        await ClockCycles(dut.clk, 4)
        ones = await count_ones(dut, dut.audio, 768)
        expected = 15 * sum(vols)
        dut._log.info(f"vols={vols}: {ones} ones / 768, expected {expected}")
        assert abs(ones - expected) <= 1


@cocotb.test()
async def test_waveforms_reach_the_output(dut):
    chip = await start(dut)
    dut.pcm_window.value = 64
    chip.set_hz(0, 2000)
    for wave_type in [psg.SAW, psg.TRIANGLE, psg.NOISE]:
        chip.set_ctrl(0, wave_type, vol=15)
        await flush(chip)
        levels = set()
        for _ in range(100):
            await Edge(dut.pcm_strobe)
            levels.add(int(dut.pcm.value))
        dut._log.info(f"wave {wave_type}: {len(levels)} distinct levels")
        assert len(levels) > 5


@cocotb.test()
async def test_freq_applies_on_high_byte(dut):
    chip = await start(dut)
    chip.set_freq(0, 4095, 7)
    chip.set_ctrl(0, vol=15)
    await flush(chip)
    before = await period_clocks(dut, dut.voice0, 2)
    chip._reg(0, psg.FREQ_LO, 0x00)
    await flush(chip)
    after = await period_clocks(dut, dut.voice0, 2)
    assert abs(after - before) < 4


@cocotb.test(skip="RENDER" not in os.environ)
async def test_render_demo(dut):
    chip = await start(dut)
    midi = psg.MidiPSG(chip)
    window = int(dut.pcm_window.value)
    sample_rate = CLK_HZ // window
    eighth = sample_rate // 6

    lead = [76, 79, 81, 79, 76, 74, 72, 74, 76, 76, 79, 81, 84, 81, 79, 76]
    bass = [45, 45, 52, 52, 41, 41, 48, 48, 43, 43, 50, 50, 45, 45, 52, 45]
    midi.program_change(0, psg.PULSE)
    midi.control_change(0, 1, 0x20)
    midi.program_change(1, psg.TRIANGLE)

    samples = bytearray()
    for step in range(len(lead)):
        midi.message(bytes([0x90, lead[step], 100]))
        midi.message(bytes([0x91, bass[step], 127]))
        if step % 2 == 0:
            midi.message(bytes([0x99, 100, 90]))
        await flush(chip)
        for i in range(eighth):
            if i == eighth // 4 and step % 2 == 0:
                midi.message(bytes([0x89, 100, 0]))
                await flush(chip)
            await Edge(dut.pcm_strobe)
            samples.append(min(255, int(dut.pcm.value) * 255 // window))
        midi.message(bytes([0x80, lead[step], 0]))
        midi.message(bytes([0x81, bass[step], 0]))

    os.makedirs("output", exist_ok=True)
    with wave.open("output/demo.wav", "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(1)
        f.setframerate(sample_rate)
        f.writeframes(bytes(samples))
