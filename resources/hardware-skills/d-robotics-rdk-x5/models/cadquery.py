from __future__ import annotations

import cadquery as cq


LENGTH_X = 85.0
WIDTH_Y = 56.0
HEIGHT_Z = 20.0


def build_model():
    return cq.Workplane("XY").box(
        LENGTH_X,
        WIDTH_Y,
        HEIGHT_Z,
        centered=(True, True, False),
    )


if __name__ == "__main__" and "show_object" in globals():
    show_object(build_model(), name="rdk_x5_reference_envelope")
