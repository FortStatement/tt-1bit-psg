<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

A three-voice sound chip with a single-bit audio output.

Each voice has a 20-bit phase accumulator advanced by a 12-bit frequency word, at one of eight octave rates. The top
bits of the phase are shaped into a 4-bit level: a pulse wave (12.5, 25, 50 or 75% duty), a saw, a triangle, or
noise. Noise samples a free-running 17-bit LFSR 16 times per period, so it is pitched with the voice. The level is
scaled by a 4-bit volume.

To fit one tile the voices share a single datapath. Their state sits in a three-stage ring that rotates every clock;
the voice at the head is updated, and its level is added to a first-order sigma-delta modulator. The modulator's carry
is the audio output: a pulse-density stream whose average is the sum of the voices / 768. An RC low-pass filter, such
as the one on the TT Audio Pmod, turns it into an analog signal.

Voice frequency: `f = f_clk * freq * 2^oct / (3 * 2^27)`. At the intended 10 MHz clock the octaves span 51 Hz (freq 2048,
oct 0) to 13 kHz (freq 4095, oct 7); lower notes use smaller freq words (A0 is 1107 in oct 0). Every piano note lands
within 2 cents.

### Registers

Write a register by putting the data on `ui_in`, the address on `uio[3:0]` and raising `uio[4]` (WR). Hold WR high
for at least 4 clocks, and keep the data and address stable from before WR rises until 3 clocks after it falls. While
WR is high the register is rewritten every time its voice comes round, so a longer pulse is harmless.

The address is `{voice[1:0], reg[1:0]}`, for voices 0 to 2:

| reg | Name    | Bits                                   | Notes                                              |
|-----|---------|----------------------------------------|----------------------------------------------------|
| 0   | FREQ_LO | `freq[7:0]`                            | Staged; applied together with FREQ_HI              |
| 1   | FREQ_HI | `-, oct[2:0], freq[11:8]`              | Write after FREQ_LO                                |
| 2   | CTRL    | `wave[1:0], duty[1:0], vol[3:0]`       | wave: 0 pulse, 1 saw, 2 triangle, 3 noise          |
| 3   | SYNC    | any                                    | Restarts the voice's phase                         |

After reset all voices are silent (volume 0).

## How to test

Clock the design at 10 MHz and connect the TT Audio Pmod to the output Pmod header. From the demo board's MicroPython,
drive `ui_in` and `uio[4:0]` with the write sequence above. `driver/psg.py` in the repository computes the register
values for a note and maps MIDI messages onto the voices.

For example, A4 (440 Hz) at full volume on voice 0, 50% pulse: write 0xA7 to address 0, 0x38 to address 1 and 0x2F to
address 2.

`uo_out[2:0]` carry each voice's raw pulse wave and `uo_out[3]` their XOR, for listening without the sigma-delta.

## External hardware

TT Audio Pmod (or any RC low-pass filter and amplifier on `uo_out[7]`).
