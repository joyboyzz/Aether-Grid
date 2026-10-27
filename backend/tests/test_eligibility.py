import unittest
from app.services.buyer_eligibility import rejection_reasons

class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.p = dict(commodity='Alphonso Mango', lot_kg=1000, requested_kg=1000,
            price=78, capacity_kg=2000, accepted_commodities=['Alphonso Mango'],
            escrow_inr=100000, distance_km=20, service_radius_km=50,
            rescue_radius_km=50, rvh_hours=2, approved=True)
    def test_eligible(self): self.assertEqual(rejection_reasons(**self.p), [])
    def test_each_gate(self):
        cases = [('accepted_commodities', [], 'commodity_mismatch'),
            ('requested_kg', 500, 'full_lot_required'),
            ('requested_kg', 1500, 'full_lot_required'),
            ('capacity_kg', 999, 'insufficient_capacity'),
            ('escrow_inr', 77999, 'insufficient_simulated_escrow'),
            ('distance_km', 51, 'outside_radius'),
            ('rvh_hours', .5, 'unreachable_before_rvh'),
            ('approved', False, 'policy_not_pre_authorized'),
            ('expired', True, 'auction_expired'),
            ('price', float('nan'), 'non_finite_or_missing_input')]
        for key, val, reason in cases:
            with self.subTest(key=key, val=val):
                self.assertIn(reason, rejection_reasons(**dict(self.p, **{key:val})))
    def test_exact_funds_and_capacity(self):
        self.assertEqual(rejection_reasons(**dict(self.p, capacity_kg=1000, escrow_inr=78000)), [])

if __name__ == '__main__': unittest.main()
