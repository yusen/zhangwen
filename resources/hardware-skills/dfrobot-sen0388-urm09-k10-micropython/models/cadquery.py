from __future__ import annotations

import cadquery as cq


# Units: mm. PCB XY center is the origin. +Z points toward the transducers.
PCB_LENGTH_X = 22.0
PCB_WIDTH_Y = 47.0
PCB_THICKNESS_Z = 1.6
PCB_CORNER_RADIUS = 2.0

CONNECTOR_LENGTH_X = 5.5
CONNECTOR_WIDTH_Y = 10.0
CONNECTOR_HEIGHT_Z = 6.3

TRANSDUCER_DIAMETER = 16.4
TRANSDUCER_HEIGHT_Z = 12.4
TRANSDUCER_PITCH_Y = 21.5

# The user confirmed that every hole center is 2.4 mm from its adjacent
# PCB edges in both X and Y directions.
REFERENCE_HOLE_DIAMETER = 3.0
REFERENCE_HOLE_CENTER_EDGE_OFFSET = 2.4


def build_model():
    pcb = (
        cq.Workplane("XY")
        .box(
            PCB_LENGTH_X,
            PCB_WIDTH_Y,
            PCB_THICKNESS_Z,
            centered=(True, True, False),
        )
        .edges("|Z")
        .fillet(PCB_CORNER_RADIUS)
    )

    hole_x = PCB_LENGTH_X / 2.0 - REFERENCE_HOLE_CENTER_EDGE_OFFSET
    hole_y = PCB_WIDTH_Y / 2.0 - REFERENCE_HOLE_CENTER_EDGE_OFFSET
    pcb = (
        pcb.faces(">Z")
        .workplane()
        .pushPoints([
            (-hole_x, -hole_y),
            (-hole_x, hole_y),
            (hole_x, -hole_y),
            (hole_x, hole_y),
        ])
        .hole(REFERENCE_HOLE_DIAMETER)
    )

    connector = (
        cq.Workplane("XY")
        .box(
            CONNECTOR_LENGTH_X,
            CONNECTOR_WIDTH_Y,
            CONNECTOR_HEIGHT_Z,
            centered=(True, True, True),
        )
        .translate((
            PCB_LENGTH_X / 2.0 - CONNECTOR_LENGTH_X / 2.0,
            0.0,
            -CONNECTOR_HEIGHT_Z / 2.0,
        ))
    )

    def transducer(center_y):
        return (
            cq.Workplane("XY")
            .circle(TRANSDUCER_DIAMETER / 2.0)
            .extrude(TRANSDUCER_HEIGHT_Z)
            .translate((0.0, center_y, PCB_THICKNESS_Z))
        )

    return (
        pcb
        .union(connector)
        .union(transducer(-TRANSDUCER_PITCH_Y / 2.0))
        .union(transducer(TRANSDUCER_PITCH_Y / 2.0))
    )


if __name__ == "__main__" and "show_object" in globals():
    show_object(build_model(), name="dfrobot_sen0388_urm09_reference")
