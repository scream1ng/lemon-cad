"""Regression tests for omitted construction and pin-release evidence."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from construction_checks import evidence_errors, RIB_SECTIONS, ACCESS_SECTIONS, PIN_SECTIONS, MOVING_SECTIONS
from records import REQUIRED_CHECKS, check

FP = 'a' * 64

def findings(sections):
    return {s: {'status': 'pass', 'method': 'Measured CAD faces and clearance envelope',
                'measurements': {'clearance_mm': 2}, 'acceptance': {'minimum_mm': 1}}
            for s in sections}

def gate(name, rows):
    c = check(name, 'pass', {'basis': 'reopened_step', 'items': rows}, 'measured criteria',
              'mm', 'named CAD components', [{'file': 'report.json', 'sha256': 'b' * 64}])
    c['geometry_fingerprint'] = FP
    return c

class ConstructionChecks(unittest.TestCase):
    def setUp(self):
        self.spec = {'plates': [{'name': 'RIB', 'seat': 'BASE', 'w': [0, 1, 0]}],
                     'clamps': [{'tag': 'T1', 'hardware': 'GH-201-B', 'mount_plate': 'RIB'}],
                     'pin_locators': [{'id': 'P1', 'shape_name': 'REF_PIN_P1', 'mode': 'sliding', 'orientation_sensitive': True}]}
        self.names = {'RIB', 'BRACE', 'REF_PIN_P1', 'REF_BUSH_P1', 'HANDLE', 'STOP', 'KEY', 'RETAINER'}
        self.pin = {'id': 'P1', 'component_names': list(self.names),
                    'mechanism': {'pin': ['REF_PIN_P1'], 'carrier': ['RIB'], 'bush': ['REF_BUSH_P1'],
                                  'handle': ['HANDLE'], 'travel_stop': ['STOP'], 'retention': ['RETAINER'], 'anti_rotation': ['KEY']},
                    'findings': findings(PIN_SECTIONS + MOVING_SECTIONS),
                    'motion_mm': {'withdrawal': 30, 'required_withdrawal': 28,
                                  'minimum_guide_engagement': 20, 'required_guide_engagement': 15}}
    def errors(self, c, names=None):
        return evidence_errors(c, self.spec, FP, self.names if names is None else names)
    def test_required_gates_registered(self):
        self.assertTrue({'rib_construction', 'fastener_access', 'pin_mechanisms'} <= set(REQUIRED_CHECKS))
    def test_complete_measured_pin_record_accepted(self):
        self.assertEqual(self.errors(gate('pin_mechanisms', [self.pin])), [])
    def test_plain_pin_without_bush_or_handle_rejected(self):
        del self.pin['mechanism']['bush']; del self.pin['mechanism']['handle']
        errors = self.errors(gate('pin_mechanisms', [self.pin]))
        self.assertTrue(any('/bush' in e for e in errors)); self.assertTrue(any('/handle' in e for e in errors))
    def test_bush_in_record_but_missing_from_step_rejected(self):
        self.assertTrue(any('absent from exported' in e for e in self.errors(gate('pin_mechanisms', [self.pin]), self.names - {'REF_BUSH_P1'})))
    def test_insufficient_stroke_and_engagement_rejected(self):
        for dimension in ('withdrawal', 'minimum_guide_engagement'):
            with self.subTest(dimension=dimension):
                pin = copy.deepcopy(self.pin); pin['motion_mm'][dimension] = 1
                self.assertTrue(any(dimension in e for e in self.errors(gate('pin_mechanisms', [pin]))))
    def test_relief_without_orientation_control_rejected(self):
        del self.pin['mechanism']['anti_rotation']
        self.assertTrue(any('anti_rotation' in e for e in self.errors(gate('pin_mechanisms', [self.pin]))))
    def test_unlisted_actual_pin_cannot_claim_no_pins(self):
        self.spec['pin_locators'] = []
        c = gate('pin_mechanisms', []); c['measured']['not_applicable_reason'] = 'No pins'
        self.assertTrue(any('inventory disagrees' in e for e in self.errors(c)))
    def test_fixed_pin_does_not_require_sliding_bush(self):
        self.spec['pin_locators'][0]['mode'] = 'fixed'
        for k in ('bush', 'handle', 'travel_stop', 'anti_rotation'): del self.pin['mechanism'][k]
        self.assertEqual(self.errors(gate('pin_mechanisms', [self.pin])), [])
    def removable_pin(self):
        self.spec['pin_locators'][0]['mode'] = 'removable'
        pin = copy.deepcopy(self.pin)
        pin['mechanism'] = {'pin': ['REF_PIN_P1'], 'carrier': ['RIB'],
                            'bush': ['REF_BUSH_P1'], 'grip': ['REF_PIN_P1']}
        pin['component_names'] = ['REF_PIN_P1', 'RIB', 'REF_BUSH_P1']
        pin['motion_mm'].update(grip_length=35, required_grip_length=25)
        pin['manual_operation'] = {'travel_reference': 'IN/OUT marks measured at bush rear face',
                                   'retention': 'Horizontal seated position assessed for this operation',
                                   'relief_orientation': 'Align rear-end line to carrier mark each cycle'}
        return pin
    def test_measured_manual_dowel_needs_no_fictional_captive_hardware(self):
        pin = self.removable_pin()
        self.assertEqual(self.errors(gate('pin_mechanisms', [pin]), set(pin['component_names'])), [])
    def test_removable_pin_still_needs_real_bush_and_usable_grip(self):
        pin = self.removable_pin()
        for role in ('bush', 'grip'):
            with self.subTest(role=role):
                bad = copy.deepcopy(pin); del bad['mechanism'][role]
                self.assertTrue(any('/'+role in e for e in self.errors(gate('pin_mechanisms', [bad]))))
        pin['motion_mm']['grip_length'] = 2
        self.assertTrue(any('grip_length' in e for e in self.errors(gate('pin_mechanisms', [pin]))))
    def test_manual_operation_cannot_omit_orientation_travel_or_retention(self):
        pin = self.removable_pin()
        for field in pin['manual_operation']:
            with self.subTest(field=field):
                bad = copy.deepcopy(pin); del bad['manual_operation'][field]
                self.assertTrue(any(field in e for e in self.errors(gate('pin_mechanisms', [bad]))))
        pin['findings']['retention']['status'] = 'unknown'
        self.assertTrue(any('/retention' in e for e in self.errors(gate('pin_mechanisms', [pin]))))
    def test_removable_guidance_still_required_before_tip_disengages(self):
        pin = self.removable_pin(); pin['motion_mm']['minimum_guide_engagement'] = 0
        self.assertTrue(any('minimum_guide_engagement' in e for e in self.errors(gate('pin_mechanisms', [pin]))))
    def test_optional_hardware_cannot_name_absent_solids(self):
        pin = self.removable_pin(); pin['mechanism']['anti_rotation'] = ['MISSING_KEY']
        pin['component_names'].append('MISSING_KEY')
        self.assertTrue(any('absent from exported' in e for e in self.errors(gate('pin_mechanisms', [pin]))))
    def test_mechanism_roles_must_be_in_component_inventory(self):
        pin = self.removable_pin(); pin['component_names'].remove('REF_BUSH_P1')
        self.assertTrue(any('omitted from component_names' in e for e in self.errors(gate('pin_mechanisms', [pin]))))
    def test_stale_evidence_rejected(self):
        c = gate('pin_mechanisms', [self.pin]); c['geometry_fingerprint'] = 'c' * 64
        self.assertTrue(any('fingerprint' in e for e in self.errors(c)))
    def test_tabbed_upright_cannot_be_exempted(self):
        c = gate('rib_construction', [{'id': 'RIB', 'component_names': ['RIB'], 'applicable': False, 'reason': 'Two base tabs'}])
        self.assertTrue(any('cannot be exempted' in e for e in self.errors(c)))
    def test_braced_rib_needs_joint_and_dry_fit_evidence(self):
        row = {'id': 'RIB', 'component_names': ['RIB', 'BRACE'], 'applicable': True, 'findings': findings(RIB_SECTIONS)}
        self.assertEqual(self.errors(gate('rib_construction', [row])), [])
        del row['findings']['joints']; del row['findings']['dry_fit']
        errors = self.errors(gate('rib_construction', [row]))
        self.assertTrue(any('/joints' in e for e in errors)); self.assertTrue(any('/dry_fit' in e for e in errors))
    def test_nominal_fit_alone_does_not_certify_rib_handling_clearance(self):
        row = {'id': 'RIB', 'component_names': ['RIB', 'BRACE'], 'applicable': True,
               'findings': findings(RIB_SECTIONS)}
        del row['findings']['handling_clearance']
        self.assertTrue(any('/handling_clearance' in e for e in self.errors(gate('rib_construction', [row]))))
    def test_fastener_check_covers_every_hole_and_backside_access(self):
        row = {'id': 'T1', 'component_names': ['RIB'], 'holes': [{'id': f'H{i}', 'stage': 'Assembled fixture', 'findings': findings(ACCESS_SECTIONS)} for i in range(1, 5)]}
        self.assertEqual(self.errors(gate('fastener_access', [row])), [])
        row['holes'][3]['findings']['screw_end']['status'] = 'fail'
        self.assertTrue(any('screw_end' in e for e in self.errors(gate('fastener_access', [row]))))
        row['holes'].pop()
        self.assertTrue(any('hole coverage' in e for e in self.errors(gate('fastener_access', [row]))))
    def test_unknown_is_allowed_as_incomplete_review(self):
        c = gate('pin_mechanisms', []); c['status'] = 'unknown'
        self.assertEqual(self.errors(c), [])
    def test_unsupported_yes_only_evidence_rejected(self):
        c = gate('pin_mechanisms', [self.pin]); c['measured'] = {'checked': True}
        self.assertTrue(self.errors(c))
    def test_missing_rows_and_duplicate_rows_rejected(self):
        self.assertTrue(self.errors(gate('pin_mechanisms', [])))
        self.assertTrue(self.errors(gate('pin_mechanisms', [self.pin, self.pin])))
    def test_invalid_numeric_motion_rejected(self):
        for value in (None, True, float('nan'), float('inf'), -1):
            with self.subTest(value=value):
                pin = copy.deepcopy(self.pin); pin['motion_mm']['withdrawal'] = value
                self.assertTrue(self.errors(gate('pin_mechanisms', [pin])))

if __name__ == '__main__': unittest.main()
