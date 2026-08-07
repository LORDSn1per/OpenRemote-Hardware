"""Regenerate the inverted MIC LED label and OpenRemote GitHub QR artwork.

The graphics are stored as filled silkscreen runs.  Unpainted cells expose the
green solder mask, producing dark lettering and QR modules on solid white
silkscreen backgrounds without relying on unsupported polygon holes.
"""

from pathlib import Path
import importlib.util
import re
import uuid


PROJECT_DIR = Path(__file__).resolve().parents[1]
BOARD = PROJECT_DIR / "OpenRemote.kicad_pcb"
QR_LIBRARY = Path(
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/"
    "scripting/plugins/kicad_qrcode.py"
)

GITHUB_URL = "https://github.com/LORDSn1per/OpenRemote-Hardware"
GITHUB_CAPTION = "OpenRemote on GitHub"

MIC_FOOTPRINT_UUID = "a3b158e0-4c63-43c7-8897-028dc62c61e6"
QR_FOOTPRINT_UUID = "47604e1c-fc39-43d0-850e-2e83814bf005"


FONT = {
    " ": ("00000",) * 7,
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "p": ("00000", "11110", "10001", "11110", "10000", "10000", "10000"),
    "e": ("00000", "01110", "10001", "11111", "10000", "10001", "01110"),
    "n": ("00000", "11110", "10001", "10001", "10001", "10001", "10001"),
    "m": ("00000", "11010", "10101", "10101", "10101", "10101", "10101"),
    "o": ("00000", "01110", "10001", "10001", "10001", "10001", "01110"),
    "t": ("00100", "11111", "00100", "00100", "00100", "00100", "00110"),
    "i": ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    "u": ("00000", "10001", "10001", "10001", "10001", "10011", "01101"),
    "b": ("10000", "10000", "10110", "11001", "10001", "10001", "11110"),
}


