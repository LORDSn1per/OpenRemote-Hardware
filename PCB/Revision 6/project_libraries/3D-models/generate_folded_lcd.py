"""Generate the through-board-flex EastRising ER-TFT028-4.2 STEP model.

Requires CadQuery 2.5.  The manufacturer drawing defines the assembled
50-pin LCD flex length as 26.70 mm.  The supplied manufacturer STEP shows
that flex flat, so this script trims the flat tail from the display backing
and recreates it with two 90-degree bends: down through the PCB opening, then
flat along the opposite side of the PCB.  This matches the installation path
used by the original OpenRemote LCD and exposes the connector landing point.
"""

from pathlib import Path
import math

import cadquery as cq


MODEL_DIR = Path(__file__).resolve().parent
SOURCE = MODEL_DIR / "ER-TFT028-4.2.step"
OUTPUT = MODEL_DIR / "ER-TFT028-4.2_Folded.step"

PANEL_BOTTOM_Y = -34.65
PANEL_TOP_Y = 35.30
PANEL_BACK_Z = 2.70
PCB_REAR_FLEX_Z = -2.90

LCD_FLEX_WIDTH = 25.50
LCD_FLEX_LENGTH = 26.70
LCD_FLEX_THICKNESS = 0.20
LCD_CONTACT_LENGTH = 3.50
LCD_CONTACT_WIDTH = 0.35
LCD_CONTACT_PITCH = 0.50
LCD_BEND_RADIUS = 1.00
# Centre of the existing wide rounded LCD-FPC cutout, in display-local Y.
# With the current placement this is the slot centred at global X ~= 72.1 mm.
PCB_CUTOUT_CENTRE_Y = -22.22

