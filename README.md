![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# 1-bit PSG

A three-voice sound chip for Tiny Tapeout (SKY130, 1x1 tile) with a single-bit sigma-delta audio output.
See [docs/info.md](docs/info.md) for how it works and the register map, and [driver/psg.py](driver/psg.py)
for the MicroPython/host driver with MIDI mapping.

## Development

All tools run in a podman container built on LibreLane 3.0.14 (the version the ttsky26d GDS action uses).
`./dev` builds it on first use and runs a command inside it; the SKY130 PDK lives in the `tt-pdk` volume.

    ./dev sh -c "cd test && make"                    # RTL tests (cocotb + Icarus)
    ./dev sh -c "cd test && python -m pytest test_driver.py"   # driver tests
    ./dev sh -c "cd test && RENDER=1 COCOTB_TEST_FILTER=test_render_demo make"
                                                     # render test/output/demo.wav (~10 min)
    ./dev ./harden.sh                                # full LibreLane flow into runs/wokwi
    cp runs/wokwi/final/pnl/tt_um_fortstatement_onebit_psg.pnl.v test/gate_level_netlist.v
    ./dev sh -c "cd test && make -B GATES=yes"       # gate-level tests

The PDK is fetched once with:

    ./dev ciel enable --pdk-root /pdk --pdk-family sky130 8afc8346a57fe1ab7934ba5a6056ea8b43078e71

## What is Tiny Tapeout?

Tiny Tapeout is an educational project that aims to make it easier and cheaper than ever to get your digital and analog designs manufactured on a real chip.

To learn more and get started, visit https://tinytapeout.com.

## Set up your Verilog project

1. Add your Verilog files to the `src` folder.
2. Edit the [info.yaml](info.yaml) and update information about your project, paying special attention to the `source_files` and `top_module` properties. If you are upgrading an existing Tiny Tapeout project, check out our [online info.yaml migration tool](https://tinytapeout.github.io/tt-yaml-upgrade-tool/).
3. Edit [docs/info.md](docs/info.md) and add a description of your project.
4. Adapt the testbench to your design. See [test/README.md](test/README.md) for more information.

The GitHub action will automatically build the ASIC files using [LibreLane](https://www.zerotoasiccourse.com/terminology/librelane/).

## Enable GitHub actions to build the results page

- [Enabling GitHub Pages](https://tinytapeout.com/faq/#my-github-action-is-failing-on-the-pages-part)

## Resources

- [FAQ](https://tinytapeout.com/faq/)
- [Digital design lessons](https://tinytapeout.com/digital_design/)
- [Learn how semiconductors work](https://tinytapeout.com/siliwiz/)
- [Join the community](https://tinytapeout.com/discord)
- [Build your design locally](https://www.tinytapeout.com/guides/local-hardening/)

## What next?

- [Submit your design to the next shuttle](https://app.tinytapeout.com/).
- Edit [this README](README.md) and explain your design, how it works, and how to test it.
- Share your project on your social network of choice:
  - LinkedIn [#tinytapeout](https://www.linkedin.com/search/results/content/?keywords=%23tinytapeout) [@TinyTapeout](https://www.linkedin.com/company/100708654/)
  - Mastodon [#tinytapeout](https://chaos.social/tags/tinytapeout) [@matthewvenn](https://chaos.social/@matthewvenn)
  - X (formerly Twitter) [#tinytapeout](https://twitter.com/hashtag/tinytapeout) [@tinytapeout](https://twitter.com/tinytapeout)
  - Bluesky [@tinytapeout.com](https://bsky.app/profile/tinytapeout.com)
