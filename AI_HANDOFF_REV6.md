# OpenRemote Rev 6 — AI Handoff

Updated: 2026-08-07 (Australia/Sydney)

## Read this first

- The active design repository is `/Volumes/home/Documents/Arduino/OpenRemote/HARDWARE/OpenRemote-Hardware`.
- Do **not** use the older sibling `OMOTE-Hardware` repository as the Rev 6 working copy.
- The user is learning Git and KiCad. Explain actions in plain English and create a Git save point when asked.
- Never discard, reset, overwrite, or mechanically “clean up” existing changes. Ask before making a major design decision.
- KiCad should be closed before editing its project files externally.
- The next immediate hardware decision is intentionally paused: do not change J6 until the physical EastRising LCD arrives and the touch-tail contact orientation is checked.

## Current Git state

- Branch: `main`
- HEAD when this handoff was written: `cb0b448` — `Update Rev 6 project metadata`
- Local branch is seven commits ahead of `origin/main`.
- The working tree contains extensive **uncommitted** Rev 6 schematic, PCB, footprint, library, and 3D-model work. Treat all of it as valuable user work.
- There are also KiCad history folders and macOS `.DS_Store` files. Do not delete or commit them without asking.
- This handoff itself is uncommitted.

Recent save points:

1. `931e525` — Start Rev 6 Schematic
2. `02e6475` — Prepared to place mic on PCB
3. `3b63bd5` — Placed microphone on rear of PCB
4. `9a52588` — Routed microphone traces
5. `8919bfe` — Organize PCB revision archives
6. `7b1a904` — Add headerless microphone 3D model
7. `cb0b448` — Update Rev 6 project metadata

## Principal Rev 6 files

- `PCB/Revision 6/OpenRemote.kicad_sch`
- `PCB/Revision 6/OpenRemote.kicad_pcb`
- `PCB/Revision 6/OpenRemote.kicad_pro`
- `PCB/Revision 6/project_libraries/symbols/OpenRemoteDisplay.kicad_sym`
- `PCB/Revision 6/project_libraries/symbols/OpenRemoteLib.kicad_sym`
- `PCB/Revision 6/project_libraries/footprints/OpenRemoteLib.pretty/`
- `PCB/Revision 6/project_libraries/3D-models/`

Revision 3, 4, and 5 folders are retained as deprecated reference designs. Rev 5 is useful when checking original geometry, but do not edit deprecated revisions.

## Confirmed microphone design

The user has already built and tested the microphone on physical hardware with their own firmware. The intent is to preserve that known-working wiring rather than redesign it.

- Module: circular MS3625 I2S microphone breakout, mechanically and electrically compatible with the familiar INMP441 module.
- KiCad reference: `MIC1`.
- Module diameter used by the custom footprint: approximately 14.4 mm.
- Mounting: module is soldered flat to the rear/non-button side of the main PCB, with the module’s logo/pad face touching the main PCB.
- The footprint uses six SMD landing pads beneath the module, not plated through-holes.
- The custom footprint includes solder-paste apertures on the microphone pads.
- A 2.0 mm non-plated acoustic opening passes through the main PCB so the microphone can listen through it.
- L/R and microphone GND are tied to GND, selecting the corresponding I2S channel.
- Microphone VDD follows the user’s tested arrangement: it is powered directly from ESP32-S3 GPIO45 at the node before the indicator LED. The LED indicates microphone power and the board label is now `MIC LED` with an inverted/white-background style.
- I2S SCK/BCLK, WS/LRCLK, and SD/DATA each pass through a 4.7 kΩ series resistor (`R45`, `R46`, and `R47`) to match the tested wiring.
- The exact existing GPIO allocation and routing are already represented in the current schematic/PCB. Do not “improve” or reassign them unless the user explicitly requests it.
- Custom footprint: `MS3625_Module_Back_Mount_SMD.kicad_mod`.
- Custom 3D model: `MS3625_Circular_Microphone_Module_No_Headers.step`; header pins were intentionally removed.

Before fabrication, verify the GPIO45 power arrangement electrically against ESP32-S3 limits and the physical prototype. It is a deliberate user requirement, but it is unusual enough to deserve an explicit design-rule review rather than a silent assumption.

## Display strategy

The original Adafruit display remains supported. Rev 6 is intended to support either the original display or a new EastRising capacitive-touch display, selected in firmware.

New display:

- EastRising/BuyDisplay `ER-TFT028-4.2` family, 2.8-inch 240×320 IPS TFT with capacitive touch option.
- Product page: <https://www.buydisplay.com/2-8-inch-240x320-ips-tft-lcd-display-panel-optional-touch-panel-wide-view>
- Touch panel: `ER-TPC028-4.1`, FT6206 controller.
- Touch drawing: <https://www.buydisplay.com/download/manual/ER-TPC028-4.1_Drawing.pdf>
- The user physically confirmed that positions 44–47 on the 50-pin tail are unpopulated on both the bare LCD and capacitive version.
- The existing 50-pin PCB connector `J2` is retained. The existing installed connector is JUSHUO `AFC07-S50ECC-00` / LCSC `C11098`, a 50-pin 0.5 mm **top-contact** connector.
- The EastRising LCD’s 50-pin tail is also intended for a top-contact connector. “Top contact” means the exposed tail contacts face up/away from the PCB when inserted into a connector mounted on the top side.
- Electrical pinout compatibility must still be checked separately; matching pitch and contact orientation alone do not prove a safe drop-in replacement.

Display mechanical assets currently in the project:

