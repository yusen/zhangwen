from __future__ import annotations

import cadquery as cq


LENGTH_X = 51.8
WIDTH_Y = 47.39
HEIGHT_Z = 7.65


def build_model():
    return cq.Workplane("XY").box(
        LENGTH_X,
        WIDTH_Y,
        HEIGHT_Z,
        centered=(True, True, True),
    )


if __name__ == "__main__" and "show_object" in globals():
    show_object(build_model(), name="mpython_esp32s3_v3_envelope")
