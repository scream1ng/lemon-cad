"""Version-one native part contract. Dimensions are millimetres in the XY plane."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


Length = Annotated[float, Field(gt=0.01, le=2000)]


class Feature(Strict):
    id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    suppressed: bool = False


class Sketch(Feature):
    type: Literal['sketch']
    profile: Literal['rectangle', 'circle']
    width: Length = 80
    height: Length = 50
    diameter: Length = 50


class Extrude(Feature):
    type: Literal['extrude']
    depth: Length


class Hole(Feature):
    type: Literal['hole']
    diameter: Length
    x: float = Field(ge=-2000, le=2000)
    y: float = Field(ge=-2000, le=2000)


class Fillet(Feature):
    type: Literal['fillet']
    radius: Length
    scope: Literal['outer_edges'] = 'outer_edges'


class CadDocumentV1(Strict):
    schema_version: Literal[1] = 1
    kind: Literal['part'] = 'part'
    units: Literal['mm'] = 'mm'
    features: list[Annotated[Sketch | Extrude | Hole | Fillet, Field(discriminator='type')]] = Field(min_length=2, max_length=34)
    rollback: int = Field(ge=2)

    @model_validator(mode='after')
    def dependencies(self):
        types = [f.type for f in self.features]
        if types[:2] != ['sketch', 'extrude'] or any(t not in ('hole', 'fillet') for t in types[2:]):
            raise ValueError('Begin with one sketch and one extrusion, then holes and an optional final fillet.')
        if types.count('fillet') > 1 or ('fillet' in types and types[-1] != 'fillet'):
            raise ValueError('Fillet must be the final feature. Insert holes before it.')
        if len({f.id for f in self.features}) != len(self.features):
            raise ValueError('Feature IDs must be unique.')
        if self.rollback > len(self.features):
            raise ValueError('Rollback is outside the feature history.')
        if self.features[0].suppressed or self.features[1].suppressed:
            raise ValueError('The base sketch and extrusion cannot be suppressed.')
        return self


Coordinate = Annotated[float, Field(ge=-2000, le=2000)]


class PlaneSketch(Feature):
    type: Literal['sketch']
    profile: Literal['rectangle', 'circle', 'polygon']
    plane: Literal['XY', 'XZ', 'YZ'] = 'XY'
    offset: Coordinate = 0
    x: Coordinate = 0
    y: Coordinate = 0
    width: Length = 80
    height: Length = 50
    diameter: Length = 50
    points: list[tuple[Coordinate, Coordinate]] = Field(default_factory=list, max_length=128)
    closed: bool = True


class ProfileExtrude(Feature):
    type: Literal['extrude']
    sketch_id: str
    operation: Literal['add', 'cut'] = 'add'
    direction: Literal[1, -1] = 1
    extent: Literal['depth', 'through_all'] = 'depth'
    depth: Length = 10


class CadDocumentV2(Strict):
    schema_version: Literal[2]
    kind: Literal['part'] = 'part'
    units: Literal['mm'] = 'mm'
    features: list[Annotated[PlaneSketch | ProfileExtrude | Hole | Fillet, Field(discriminator='type')]] = Field(min_length=2, max_length=128)
    rollback: int = Field(ge=2)

    @model_validator(mode='after')
    def dependencies(self):
        if [f.type for f in self.features[:2]] != ['sketch', 'extrude']:
            raise ValueError('Begin with a sketch and an additive extrusion.')
        base, extrusion = self.features[:2]
        if extrusion.operation != 'add' or base.suppressed or extrusion.suppressed:
            raise ValueError('The base sketch and additive extrusion cannot be suppressed.')
        if self.rollback > len(self.features):
            raise ValueError('Rollback is outside the feature history.')
        seen = {}
        extended = False
        for i, f in enumerate(self.features):
            if f.id in seen:
                raise ValueError('Feature IDs must be unique.')
            if f.type == 'extrude':
                if f.sketch_id not in seen or seen[f.sketch_id].type != 'sketch':
                    raise ValueError(f'Extrusion ({f.id}): select an earlier sketch.')
                if f.operation == 'add' and f.extent != 'depth':
                    raise ValueError(f'Extrusion ({f.id}): additive extrusions require a depth.')
                if i > 1:
                    extended = True
            elif f.type in ('hole', 'fillet'):
                # Preserve migrated version-one features before any general operations.
                if extended or base.plane != 'XY' or base.offset != 0 or base.x != 0 or base.y != 0 or base.profile == 'polygon' or extrusion.direction != 1:
                    raise ValueError(f'{f.type.title()} ({f.id}): legacy features require the original XY base; use a sketch cut for new holes.')
            elif i > 0:
                extended = True
            seen[f.id] = f
        return self


class SketchFrame(Strict):
    origin: tuple[Coordinate, Coordinate, Coordinate]
    u: tuple[float, float, float]
    v: tuple[float, float, float]

    @model_validator(mode='after')
    def orthonormal(self):
        if any(abs(sum(x*x for x in axis)-1) > 1e-8 for axis in (self.u, self.v)) or abs(sum(a*b for a,b in zip(self.u,self.v))) > 1e-8:
            raise ValueError('Sketch axes must be perpendicular unit vectors.')
        return self


class FaceSketch(PlaneSketch):
    plane: Literal['XY', 'XZ', 'YZ', 'FACE'] = 'XY'
    frame: SketchFrame | None = None

    @model_validator(mode='after')
    def face_plane(self):
        if (self.plane == 'FACE') != (self.frame is not None):
            raise ValueError('Face sketches require a frame; datum sketches must not have one.')
        if self.plane == 'FACE' and self.offset != 0:
            raise ValueError('Face sketches use the frame origin instead of a plane offset.')
        return self


class CadDocumentV3(CadDocumentV2):
    schema_version: Literal[3]
    features: list[Annotated[FaceSketch | ProfileExtrude | Hole | Fillet, Field(discriminator='type')]] = Field(min_length=2, max_length=128)


CadDocument = Annotated[CadDocumentV1 | CadDocumentV2 | CadDocumentV3, Field(discriminator='schema_version')]
_document = TypeAdapter(CadDocument)


def validate_document(value):
    return _document.validate_python(value)
