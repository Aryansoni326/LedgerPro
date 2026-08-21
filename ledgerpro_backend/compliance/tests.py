from django.test import TestCase

from compliance.adapters import get_adapter, get_adapter_for_firm
from compliance.adapters.base import TaxBreakdown
from compliance.adapters.india_gst import IndiaGSTAdapter
from compliance.adapters.us_salestax import USSalesTaxAdapter
from compliance.adapters.registry import registered_jurisdictions


class _FakeFirm:
    """Lightweight stand-in so tests don't need the DB."""
    def __init__(self, jurisdiction='IN', gstin='27AAAAA1111A1Z1'):
        self.jurisdiction = jurisdiction
        self.gstin = gstin


# ── registry tests ──────────────────────────────────────────────
class RegistryTests(TestCase):
    def test_get_adapter_india(self):
        a = get_adapter('IN')
        self.assertIsInstance(a, IndiaGSTAdapter)

    def test_get_adapter_us(self):
        a = get_adapter('US')
        self.assertIsInstance(a, USSalesTaxAdapter)

    def test_get_adapter_unknown_raises(self):
        with self.assertRaises(ValueError):
            get_adapter('XX')

    def test_get_adapter_for_firm_default(self):
        firm = _FakeFirm(jurisdiction=None)
        a = get_adapter_for_firm(firm)
        self.assertIsInstance(a, IndiaGSTAdapter)

    def test_registered_jurisdictions(self):
        codes = [code for code, _ in registered_jurisdictions()]
        self.assertIn('IN', codes)
        self.assertIn('US', codes)


# ── India GST adapter tests ────────────────────────────────────
class IndiaGSTValidationTests(TestCase):
    def setUp(self):
        self.adapter = IndiaGSTAdapter()

    def test_valid_gstin(self):
        result = self.adapter.validate_tax_id('27AAAAA1111A1Z1')
        self.assertTrue(result.valid)
        self.assertEqual(result.normalised, '27AAAAA1111A1Z1')

    def test_valid_gstin_lowercase(self):
        result = self.adapter.validate_tax_id('27aaaaa1111a1z1')
        self.assertTrue(result.valid)

    def test_invalid_gstin(self):
        result = self.adapter.validate_tax_id('INVALID')
        self.assertFalse(result.valid)
        self.assertIn('Invalid GSTIN', result.error_message)

    def test_empty_gstin(self):
        result = self.adapter.validate_tax_id('')
        self.assertFalse(result.valid)

    def test_tax_component_keys(self):
        self.assertEqual(self.adapter.tax_component_keys(), ['cgst', 'sgst', 'igst', 'cess'])

    def test_extract_tax_from_text(self):
        text = "CGST @ 9%  900.00  SGST @ 9%  900.00  Total 11,800.00"
        breakdown = self.adapter.extract_tax_from_text(text)
        self.assertEqual(breakdown.components['cgst'], 900.0)
        self.assertEqual(breakdown.components['sgst'], 900.0)
        self.assertEqual(breakdown.components['igst'], 0.0)

    def test_check_tax_consistency_valid_intra(self):
        parsed = {'cgst': 100, 'sgst': 100, 'igst': 0}
        result = self.adapter.check_tax_consistency(parsed)
        self.assertTrue(result.consistent)

    def test_check_tax_consistency_conflicting(self):
        parsed = {'cgst': 100, 'sgst': 100, 'igst': 50}
        result = self.adapter.check_tax_consistency(parsed)
        self.assertFalse(result.consistent)
        self.assertTrue(any('conflicting' in w for w in result.warnings))

    def test_check_tax_consistency_invalid_gstin_format(self):
        parsed = {'gstin_from': 'BAD', 'cgst': 0, 'sgst': 0, 'igst': 0}
        result = self.adapter.check_tax_consistency(parsed)
        self.assertFalse(result.consistent)
        self.assertTrue(any('Invalid' in w for w in result.warnings))

    def test_compute_tax_total(self):
        raw = {'cgst': 100, 'sgst': 100, 'igst': 0, 'cess': 10}
        self.assertEqual(self.adapter.compute_tax_total(raw), 210.0)

    def test_extract_party_tax_ids(self):
        text = "Seller: 27AAAAA1111A1Z1  Buyer: 24BBBBB2222B2Z2"
        seller, buyer = self.adapter.extract_party_tax_ids(text)
        self.assertEqual(seller, '27AAAAA1111A1Z1')
        self.assertEqual(buyer, '24BBBBB2222B2Z2')

    def test_export_column_map_has_all_keys(self):
        cols = self.adapter.export_column_map()
        self.assertIn('gstin_from', cols)
        self.assertIn('cgst', cols)

    def test_build_mock_tax_fields_sale(self):
        fields = self.adapter.build_mock_tax_fields(is_sale=True, firm_tax_id='27AAAAA1111A1Z1')
        self.assertEqual(fields['gstin_from'], '27AAAAA1111A1Z1')

    def test_build_mock_tax_fields_purchase(self):
        fields = self.adapter.build_mock_tax_fields(is_sale=False, firm_tax_id='27AAAAA1111A1Z1')
        self.assertEqual(fields['gstin_to'], '27AAAAA1111A1Z1')

    def test_jurisdiction_identity(self):
        self.assertEqual(self.adapter.jurisdiction_code, 'IN')
        self.assertEqual(self.adapter.tax_id_field_name, 'gstin')
        self.assertEqual(self.adapter.tax_id_label, 'GSTIN')


# ── US stub adapter tests ──────────────────────────────────────
class USSalesTaxAdapterTests(TestCase):
    def setUp(self):
        self.adapter = USSalesTaxAdapter()

    def test_valid_ein(self):
        result = self.adapter.validate_tax_id('12-3456789')
        self.assertTrue(result.valid)

    def test_invalid_ein(self):
        result = self.adapter.validate_tax_id('INVALID')
        self.assertFalse(result.valid)

    def test_jurisdiction_identity(self):
        self.assertEqual(self.adapter.jurisdiction_code, 'US')
        self.assertEqual(self.adapter.tax_id_field_name, 'ein')

    def test_tax_component_keys(self):
        self.assertEqual(self.adapter.tax_component_keys(), ['sales_tax', 'use_tax'])

    def test_check_tax_consistency_always_valid(self):
        result = self.adapter.check_tax_consistency({})
        self.assertTrue(result.consistent)


# ── extensibility acceptance test ───────────────────────────────
class ExtensibilityTests(TestCase):
    """Adding a new jurisdiction requires no changes outside compliance/adapters/."""

    def test_us_adapter_works_without_core_changes(self):
        firm = _FakeFirm(jurisdiction='US')
        adapter = get_adapter_for_firm(firm)
        self.assertIsInstance(adapter, USSalesTaxAdapter)
        self.assertEqual(adapter.jurisdiction_code, 'US')
        result = adapter.validate_tax_id('12-3456789')
        self.assertTrue(result.valid)


class TaxBreakdownTests(TestCase):
    def test_total_property(self):
        tb = TaxBreakdown(components={'a': 10.0, 'b': 20.5})
        self.assertAlmostEqual(tb.total, 30.5)

    def test_empty_total(self):
        tb = TaxBreakdown()
        self.assertEqual(tb.total, 0.0)
