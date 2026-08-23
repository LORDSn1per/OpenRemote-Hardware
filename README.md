# OpenRemote Rev6 Hardware

<p align="center">
  <img src="images/OpenRemote%20Rev6.jpeg" alt="OpenRemote Rev6 universal remote" width="100%">
</p>

OpenRemote Rev6 is an open-source, offline smart remote based on the excellent [OMOTE hardware](https://github.com/OMOTE-Community/OMOTE-Hardware). It combines a 2.8-inch capacitive touchscreen with physical buttons, infrared, Wi-Fi, Bluetooth, an ESP32-S3, expandable storage, and a fully 3D-printable enclosure.

Rev6 focuses on making the remote easier to source, nicer to print, more serviceable, and ready for future dock charging—while retaining support for the original Adafruit display.

> **Firmware:** [OpenRemote Firmware](https://github.com/LORDSn1per/OpenRemote-Firmware)

## What is new in Revision 6?

- **New IPS display support.** Rev6 supports the EastRising/BuyDisplay ER-TFT028A2-4 capacitive display with a separate six-pin touch FPC. It is brighter, sharper, has much better viewing angles, and is easier to source than the original display.
- **Original display compatibility.** The original Adafruit Product 2770/CH280QV10-CT display remains supported through the alternate display configuration and matching front cover.
- **Built-in microphone.** A rear-mounted digital I2S microphone provides hardware support for voice control, voice search, and future assistant features.
- **Faster charging.** The TP4056 charging circuit is configured for up to approximately 1 A, subject to the battery, power source, and thermal conditions.
- **Future charging input.** Rev6 includes a dedicated 5 V input before the fuse, ready for the planned pogo-pin charging dock or other future charging options.
- **Improved serviceability.** Five rear-installed M3 × 8 mm screws secure the PCB and enclosure, making the remote easier to assemble and reopen.
- **Updated PCB branding.** The board is now branded OpenRemote and includes a QR code linking directly to the firmware repository.

<p align="center">
  <img src="images/OpenRemote%20Rev6%20Brochure.jpeg" alt="OpenRemote Rev6 feature overview" width="100%">
</p>

## New BuyDisplay LCD

The recommended Rev6 screen is the 2.8-inch 240×320 EastRising/BuyDisplay IPS TFT with capacitive touch. Its separate six-pin touch cable connects to the new J6 connector on the Rev6 PCB.

The BuyDisplay assembly is approximately **0.8 mm thicker** than the original Adafruit screen. It therefore requires the newly updated BuyDisplay front cover plate. Do not try to force the thicker display into the original Adafruit cover.

- Use **`Cover Plate v19 - BuyDisplay LCD.stl`** with the new BuyDisplay screen.
- Use **`Cover Plate v12 - Adafruit LCD.stl`** with the original Adafruit screen.

The enclosure release also includes a **Bambu Lab 3MF project** prepared for multicolour printing.

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

The Rev6 enclosure will be available with two rear-shell choices:

1. **Normal rear case** — the standard shell for USB-C charging.
2. **Pogo-pin rear case — coming soon** — includes two charging contacts for use with the new self-aligning charging dock.

The planned dock will place the spring-loaded pogo pins in the dock and use neat, fixed gold-plated contacts in the remote. The dock and pogo-contact case are still under development; final CAD will be released after the physical contacts and pins have been measured and tested.

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
- Future pogo-pin dock charging support
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

The Rev6 PCB has been completed and submitted for manufacture. The normal rear enclosure and updated display covers are complete. The pogo-pin rear case and new charging dock are the next major hardware additions and will be published after physical prototyping.

## Credits

OpenRemote builds on the original open-source [OMOTE](https://github.com/OMOTE-Community) hardware project. Thank you to the OMOTE contributors and community for creating the foundation that made OpenRemote possible.
