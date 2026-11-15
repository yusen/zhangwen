"""Fixed C3 assembly; STEP is data and models cannot select paths or code."""
from functools import lru_cache
import cadquery as cq
from .builtin_templates import TEMPLATES, checked_dependency

# Measured from the supplied STEP, mm. PCB lower face is source Z=0.
PCB_CENTER = (53.721107442215, 49.5935991871985)
SOCKET_CENTER = (53.462106939093, 49.149098298198)
SOCKET_TOP = 10.000050876399
HOLES = ((32.000064000128,26.99986499973),
         (74.500149000298,27.000054000108),
         (53.721107442215,72.009144018288))
PCB_SIZE = (52.55270510541,52.933705867411)


def _reference(key):
    path=checked_dependency(TEMPLATES['auto-open-lid-box-c3'],key)
    return _load(str(path))


@lru_cache(maxsize=2)
def _load(path):
    return cq.importers.importStep(path).val()


def assembly(center_x, center_y, pcb_z):
    shift=(center_x-PCB_CENTER[0],center_y-PCB_CENTER[1],pcb_z)
    expansion=_reference('expansion').translate(cq.Vector(*shift))
    # Core pad rows have +0.5mm length offset; compensate before alignment.
    core=(_reference('core').rotate((0,0,0),(0,0,1),90)
          .translate(cq.Vector(SOCKET_CENTER[0]+shift[0],
                              SOCKET_CENTER[1]-.5+shift[1],
                              pcb_z+SOCKET_TOP+.3+2.5)))
    return cq.Workplane('XY').newObject([core]),cq.Workplane('XY').newObject([expansion])


def tray(box_length, center_x, center_y, pcb_z, thickness=3.0):
    """Floor bridge, low locating lips, three measured-hole bosses and ribs."""
    if not 2 <= thickness <= 5 or not thickness+2.9 <= pcb_z <= 20:
        raise ValueError('托板厚度或PCB高度使底部焊针避让不足，至少留1毫米。')
    if not 6 <= center_x-PCB_SIZE[0]/2-box_length/2 <= 20:
        raise ValueError('扩展板距盒壁须为6至20毫米，保留加强筋和元件空间。')
    inner_x=box_length/2-.5
    outer_x=center_x+PCB_SIZE[0]/2+3.0
    half_y=PCB_SIZE[1]/2+3.0
    body=(cq.Workplane('XY').box(outer_x-inner_x,half_y*2,thickness,
                               centered=(True,True,False))
          .translate(((inner_x+outer_x)/2,center_y,0)))
    for x,y in HOLES:
        x+=center_x-PCB_CENTER[0]; y+=center_y-PCB_CENTER[1]
        boss=(cq.Workplane('XY').circle(3.2).extrude(pcb_z-thickness+.2)
              .translate((x,y,thickness-.2)))
        body=body.union(boss)
        pilot=cq.Workplane('XY').circle(1.25).extrude(pcb_z+1).translate((x,y,-.5))
        body=body.cut(pilot)
    # Low lips stay below the underside pins. The USB end is open.
    for x in (center_x-PCB_SIZE[0]/2-1.4,center_x+PCB_SIZE[0]/2+1.4):
        lip=(cq.Workplane('XY').box(1.6,PCB_SIZE[1]+4,1.3,
                                   centered=(True,True,False))
             .translate((x,center_y,thickness-.1)))
        body=body.union(lip)
    lip=(cq.Workplane('XY').box(PCB_SIZE[0]+4,1.6,1.3,
                              centered=(True,True,False))
         .translate((center_x,center_y+PCB_SIZE[1]/2+1.4,thickness-.1)))
    body=body.union(lip)
    for y in (center_y-18,center_y+18):
        rib=(cq.Workplane('XZ').polyline([(inner_x,thickness-.2),
                (center_x-PCB_SIZE[0]/2-2.3,thickness-.2),
                (inner_x,18)]).close().extrude(3)
             .translate((0,y+1.5,0)))
        body=body.union(rib)
    return body.clean()


def rear_assembly(center_y, pcb_z):
    """Rotate the complete aligned stack onto +Y; USB now faces +X."""
    return tuple(part.rotate((0, 0, 0), (0, 0, 1), 90)
                 for part in assembly(center_y, 0, pcb_z))


def rear_tray(box_width, center_y, pcb_z, thickness=3.0):
    """The same measured three-hole tray joins the rear wall below the hinge."""
    return tray(box_width, center_y, 0, pcb_z, thickness).rotate(
        (0, 0, 0), (0, 0, 1), 90)
