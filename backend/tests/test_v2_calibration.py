import unittest
from app.calibration.fit_q10 import fit
class CalibrationTests(unittest.TestCase):
    def rows(self):return [dict(lot_id=str(i),source='synthetic',split='train' if i<3 else 'holdout',temperature_c=t,observed_shelf_hours=264*2.8**(-(t-5)/10),shelf_reference_hours=264) for i,t in enumerate([5,15,25,12,22])]
    def test_recovers_known_synthetic_constant(self):
        r=fit(self.rows(),True);self.assertAlmostEqual(r['q10'],2.8);self.assertLess(r['holdout_mape_pct'],1e-10);self.assertFalse(r['configuration_changed'])
    def test_synthetic_not_field_evidence(self):
        with self.assertRaises(ValueError):fit(self.rows())
    def test_holdout_leakage_rejected(self):
        rows=self.rows();rows[-1]['lot_id']=rows[0]['lot_id']
        with self.assertRaises(ValueError):fit(rows,True)
    def test_missing_holdout_rejected(self):
        with self.assertRaises(ValueError):fit(self.rows()[:3],True)
