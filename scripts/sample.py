from pathlib import Path
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs

def sample(path):
    base = BRepPrimAPI_MakeBox(160, 70, 6).Shape()
    upright = BRepPrimAPI_MakeBox(160, 6, 90).Shape()
    shape = BRepAlgoAPI_Fuse(base, upright).Shape()
    for x in (35,125):
        for axis in (gp_Ax2(gp_Pnt(x,-1,60),gp_Dir(0,1,0)),gp_Ax2(gp_Pnt(x,45,-1),gp_Dir(0,0,1))):
            shape = BRepAlgoAPI_Cut(shape,BRepPrimAPI_MakeCylinder(axis,6,8).Shape()).Shape()
    writer=STEPControl_Writer();writer.Transfer(shape,STEPControl_AsIs);writer.Write(str(path))

if __name__ == '__main__':
    sample(Path('frontend/public/sample-bracket.step'))