SCREEN_LABEL = {
    "S": ("01110", "10000", "10000", "01110", "00001", "00001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "N": ("10001", "11001", "11001", "10101", "10011", "10011", "10001"),
}


def box(x_size, y_size, z_size, x, y, z):
    return (
        cq.Workplane("XY")
        .box(x_size, y_size, z_size)
        .translate((x, y, z))
        .val()
    )


def quarter_bend(width, radius, thickness, centre_y, centre_z, start_degrees, end_degrees):
    """Create a constant-thickness quarter bend extruded across the flex width."""
    steps = 16
    outer_radius = radius + thickness / 2.0
    inner_radius = radius - thickness / 2.0
    outer_points = []
    inner_points = []

    for step in range(steps + 1):
        angle = math.radians(
            start_degrees + (end_degrees - start_degrees) * step / steps
        )
        outer_points.append(
            (
                centre_y + outer_radius * math.cos(angle),
                centre_z + outer_radius * math.sin(angle),
            )
        )

    for step in range(steps, -1, -1):
        angle = math.radians(
            start_degrees + (end_degrees - start_degrees) * step / steps
        )
        inner_points.append(
            (
                centre_y + inner_radius * math.cos(angle),
                centre_z + inner_radius * math.sin(angle),
            )
        )

    return (
        cq.Workplane("YZ")
        .polyline(outer_points + inner_points)
        .close()
        .extrude(width / 2.0, both=True)
        .val()
    )


def add_screen_label(assembly):
    """Add a font-independent SCREEN label to the glass-facing surface."""
    pixel = 0.65
    pitch = 0.78
    character_pitch = 4.45
    text = "SCREEN"
    total_width = (len(text) - 1) * character_pitch + 4 * pitch
    start_x = -total_width / 2.0

    for character_index, character in enumerate(text):
        pattern = SCREEN_LABEL[character]
        character_x = start_x + character_index * character_pitch
        for row, bits in enumerate(pattern):
            for column, bit in enumerate(bits):
                if bit == "1":
                    assembly.add(
                        box(
                            pixel,
                            pixel,
                            0.05,
                            character_x + column * pitch,
                            (3 - row) * pitch,
                            PANEL_BACK_Z + 0.18,
                        ),
                        name=f"screen_label_{character_index}_{row}_{column}",
                        color=cq.Color(0.62, 0.64, 0.66),
                    )


def main():
    imported = cq.importers.importStep(str(SOURCE)).val()
    solids = imported.Solids()

    if len(solids) != 40:
        raise RuntimeError(
            f"Expected 40 solids in {SOURCE.name}; found {len(solids)}. "
            "The source model may have changed."
        )

    assembly = cq.Assembly(name="ER-TFT028-4.2_Folded")

    # Preserve the detailed manufacturer solids.  A controlled black bezel
    # and dark-grey viewing area are added below so the visible LCD face does
    # not inherit the white rear-cover appearance from the supplied STEP.
    front_colours = {
        0: cq.Color(0.12, 0.12, 0.12),
        1: cq.Color(0.12, 0.12, 0.12),
        2: cq.Color(0.12, 0.12, 0.12),
        3: cq.Color(0.08, 0.08, 0.08),
        4: cq.Color(0.07, 0.075, 0.08),
        5: cq.Color(0.12, 0.12, 0.12),
        6: cq.Color(0.08, 0.08, 0.08),
        7: cq.Color(0.04, 0.04, 0.04),
    }

    for index in range(8):
        assembly.add(
            solids[index],
            name=f"display_front_{index:02d}",
            color=front_colours[index],
        )

    add_screen_label(assembly)

    # Solid 39 contains the rear display structure and the original flat LCD
    # tail.  Keep only the portion inside the 50.20 x 69.30 mm panel outline.
    panel_clip = box(
        60.0,
        PANEL_TOP_Y - PANEL_BOTTOM_Y,
        8.0,
        0.0,
        (PANEL_TOP_Y + PANEL_BOTTOM_Y) / 2.0,
        1.0,
    )
    rear_panel = solids[39].intersect(panel_clip)
    assembly.add(
        rear_panel,
        name="display_rear_without_flat_flex",
        color=cq.Color(0.04, 0.04, 0.04),
    )

    panel_centre_y = (PANEL_TOP_Y + PANEL_BOTTOM_Y) / 2.0
    assembly.add(
        box(50.20, 69.30, 0.08, 0.0, panel_centre_y, PANEL_BACK_Z + 0.04),
        name="black_lcd_bezel",
        color=cq.Color(0.015, 0.015, 0.015),
    )
    assembly.add(
        box(43.20, 57.60, 0.06, 0.0, 0.0, PANEL_BACK_Z + 0.11),
        name="dark_grey_lcd_viewing_area",
        color=cq.Color(0.07, 0.075, 0.08),
    )

    flex_colour = cq.Color(1.00, 0.48, 0.02)
    stiffener_colour = cq.Color(0.93, 0.72, 0.18)
    contact_colour = cq.Color(1.00, 0.82, 0.18)

    # Run from the display edge to the existing wide rounded PCB cutout.  The
    # first smooth 90-degree bend enters that cutout; the second smooth bend
    # turns onto the opposite side.  Straight and arc lengths are deducted
    # from the specified 26.70 mm cable length.
    upper_bend_centre_z = PANEL_BACK_Z - LCD_BEND_RADIUS
    lower_bend_centre_z = PCB_REAR_FLEX_Z + LCD_BEND_RADIUS
    upper_bend_centre_y = PCB_CUTOUT_CENTRE_Y - LCD_BEND_RADIUS
    lower_bend_centre_y = PCB_CUTOUT_CENTRE_Y + LCD_BEND_RADIUS
    upper_bend_start_y = upper_bend_centre_y
    rear_flat_start_y = lower_bend_centre_y
    panel_side_lead_length = upper_bend_start_y - PANEL_BOTTOM_Y
    vertical_length = upper_bend_centre_z - lower_bend_centre_z
    bend_arc_length = math.pi * LCD_BEND_RADIUS
    rear_flat_length = (
        LCD_FLEX_LENGTH
        - panel_side_lead_length
        - vertical_length
        - bend_arc_length
    )
    flex_end_y = rear_flat_start_y + rear_flat_length
    flex_centre_y = (rear_flat_start_y + flex_end_y) / 2.0
    flex_z = PCB_REAR_FLEX_Z

    assembly.add(
        box(
            LCD_FLEX_WIDTH,
            panel_side_lead_length,
            LCD_FLEX_THICKNESS,
            0.0,
            (PANEL_BOTTOM_Y + upper_bend_start_y) / 2.0,
            PANEL_BACK_Z,
        ),
        name="lcd_flex_panel_side_lead_to_cutout",
        color=flex_colour,
    )

    assembly.add(
        box(
            LCD_FLEX_WIDTH,
            rear_flat_length,
            LCD_FLEX_THICKNESS,
            0.0,
            flex_centre_y,
            flex_z,
        ),
        name="rear_side_lcd_flex",
        color=flex_colour,
    )

    assembly.add(
        box(
            LCD_FLEX_WIDTH,
            LCD_FLEX_THICKNESS,
            vertical_length,
            0.0,
            PCB_CUTOUT_CENTRE_Y,
            (upper_bend_centre_z + lower_bend_centre_z) / 2.0,
        ),
        name="lcd_flex_through_pcb_leg",
        color=flex_colour,
    )

    assembly.add(
        quarter_bend(
            LCD_FLEX_WIDTH,
            LCD_BEND_RADIUS,
            LCD_FLEX_THICKNESS,
            upper_bend_centre_y,
            upper_bend_centre_z,
            90.0,
            0.0,
        ),
        name="lcd_flex_upper_90_degree_bend",
        color=flex_colour,
    )
    assembly.add(
        quarter_bend(
            LCD_FLEX_WIDTH,
            LCD_BEND_RADIUS,
            LCD_FLEX_THICKNESS,
            lower_bend_centre_y,
            lower_bend_centre_z,
            180.0,
            270.0,
        ),
        name="lcd_flex_lower_90_degree_bend",
        color=flex_colour,
    )

    contact_centre_y = flex_end_y - LCD_CONTACT_LENGTH / 2.0
    assembly.add(
        box(
            LCD_FLEX_WIDTH,
            LCD_CONTACT_LENGTH,
            0.12,
            0.0,
            contact_centre_y,
            PCB_REAR_FLEX_Z - 0.08,
        ),
        name="lcd_flex_stiffener",
        color=stiffener_colour,
    )

    for pin in range(50):
        x = (pin - 24.5) * LCD_CONTACT_PITCH
        assembly.add(
            box(
                LCD_CONTACT_WIDTH,
                LCD_CONTACT_LENGTH,
                0.04,
                x,
                contact_centre_y,
                PCB_REAR_FLEX_Z - 0.17,
            ),
            name=f"lcd_contact_{pin + 1:02d}",
            color=contact_colour,
        )

    assembly.save(str(OUTPUT), exportType="STEP", mode="default")
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    main()
