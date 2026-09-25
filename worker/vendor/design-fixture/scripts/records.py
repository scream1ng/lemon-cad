"""Evidence identities and required checks shared by build and delivery validation."""
import hashlib
import json
from pathlib import Path

GEOMETRY_CHECKS = ('tab_slot_seat_bridge','material_width','nest','solid_integrity','contacts',
                   'constraint_independence','interference','step_roundtrip','fixture_insertion','clamp_mounts','hardware_geometry','mount_compactness','same_side_secondary','assembly_locating','mounting_height','cap_joints','cross_support')
ENGINEERING_CHECKS = ('source_survey','clamp_seating','clamp_motion','workpiece_loading','workpiece_unloading',
                      'weld_access','retention','strength','tolerances','distortion','trial_validation','assembly_tolerances','hardware_pose','hardware_clearance',
                      'rib_construction','fastener_access','pin_mechanisms')
REQUIRED_CHECKS = GEOMETRY_CHECKS + ENGINEERING_CHECKS
STATUSES = {'pass','fail','unknown','exception'}

def aggregate(values):
    values=list(values)
    return 'fail' if 'fail' in values else 'pass' if values and all(v=='pass' for v in values) else 'unknown'

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def check(name,status,measured=None,limit=None,units=None,scope='',evidence=None):
    return {'name':name,'status':status,'measured':measured,'limit':limit,'units':units,'scope':scope,
            'evidence':evidence or [],'next_action':None if status=='pass' else 'Resolve and rerun this check on this geometry revision.'}
