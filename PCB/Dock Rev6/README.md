# OpenRemote Dock Rev6 KiCad Project

This is a self-contained KiCad 10 project starter for the OpenRemote Rev6 charging dock.

## Included footprints and 3D models

| Library footprint | Intended hardware | Interface / package |
|---|---|---|
| `ESP32-C3_SuperMini_Header_2x08_P2.54mm` | ESP32-C3 Super Mini shown by the owner | Two 1x8 headers, 2.54 mm pitch; owner-supplied STEP model |
| `CC1101_433MHz_Coil_Module_2x04_P2.54mm` | 28x15 mm CC1101 433 MHz module, spring antenna version | 2x4 header, 2.54 mm pitch |
| `LED_5mm_Side_Mount_C405273` | Meihua MHL512IR059CRT IR LED, LCSC C405273 | THT, 5 mm, horizontal/side mounting |
| `FS8205A_SOT-23-6` | FUXINSEMI FS8205A, LCSC C908265 | SOT-23-6 |
| `HX-XH2.54-2PZZ_C42391660` | hanxia HX-XH2.54-2PZZ, LCSC C42391660 | Vertical shrouded 1x2 male header; vendor land pattern is 2.50 mm pitch |
| `SW_6x6x5H_THT` | 6x6 mm tactile switch, 5 mm body height | Four-pin THT |
| `LED_5mm_Green_THT` | Standard green 5 mm LED | THT, 2.54 mm pitch |

The ESP32 model is the owner's supplied `esp32 c3 supermini.step`, copied into the project as `ESP32-C3_SuperMini.step`. The project also includes `ESP32-C3_SuperMini_2x08_Header.step`: two 2.24 mm-high black 1x8 header blocks with 16 gold pins. All STEP files are project-local, so no Downloads or global KiCad 3D-model path is required.

## Important sourcing notes

- The ESP module follows the owner's supplied **16-pin ESP32-C3 Super Mini** image: 18x22.52 mm with two 1x8, 2.54 mm header rows. It does not use the different 18-pin Waveshare C3-Zero footprint from the earlier retail link.
- J1 is the exact hanxia HX-XH2.54-2PZZ sold as LCSC C42391660. LCSC describes it as 2.54 mm, but its manufacturer-linked EasyEDA land pattern uses 2.50 mm pad pitch, 1.0 mm drills, and a 7.5 x 5.9 mm shrouded body; the project follows that land pattern.
- CC1101 clone modules vary. This footprint follows the common 28x15 mm, 2x4 2.54 mm module and the pin order shown in the provided image. Check the delivered module before ordering the PCB.
- `Dock Rev6.kicad_pcb` uses a 45x60 mm main body with narrow front and rear tongues. The confirmed physical rear tongue ends at dock Z=`-68.0 mm`; it is straight between the two rear receivers and has no obsolete scallops.
- The owner confirmed that the provisional handoff reversed the physical faces. The installed-board mapping is now **physical dock Z = KiCad Y - 140 mm**: Fusion Z=`-70` is the rear and Z=`+30` is the front.
- U1 is centred at KiCad `(100.00, 82.39)` with USB-C facing the physical rear and is placed on `B.Cu`. The ESP32 module hangs below the host PCB; the black header plastic lies between the ESP32 board and the host PCB, as it will when assembled with female header sockets. It was moved 1.5 mm into the cavity so the module PCB clears the rear wall. Its exact 18 mm body has approximately 0.50 mm lateral clearance to each physical rear lid receiver.
- The four large `User.Drawings` circles are the exact **15 mm OD physical receiver outlines**, mirrored into the confirmed board coordinates. Rear centres are KiCad `(82.998, 80.858)` and `(117.002, 80.858)`; front centres are `(83.643, 161.292)` and `(116.357, 161.292)`.
- In Fusion, `Dock + Correct Rear USB-C Opening Base Feature` was removed and the retained master body was restored as the visible solid `Dock - User Editable Shell (No Cutouts)`. This leaves the enclosure apertures for the owner to sketch and cut directly without deleting the dock shell.
- The final exact-solid Fusion audit reports **no collision between the underside ESP32/header assembly and the base lid or its bosses**. The lowest point of the ESP32 model is 0.294 mm above the flat lid surface. The USB, button, and LED apertures are intentionally left for the owner to create before enclosure release.
- Four 3.3 mm NPTH M3 mounting holes are on an exact 37x52 mm pattern at dock X/Z `(+/-18.5, +6)` and `(+/-18.5, -46)`. Each hole has an R4 mm all-copper keepout. H1-H4 are locked `board_only` footprints, excluded from BOM and position files, so **Update PCB from Schematic will not delete them again**.
- The matching Fusion base lid has four 7.5 mm OD bosses at those same centres. Each boss has a 2.55 mm blind pilot, an 8.0 mm PCB seating plane, and 3.4 mm thread engagement for an M3x5 screw through this 1.6 mm board. The original pre-boss lid body is retained hidden for rollback.

## Pin order

CC1101 pads are numbered by rows as shown in the supplied diagram: `1 GND`, `2 VCC`, `3 GDO0`, `4 CSN`, `5 SCK`, `6 MOSI`, `7 MISO/GDO1`, `8 GDO2`.