def load_qr_library():
    if not QR_LIBRARY.exists():
        raise FileNotFoundError(f"KiCad QR library not found: {QR_LIBRARY}")
    spec = importlib.util.spec_from_file_location("kicad_qrcode", QR_LIBRARY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def text_bitmap(text):
    rows = [""] * 7
    for index, character in enumerate(text):
        glyph = FONT[character]
        for row in range(7):
            if index:
                rows[row] += "0"
            rows[row] += glyph[row]
    return rows


def carve_text(grid, text, start_row, start_col):
    bitmap = text_bitmap(text)
    for row, bits in enumerate(bitmap):
        for column, bit in enumerate(bits):
            if bit == "1":
                grid[start_row + row][start_col + column] = False


def deterministic_uuid(namespace, index):
    return str(uuid.uuid5(uuid.UUID(namespace), str(index)))


def filled_runs(grid, width, height, layer, namespace):
    """Convert a white-cell grid into merged filled fp_poly rectangles."""
    row_count = len(grid)
    column_count = len(grid[0])
    cell_width = width / column_count
    cell_height = height / row_count
    output = []
    shape_index = 0

    for row, cells in enumerate(grid):
        column = 0
        while column < column_count:
            if not cells[column]:
                column += 1
                continue
            start = column
            while column < column_count and cells[column]:
                column += 1

            x1 = -width / 2 + start * cell_width
            x2 = -width / 2 + column * cell_width
            y1 = -height / 2 + row * cell_height
            y2 = y1 + cell_height
            shape_uuid = deterministic_uuid(namespace, shape_index)
            shape_index += 1
            output.append(
                f'''\t\t(fp_poly
\t\t\t(pts
\t\t\t\t(xy {x1:.6f} {y1:.6f}) (xy {x2:.6f} {y1:.6f})
\t\t\t\t(xy {x2:.6f} {y2:.6f}) (xy {x1:.6f} {y2:.6f})
\t\t\t)
\t\t\t(stroke (width 0) (type solid))
\t\t\t(fill yes)
\t\t\t(layer "{layer}")
\t\t\t(uuid "{shape_uuid}")
\t\t)'''
            )
    return "\n".join(output)


def offset_artwork_y(artwork, offset):
    """Translate every polygon Y coordinate in generated artwork."""
    return re.sub(
        r"\(xy (-?\d+\.\d+) (-?\d+\.\d+)\)",
        lambda match: (
            f"(xy {match.group(1)} {float(match.group(2)) + offset:.6f})"
        ),
        artwork,
    )


def mic_label_block():
    width = 8.926248
    height = 2.049516
    columns = 53
    rows = 12
    grid = [[True] * columns for _ in range(rows)]

    # Approximate the original rounded KiBuzzard plaque corners.
    for row, inset in ((0, 2), (1, 1), (rows - 2, 1), (rows - 1, 2)):
        for column in range(inset):
            grid[row][column] = False
            grid[row][columns - 1 - column] = False

    bitmap_width = len(text_bitmap("MIC LED")[0])
    carve_text(grid, "MIC LED", 2, (columns - bitmap_width) // 2)
    artwork = filled_runs(grid, width, height, "F.SilkS", MIC_FOOTPRINT_UUID)

    return f'''\t(footprint "OpenRemote:MIC_LED_LABEL"
\t\t(layer "F.Cu")
\t\t(uuid "{MIC_FOOTPRINT_UUID}")
\t\t(at 81.95 89.55 90)
\t\t(descr "Inverted MIC LED silkscreen label")
\t\t(tags "OpenRemote MIC LED inverted silkscreen")
\t\t(property "Reference" "MIC_LED_LABEL"
\t\t\t(at 0 -4.072758 90)
\t\t\t(layer "F.SilkS")
\t\t\t(hide yes)
\t\t\t(effects (font (size 0.0254 0.0254) (thickness 0.15)))
\t\t)
\t\t(property "Value" "MIC LED"
\t\t\t(at 0 4.072758 90)
\t\t\t(layer "F.Fab")
\t\t\t(hide yes)
\t\t\t(effects (font (size 0.0254 0.0254) (thickness 0.15)))
\t\t)
\t\t(attr board_only exclude_from_pos_files exclude_from_bom)
\t\t(duplicate_pad_numbers_are_jumpers no)
{artwork}
\t\t(embedded_fonts no)
\t)'''


def qr_label_block():
    qr_module = load_qr_library()
    qr = qr_module.QRCode.getMinimumQRCode(
        GITHUB_URL, qr_module.ErrorCorrectLevel.M
    )
    if qr.getModuleCount() != 33:
        raise RuntimeError(
            f"Expected a version-4/33-module QR code; got {qr.getModuleCount()} modules"
        )

    width = 19.926
    height = 23.34
    qr_border = 4
    qr_size = qr.getModuleCount() + 2 * qr_border
    caption_rows = 19
    caption_columns = 137

    qr_grid = [[True] * qr_size for _ in range(qr_size)]
    for row in range(qr.getModuleCount()):
        for column in range(qr.getModuleCount()):
            qr_grid[row + qr_border][column + qr_border] = not qr.isDark(row, column)

    # Rounded top corners, entirely within the four-module quiet zone.
    for row, inset in ((0, 2), (1, 1)):
        for column in range(inset):
            qr_grid[row][column] = False
            qr_grid[row][qr_size - 1 - column] = False

    caption_grid = [[True] * caption_columns for _ in range(caption_rows)]
    caption_bitmap_width = len(text_bitmap(GITHUB_CAPTION)[0])
    carve_text(
        caption_grid,
        GITHUB_CAPTION,
        5,
        (caption_columns - caption_bitmap_width) // 2,
    )

    # Rounded bottom corners.
    for row, inset in ((caption_rows - 3, 1), (caption_rows - 2, 3), (caption_rows - 1, 6)):
        for column in range(inset):
            caption_grid[row][column] = False
            caption_grid[row][caption_columns - 1 - column] = False

    qr_height = width
    caption_height = height - qr_height
    qr_offset = -height / 2 + qr_height / 2
    qr_art = offset_artwork_y(
        filled_runs(qr_grid, width, qr_height, "B.SilkS", QR_FOOTPRINT_UUID),
        qr_offset,
    )

    # filled_runs centres each grid at zero; translate caption rectangles by
    # rewriting their local Y values into the lower caption band.
    caption_namespace = str(uuid.uuid5(uuid.UUID(QR_FOOTPRINT_UUID), "caption"))
    caption_art = filled_runs(
        caption_grid, width, caption_height, "B.SilkS", caption_namespace
    )
    caption_offset = -height / 2 + qr_height + caption_height / 2
    caption_art = offset_artwork_y(
        caption_art,
        caption_offset,
    )
    artwork = qr_art + "\n" + caption_art

    return f'''\t(footprint "OpenRemote:OPENREMOTE_GITHUB_QR"
\t\t(layer "B.Cu")
\t\t(uuid "{QR_FOOTPRINT_UUID}")
\t\t(at 94.675 115.075 -90)
\t\t(descr "Inverted OpenRemote GitHub QR code and caption")
\t\t(tags "QR {GITHUB_URL} {GITHUB_CAPTION}")
\t\t(property "Reference" "OPENREMOTE_QR"
\t\t\t(at 16.047038 1.676571 90)
\t\t\t(layer "B.SilkS")
\t\t\t(hide yes)
\t\t\t(effects (font (size 1.5 1.5) (thickness 0.3)) (justify mirror))
\t\t)
\t\t(property "Value" "{GITHUB_URL}"
\t\t\t(at 0.75 0 90)
\t\t\t(layer "B.Fab")
\t\t\t(hide yes)
\t\t\t(effects (font (size 1 1) (thickness 0.15)) (justify mirror))
\t\t)
\t\t(property "Caption" "{GITHUB_CAPTION}"
\t\t\t(at 0 0 90)
\t\t\t(layer "B.Fab")
\t\t\t(hide yes)
\t\t\t(effects (font (size 1 1) (thickness 0.15)) (justify mirror))
\t\t)
\t\t(attr board_only exclude_from_pos_files exclude_from_bom)
\t\t(duplicate_pad_numbers_are_jumpers no)
{artwork}
\t\t(embedded_fonts no)
\t)'''


def footprint_span(board_text, footprint_uuid):
    uuid_position = board_text.index(f'\t\t(uuid "{footprint_uuid}")')
    start = board_text.rfind("\n\t(footprint ", 0, uuid_position) + 1
    depth = 0
    in_string = False
    escaped = False
    for position in range(start, len(board_text)):
        character = board_text[position]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        else:
            if character == '"':
                in_string = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    return start, position + 1
    raise ValueError(f"Unterminated footprint {footprint_uuid}")


def main():
    board_text = BOARD.read_text()
    replacements = [
        (MIC_FOOTPRINT_UUID, mic_label_block()),
        (QR_FOOTPRINT_UUID, qr_label_block()),
    ]
    spans = []
    for footprint_uuid, replacement in replacements:
        start, end = footprint_span(board_text, footprint_uuid)
        spans.append((start, end, replacement))
    for start, end, replacement in sorted(spans, reverse=True):
        board_text = board_text[:start] + replacement + board_text[end:]
    BOARD.write_text(board_text)
    print(f"Updated {BOARD}")
    print(f"QR content: {GITHUB_URL}")
    print(f"Caption: {GITHUB_CAPTION}")


if __name__ == "__main__":
    main()
