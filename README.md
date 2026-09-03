# OpenRemote Rev6 Hardware

<p align="center">
  <img src="images/OpenRemote%20Rev6.jpeg" alt="OpenRemote Rev6 universal remote" width="100%">
</p>

OpenRemote Rev6 is an open-source, offline smart remote based on the excellent [OMOTE hardware](https://github.com/OMOTE-Community/OMOTE-Hardware). It combines a 2.8-inch capacitive touchscreen with physical buttons, infrared, Wi-Fi, Bluetooth, an ESP32-S3, expandable storage, and a fully 3D-printable enclosure.

Rev6 focuses on making the remote easier to source, nicer to print, more serviceable, and ready for dock charging—while retaining support for the original Adafruit display.

> **Firmware:** [OpenRemote Firmware](https://github.com/LORDSn1per/OpenRemote-Firmware)

## What is new in Revision 6?

- **New IPS display support.** Rev6 supports the EastRising/BuyDisplay ER-TFT028A2-4 capacitive display with a separate six-pin touch FPC. It is brighter, sharper, has much better viewing angles, and is easier to source than the original display.
- **Original display compatibility.** The original Adafruit Product 2770/CH280QV10-CT display remains supported through the alternate display configuration and matching front cover.
- **Built-in microphone.** A rear-mounted digital I2S microphone provides hardware support for voice control, voice search, and future assistant features.
- **Faster charging.** The TP4056 charging circuit is configured for up to approximately 1 A, subject to the battery, power source, and thermal conditions.
- **Dock charging input.** Rev6 includes a dedicated 5 V input before the fuse, feeding the pogo-pin charging dock contacts or any other 5 V source.
- **Improved serviceability.** Five rear-installed M3 × 8 mm screws secure the PCB and enclosure, making the remote easier to assemble and reopen.
- **Updated PCB branding.** The board is now branded OpenRemote and includes a QR code linking directly to the firmware repository.

<p align="center">
  <img src="images/OpenRemote%20Rev6%20Brochure.jpeg" alt="OpenRemote Rev6 feature overview" width="100%">
</p>

## New BuyDisplay LCD

The recommended Rev6 screen is the 2.8-inch 240×320 EastRising/BuyDisplay IPS TFT with capacitive touch. Its separate six-pin touch cable connects to the new J6 connector on the Rev6 PCB.

The BuyDisplay assembly is approximately **0.8 mm thicker** than the original Adafruit screen. It therefore requires the newly updated BuyDisplay front cover plate. Do not try to force the thicker display into the original Adafruit cover.

Printable parts are split by display, so each folder contains a complete, matched set:

- [`CAD/BuyDisplay LCD/`](CAD/BuyDisplay%20LCD) — use **`Cover Plate 5mm (+1mm) Rev6-v37.stl`** with the new BuyDisplay screen.
- [`CAD/Adafruit LCD/`](CAD/Adafruit%20LCD) — use **`Cover Plate 4mm (+0mm) Rev6-v37.stl`** with the original Adafruit screen.

Each folder also carries a **Bambu Lab 3MF project** prepared for multicolour printing.

| BuyDisplay screen | New and original screens |
|:---:|:---:|
| <img src="images/New%20LCD.jpeg" alt="BuyDisplay 2.8-inch IPS capacitive display" width="300"> | <img src="images/New%20Vs%20Old%20Screen.JPG" alt="BuyDisplay screen beside the original Adafruit screen" width="620"> |

## Redesigned printed buttons

The Rev6 button system has been redesigned for a cleaner, more professional finish:

- The button grid now prints as **two interlocking halves** that click together.
- Separating the grid makes multicolour button graphics easier to print cleanly.
- Button faces are now completely smooth.
- The old physical cut-outs used to form button icons have been removed.
- Icons and labels can instead be printed directly into the smooth button surfaces for sharper graphics and a much nicer feel.
- The supplied Bambu Lab 3MF project contains the prepared colour-printing setup.

## Rear-case options

The Rev6 enclosure is available with two rear-shell choices:

1. **Normal rear case** — the standard shell for USB-C charging (`Case - Screws and No Pogo Pins Rev6-v37.stl`).
2. **Pogo-pin rear case** — adds two charging contacts for the self-aligning charging dock (`Case - Screws with Pogo Pins Rev6-v37.stl`).

The spring-loaded pogo pins live in the dock; the remote carries fixed gold-plated contacts, so there is nothing sprung to wear out in the handheld part.

## Charging dock

The Rev6 charging dock is a self-aligning cradle that charges the remote through the pogo-pin rear case, and doubles as an always-on IR and sub-GHz blaster in its own right.

- **Pogo-pin charging.** Two spring-loaded pins meet the fixed contacts in the pogo rear case, so the remote charges by being set down rather than plugged in.
- **Independent ESP32-C3.** An ESP32-C3 Super Mini gives the dock its own Wi-Fi and Bluetooth, so it can act while the remote is asleep or away from the cradle.
- **Four-emitter IR blaster.** Four MHL512IR059CRT 940 nm emitters run in parallel, each through its own 39 Ω 0.5 W resistor, switched by an FS8205A dual MOSFET. Designed for roughly 95 mA per emitter in pulsed remote-control service, giving the dock far more IR reach than the handheld unit.
- **433 MHz sub-GHz radio.** A CC1101 module on SPI adds control of RF devices that infrared cannot reach — blinds, garage doors, and similar.
- **Status LED and button.** A tactile button on GPIO3 with hardware debounce, plus a status indicator.
- **Powered by USB-C or JST.** Power comes in through the ESP32-C3 module's USB-C, or the JST XH 2-pin input (J1).
- **Serviceable.** A 45 × 60 mm two-layer PCB on a 37 × 52 mm M3 mounting pattern, with a separate printed base lid.

> **Firmware note:** the IR bank is sized for pulsed use. Firmware must not hold `IR_PWM` high continuously.

### Dock files

- Printable parts: [`CAD/Dock/STL`](CAD/Dock/STL) — dock shell, base lid, and menu button, plus a Bambu Lab 3MF project in [`CAD/Dock`](CAD/Dock).
- Fusion source: [`CAD/Charging Dock Rev6-v47.f3z`](CAD/Charging%20Dock%20Rev6-v47.f3z)
- KiCad source: [`PCB/Dock Rev6`](PCB/Dock%20Rev6) — includes its own [project README](PCB/Dock%20Rev6/README.md) covering footprints, sourcing notes, and the Fusion handoff transform.
- [Gerber and drill ZIP](PCB/Dock%20Rev6/Productions%20Files/gerber.zip)
- [Component placement list (CPL)](PCB/Dock%20Rev6/Productions%20Files/CPL.csv)
- [Bill of materials (BOM)](PCB/Dock%20Rev6/Productions%20Files/BOM.xlsx)

> Several dock BOM lines have no LCSC code yet: the 100 Ω and 100 kΩ resistors, the 100 µF electrolytic, the 39 Ω 0.5 W IR resistors, and both modules (ESP32-C3 Super Mini, CC1101). The two modules are owner-supplied and not intended for assembly-house placement. Fill the remaining passives before ordering an assembled dock PCB.

## PCB files

The complete KiCad source is in [`PCB/Revision 6`](PCB/Revision%206). Custom symbols, footprints, and 3D models are included with the project.

The exact production files prepared for the Rev6 manufacturing order are here:

- [Gerber and drill ZIP](PCB/Revision%206/PCB%20Production%20Files/gerber.zip)
- [Component placement list (CPL)](PCB/Revision%206/PCB%20Production%20Files/CPL.csv)
- [Bill of materials (BOM)](PCB/Revision%206/PCB%20Production%20Files/BOM.xlsx)

The PCB is a two-layer design. The production set was exported using the **EastRising Capacitive LCD** assembly variant. The original Adafruit display remains represented in the KiCad project as an alternate variant.

> MIC1, the microphone module, does not currently have a JLCPCB/LCSC placement code in the production BOM. Source and fit it separately if your assembler cannot supply it.

## Core hardware features

- ESP32-S3 with Wi-Fi and Bluetooth
- 2.8-inch 240×320 capacitive touchscreen
- Physical navigation, media, volume, channel, activity, and colour buttons
- High-power infrared output
- MicroSD storage
- Motion-based wake support
- Built-in I2S microphone
- USB-C charging
- Pogo-pin dock charging
- Fully local operation with no mandatory cloud service

## Building the remote

1. Order the Rev6 PCB using the supplied Gerber ZIP, BOM, and CPL.
2. Source the selected LCD and use its matching front cover plate.
3. Print the enclosure and buttons. For multicolour printing, use the supplied Bambu Lab 3MF project.
4. Fit a suitable protected 3.7 V LiPo battery with the correct JST polarity.
5. Install the PCB and secure the assembly using five M3 × 8 mm screws.
6. Flash the latest [OpenRemote firmware](https://github.com/LORDSn1per/OpenRemote-Firmware).

Always verify component orientation, battery polarity, display selection, and the manufacturer preview before ordering assembled PCBs.

## Project status

The Rev6 remote PCB has been manufactured and assembled, and the first unit is running. The normal and pogo-pin rear cases and both display cover plates are complete and published.

The charging dock has a complete KiCad design with production files and printable enclosure parts. Its PCB has not yet been through a manufacturing run, and several BOM lines still need LCSC codes before an assembled order — treat the dock as pre-production.

## Credits

OpenRemote builds on the original open-source [OMOTE](https://github.com/OMOTE-Community) hardware project. Thank you to the OMOTE contributors and community for creating the foundation that made OpenRemote possible.