ESP32-C3 Super Mini pad numbers use the printed signal names directly. USB-C is at the top: left row `5V`, `GND`, `3V3`, `GPIO4/SCK/A4`, `GPIO3/A3`, `GPIO2/A2`, `GPIO1/A1`, `GPIO0/A0`; right row `GPIO5/MISO/A5`, `GPIO6/MOSI`, `GPIO7/SS`, `GPIO8/SDA`, `GPIO9/SCL`, `GPIO10`, `GPIO20/RX`, `GPIO21/TX`.

## Electrical design

- CC1101 SPI: `GPIO4 SCK`, `GPIO5 MISO`, `GPIO6 MOSI`, `GPIO7 CSN`; interrupts are `GPIO10 GDO0` and `GPIO20 GDO2`.
- Four MHL512IR059CRT emitters are connected in parallel through individual `39R 0.5W` resistors. GPIO0 drives both paralleled halves of Q1 through `100R`, with a `100k` gate pulldown.
- The 39R IR branches are designed for pulsed remote-control service at approximately 95mA per LED from 5V. Firmware must not hold `IR_PWM` high continuously.
- The green status LED uses GPIO1 and `1k`. The tactile button uses GPIO3 with a `10k` pull-up and `100nF` hardware debounce.
- ESP32-C3 strap pins GPIO2, GPIO8, and GPIO9 are deliberately left unconnected; GPIO21 is also reserved.
- Added decoupling: `100nF + 10uF` at the ESP 5V input, `100nF + 10uF` at the CC1101 3.3V rail, and `100uF + 100nF` at the pulsed IR bank.

### Capacitor placement

- `C1 100nF`: immediately beside U1's 5V/GND header pins; shortest possible loop.
- `C2 10uF`: beside U1 and C1 on the 5V rail; C1 should be closer than C2.
- `C3 100nF`: immediately beside U2 pins 2 VCC and 1 GND; this is the most placement-sensitive radio capacitor.
- `C4 10uF`: beside U2 and C3; C3 should be closer than C4.
- `C5 100nF`: beside U1 GPIO3 and pull-up R1, at the controller end of the BUTTON trace.
- `C6 100uF`: beside Q1/J1 at the high-current IR power entry/current loop.
- `C7 100nF`: beside Q1/J1 and C6, with the shortest 5V-to-GND loop; C7 should be closer to the switching loop than C6.

`Dock Rev6.kicad_pcb` is populated but not routed. The remaining SMD parts are staged by circuit: C1/C2 beside the header-mounted ESP32, C5/R1 immediately left of it, C3/C4 beside the CC1101 power pins, R3/R4/Q1 to the left of the CC1101 coil envelope, C7 beside J1, and R2 beside D5. The current DRC reports silkscreen cleanup warnings plus the expected unrouted nets; it does not report a copper short, hole, or board-edge clearance failure.

The board immediately before the front/back and mounting-hole correction is retained as `Dock Rev6.before-mechanical-correction-v2.kicad_pcb`; the board immediately before the final rear-wall fit is retained as `Dock Rev6.before-mechanical-fit-v3.kicad_pcb`. `apply_mechanical_fit_v3.py` reapplies the final U1 position and rear-tongue geometry without altering nets or component identities. Use KiCad's native refill after running it. Do not run `generate_dock_rev6_mechanical_board.py` on the populated board; that generator creates a blank mechanical PCB and would replace component placement.

## Fusion 3D handoff

`Dock Rev6 PCB Assembly.step` is the current board-plus-components model handed to
Fusion. Regenerate it with `export_dock_rev6_step.py`, which runs:

```
kicad-cli pcb export step --subst-models --no-dnp --force
```

No origin flag is passed, so the STEP keeps KiCad's absolute board coordinates
(substrate spans X `77.5`-`122.5`, Y `-166.0`-`-72.0`, Z `0`-`1.6`). The Fusion
placement transform depends on that:

```
dock X =  step X - 100 mm
dock Y =  step Z + 8 mm      (PCB seating plane on the base-lid bosses)
dock Z = -step Y - 140 mm    (owner-confirmed mirrored physical face)
```

`CAD/FusionScripts/DockRev6PCBReplace` deletes any existing `Dock Rev6 PCB*`
occurrence, re-imports this STEP at that transform as the component
`Dock Rev6 PCB`, then re-runs the solid interference check against `Dock:1` and
`Dock Base Lid:1` and writes `CAD/Dock Rev6/Charging Dock Rev6 PCB Replace Report.json`.
Base-lid interference is a failure; dock-shell interference at SW1, J1, D1-D5 is
expected until the owner cuts the USB, button, and LED apertures.

`Dock Rev6 Component Staging.step` is the superseded 26 Aug 16:52 export, taken
before power/ground routing was finalised and before SW1 moved to the
`SW-TH_KH-6X6X5H-ZJ` (C2837541) model and J1 to `HX-XH2.54-2PZZ` (C42391660). It
is kept only for rollback; Fusion should no longer import it.

`Dock Rev6 PCB Assembly Preview.png` and `Dock Rev6 PCB Assembly Preview Bottom.png`
are `kicad-cli pcb render` views of the same board state.