- Original display footprint/model: `Adafruit_280QV10_MECHANICAL.kicad_mod`, reference `LCD1`.
- EastRising footprint/model: `ER-TFT028-4.2_MECHANICAL.kicad_mod`, reference `LCD2`.
- EastRising source model: `ER-TFT028-4.2.step`.
- Custom folded model: `ER-TFT028-4.2_Folded.step`.
- Touch-flex model: `ER-TFT028-4.2_TouchFPC.wrl`.
- Generator: `project_libraries/3D-models/generate_folded_lcd.py`.
- The intended visible screen has a black border, dark-grey display area, and identifying `SCREEN` text so its glass/front side is obvious.

The folded LCD/touch flex geometry is a visualization aid, not a manufacturing-authoritative flex model. The user has repeatedly identified geometry/orientation problems in earlier iterations. Recheck it against the official drawings and the physical part before relying on where either tail lands.

Both LCD mechanical footprints/models currently exist in the PCB and may both appear in KiCad’s 3D Viewer. PCB-editor appearance presets do not automatically suppress separate 3D models in the 3D Viewer. Do not claim that the model-switching workflow is complete until it is tested in the installed KiCad version.

## Six-pin capacitive-touch connector J6 — unresolved

Current design state:

- `J6` is placed and routed on the front copper side at approximately `(148.05, 85.0)`, rotated −90°.
- Current symbol value: `ER-CON06HB-1_TOUCH`.
- Current footprint: `ER-CON06HB-1_Compatible_1x06_P0.50mm_BottomContact`.
- It is currently modelled after Hirose `FH12-6S-0.5SH`, with `Hirose_FH12-6S-0.5SH_1x06_P0.50mm.step`.
- Current schematic mapping:
  - Pin 1: GND
  - Pin 2: SDA
  - Pin 3: SCL
  - Pin 4: TP_NRST
  - Pin 5: nINT, intentionally not connected at present
  - Pin 6: +VSW
- `TP_NRST` should remain connected to the same touch reset net used at the 50-pin display interface.
- `+VSW` powers the touch connector and is the switched display supply; do not relabel it as IOVCC merely because it connects to the display power domain.

Contact-orientation decision:

- EastRising recommends `ER-CON06HB-1`, whose dedicated product page describes it as a six-pin, 0.5 mm bottom-contact connector: <https://www.buydisplay.com/6-pin-0-5mm-pitch-bottom-contact-zif-connector-fpc-connector>
- EastRising also offers `ER-CON06HT-1` as the top-contact version.
- However, the correct choice for this PCB depends on which way the **exposed gold pads face after the real touch tail is folded through the PCB opening and reaches the present J6 location**.
- If the exposed pads face down toward the PCB, retain a bottom-contact connector.
- If the exposed pads face up away from the PCB, use a top-contact connector.
- The user decided to wait for the actual LCD and physically check where the tail lands. Respect that decision: do not change J6 now.
- When changing contact type later, do not merely rename the part. Verify the exact manufacturer footprint, actuator/entry direction, tail thickness, pin-1 orientation, and whether pin numbering becomes mirrored relative to the already-routed traces.

## Other completed Rev 6 presentation changes

- Branding is OpenRemote rather than OMOTE.
- The PCB QR code points to <https://github.com/LORDSn1per/OpenRemote-Hardware>.
- QR caption: `OpenRemote on GitHub`.
- The old `USER LED` board marking was changed to an inverted `MIC LED` marking.
- A stray display/PCB-outline line on front silkscreen was previously targeted for removal; visually recheck both PCB sides rather than assuming every outline artifact is gone.

## Required checks before fabrication

1. Receive the physical EastRising display and establish the installed orientation of both tails.
2. Determine whether J6 must be bottom-contact or top-contact at its current PCB location.
3. Verify J6 pin 1 and all six routed signals against the physical tail and exact connector datasheet.
4. Confirm the EastRising 50-pin electrical pinout against the existing J2 schematic, not just its mechanical compatibility.
5. Inspect the EastRising flex bend path and connector landing positions using physical measurements.
6. Run KiCad ERC and PCB DRC and review every new violation manually.
7. Confirm microphone acoustic-hole size/location, rear mounting, solder-mask and paste apertures, courtyard clearance, and module orientation.
8. Confirm GPIO45 microphone power and indicator LED current against the tested prototype and ESP32-S3 electrical limits.
9. Check that copper, planes, traces, and components do not obstruct the acoustic opening or interfere mechanically with either display/flex.
10. Open the 3D Viewer and verify component side, Z offsets, flex direction, screen side, and that the chosen display model alone is visible.
11. Create a named Git save point before any connector-orientation or pin-mapping change.

## Source material supplied by the user

- Microphone product was identified as the circular MS3625 clone of an INMP441 module.
- Microphone STEP originally supplied as `/Users/phillipcarlson/Downloads/INMP441 I2S Microphone Module v15.step`.
- EastRising display STEP originally supplied as `/Users/phillipcarlson/Downloads/ER-TFT028-4.2.stp`.
- Physical display/connector photographs were supplied in the conversation, including `IMG_2020.HEIC` and `IMG_2021.JPG`.
- Treat the user’s physical photographs and measurements as stronger evidence of assembly orientation than generic third-party 3D models.

## Recommended first response by the next AI

Confirm that the active work is in `OpenRemote-Hardware/PCB/Revision 6`, state that J6 will remain unchanged until the LCD arrives, then inspect `git status` before doing anything. Do not make a speculative connector change or commit the current dirty working tree without the user’s explicit request.
