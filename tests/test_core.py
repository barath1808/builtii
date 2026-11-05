from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from builtii.audit import reconcile
from builtii.schema import validate_page, quantity
from builtii.pipeline import run, save_json
from builtii.evaluation import evaluate
from .helpers import item, page, make_pdf, FakeProvider


def audit(a, b=None, total=1):
    return reconcile([validate_page(a, a["page"])], [validate_page(b or deepcopy(a), (b or a)["page"])], total, [])


class EvidenceTests(unittest.TestCase):
    def test_agreement_has_no_accuracy_claim(self):
        report = audit(page())
        self.assertEqual(report["rows"][0]["status"], "supported")
        self.assertIsNone(report["accuracy_percentage"])

    def test_disagreement_preserves_both_values(self):
        row = audit(page(), page([item(13)]))["rows"][0]
        self.assertEqual((row["quantity"], row["ai2_quantity"]), ("12", "13"))
        self.assertEqual(row["status"], "review_required")

    def test_quantity_is_never_used_to_match(self):
        b = item(); b["asset_id"] = "B2"
        report = audit(page(), page([b]))
        self.assertEqual(len(report["rows"]), 2)
        self.assertTrue(all(r["status"] == "review_required" for r in report["rows"]))

    def test_different_work_actions_not_combined(self):
        report = audit(page(), page([item(action="remove")]))
        self.assertEqual(len(report["rows"]), 2)

    def test_unknown_action_is_not_installation(self):
        row = audit(page([item(action=None)]))["rows"][0]
        self.assertEqual(row["status"], "review_required")
        self.assertIsNone(row["ai1"]["scope"]["action"])

    def test_existing_to_remain_is_not_supported_work(self):
        self.assertEqual(audit(page([item(action="remain")]))["rows"][0]["status"],"review_required")

    def test_placeholder_ids_are_not_physical_identity(self):
        a=item(asset="UNKNOWN");a["identity_context"]="UNKNOWN"
        validated=validate_page(page([a]),1)
        self.assertIsNone(validated["items"][0]["asset_id"])

    def test_known_distinct_assets_can_be_supported_without_summing(self):
        a=item(asset="B1");b=item(asset="B2");b["evidence"][0]["bbox"]=[.6,.6,.9,.9]
        report=audit(page([a,b]))
        self.assertEqual(len(report["rows"]),2)
        self.assertTrue(all(r["status"]=="supported" for r in report["rows"]))

    def test_all_disciplines_use_same_contract(self):
        for work in ("light fixture", "foundation", "sod", "duct", "custom fabricated component"):
            a = item(description=work); a["scope"]["work_type"] = work
            self.assertEqual(audit(page([a]))["rows"][0]["status"], "supported")

    def test_ai2_only_item_is_visible(self):
        report = audit(page([]), page())
        self.assertIsNone(report["rows"][0]["quantity"])
        self.assertEqual(report["rows"][0]["ai2_quantity"], "12")

    def test_duplicate_views_are_not_summed(self):
        a = page(); b = page(number=2)
        report = reconcile([validate_page(a,1),validate_page(b,2)], [validate_page(a,1),validate_page(b,2)],2,[])
        self.assertEqual(len(report["rows"]),2)
        self.assertTrue(all(r["status"] == "review_required" for r in report["rows"]))

    def test_unknown_identity_repeated_scope_is_flagged(self):
        a = item(asset=None); b = item(asset=None); b["evidence"][0]["bbox"] = [.6,.6,.9,.9]
        report = audit(page([a,b]))
        self.assertTrue(all(r["status"] == "review_required" for r in report["rows"]))

    def test_one_to_many_match_is_not_certified(self):
        report = audit(page(),page([item(),item()]))
        self.assertEqual(len(report["rows"]),3)
        self.assertTrue(all(r["status"] == "review_required" for r in report["rows"]))

    def test_missing_page_affects_completeness_and_review_queue(self):
        report = audit(page(),total=2)
        self.assertFalse(report["processing_complete"])
        self.assertEqual(len(report["review_regions"]),2)

    def test_partial_page_keeps_regions_and_downgrades(self):
        a = page(); a["coverage"] = "partial"; a["review_regions"]=[{"reason":"Unreadable note", "bbox":[.7,.7,1,1]}]
        report = audit(a)
        self.assertEqual(report["rows"][0]["status"],"review_required")
        self.assertEqual(report["review_regions"][0]["bbox"],[.7,.7,1,1])

    def test_unknown_quantity_retained(self):
        a = item(); a["measurement"]["operation"] = "unresolved"; a["measurement"]["operands"] = []
        row = audit(page([a]))["rows"][0]
        self.assertIsNone(row["quantity"])
        self.assertEqual(row["status"],"review_required")

    def test_bad_calculation_retained_with_reason(self):
        a=item(); a["measurement"]["operands"][0]["unit"]="M"
        row=audit(page([a]))["rows"][0]
        self.assertIsNone(row["quantity"])
        self.assertTrue(row["reasons"])

    def test_typical_details_not_supported_installations(self):
        a=item();a["representation"]="typical_detail"
        self.assertEqual(audit(page([a]))["rows"][0]["status"],"review_required")

    def test_strict_schema_metadata_and_bbox(self):
        for mutate in (lambda p:p.update(page=2),lambda p:p.update(extra="invalid"),
                       lambda p:p["items"][0]["evidence"][0].update(bbox=[.8,.8,.1,.1])):
            p=page();mutate(p)
            with self.assertRaises(ValueError):validate_page(p,1)

    def test_nonfinite_and_boolean_are_rejected(self):
        for value in (float('nan'),float('inf'),True,-1):
            with self.assertRaises(ValueError):validate_page(page([item(value)]),1)

    def test_dimensional_calculation(self):
        a=item();a["unit"]="M2";a["measurement"]={"operation":"product","operands":[{"value":2,"unit":"M","quote":"2 m"},{"value":3,"unit":"M","quote":"3 m"}],"explanation":"Explicit rectangle dimensions"}
        self.assertEqual(quantity(a),"6")
        self.assertEqual(audit(page([a]))["rows"][0]["status"],"review_required")
        a["measurement"]["operands"][1]["unit"]="FT"
        with self.assertRaises(ValueError):quantity(a)

    def test_decimal_sum(self):
        a=item();a["unit"]="M";a["measurement"]={"operation":"sum","operands":[{"value":.1,"unit":"M","quote":"0.1 m"},{"value":.2,"unit":"M","quote":"0.2 m"}],"explanation":"Two distinct segments"}
        self.assertEqual(quantity(a),"0.3")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.pdf=self.root/"drawing.pdf";make_pdf(self.pdf)

    def test_end_to_end_cache_and_exports(self):
        provider=FakeProvider();folder,report=run(self.pdf,self.root/"out",provider)
        self.assertTrue(report["processing_complete"])
        self.assertEqual(len(provider.calls),2)
        self.assertTrue((folder/"previews/1.png").is_file())
        self.assertIn("12",(folder/"quantities.csv").read_text(encoding="utf-8-sig"))
        run(self.pdf,self.root/"out",provider)
        self.assertEqual(len(provider.calls),2)
        provider.models={"ai1":"changed","ai2":"test-auditor"}
        other,_=run(self.pdf,self.root/"out",provider)
        self.assertNotEqual(folder,other)
        self.assertEqual(len(provider.calls),4)

    def test_failed_auditor_and_resume(self):
        provider=FakeProvider(fail="ai2");folder,report=run(self.pdf,self.root/"out",provider)
        self.assertFalse(report["processing_complete"])
        self.assertEqual(report["rows"][0]["status"],"review_required")
        provider.fail=None;provider.calls=[]
        _,report=run(self.pdf,self.root/"out",provider)
        self.assertTrue(report["processing_complete"])
        self.assertEqual(provider.calls,[("ai2",1)])

    def test_force_failure_does_not_restore_stale_cache(self):
        provider=FakeProvider();folder,_=run(self.pdf,self.root/"out",provider)
        provider.fail="ai2";run(self.pdf,self.root/"out",provider,force=True)
        self.assertFalse((folder/"cache/ai2-1.json").exists())

    def test_corrupt_cache_is_reprocessed(self):
        provider=FakeProvider();folder,_=run(self.pdf,self.root/"out",provider)
        (folder/"cache/ai1-1.json").write_text('{}');provider.calls=[]
        run(self.pdf,self.root/"out",provider)
        self.assertEqual(provider.calls,[("ai1",1)])

    def test_render_failure_cannot_certify_cached_evidence(self):
        from unittest.mock import patch
        provider=FakeProvider();folder,_=run(self.pdf,self.root/"out",provider)
        with patch('builtii.pipeline.pdf.render',side_effect=ValueError('test')):
            _,report=run(self.pdf,self.root/"out",provider)
        self.assertFalse(report["processing_complete"])
        self.assertEqual(report["rows"][0]["status"],"review_required")

    def test_html_and_csv_injection(self):
        provider=FakeProvider()
        original=provider.extract
        def malicious(*args):
            p=original(*args);p['items'][0]['description']='<script>alert(1)</script>';return p
        provider.extract=malicious
        folder,_=run(self.pdf,self.root/"out",provider)
        html=(folder/"report.html").read_text()
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('&lt;script&gt;',html)
        from builtii.report import safe_cell
        self.assertEqual(safe_cell(' =1+2'),"' =1+2")

    def test_reviewed_boq_is_separate_and_run_bound(self):
        provider=FakeProvider();folder,report=run(self.pdf,self.root/"out",provider)
        ref=self.root/"reference.csv";ref.write_text('item_no,description,quantity,unit\nA,Structural members,12,EA\nB,Other item,2,EA\n')
        mapping=self.root/"mapping.json";save_json(mapping,{"run_id":report["run_id"],"items":{"A":["p1-ai1-1"]}})
        before=(folder/"report.json").read_bytes()
        result=evaluate(folder/"report.json",ref,mapping)
        self.assertEqual(result["metrics"]["comparison_coverage"],.5)
        self.assertEqual(result["metrics"]["exact_agreement"],1)
        self.assertEqual((folder/"report.json").read_bytes(),before)
        self.assertEqual(len(provider.calls),2)
        save_json(mapping,{"run_id":"different","items":{}})
        with self.assertRaises(ValueError):evaluate(folder/"report.json",ref,mapping)

    def test_boq_double_allocation_is_rejected(self):
        folder,report=run(self.pdf,self.root/"out",FakeProvider())
        ref=self.root/"reference.csv";ref.write_text('item_no,description,quantity,unit\nA,Members,12,EA\nB,Members,12,EA\n')
        mapping=self.root/"mapping.json";save_json(mapping,{"run_id":report["run_id"],"items":{"A":["p1-ai1-1"],"B":["p1-ai1-1"]}})
        with self.assertRaises(ValueError):evaluate(folder/"report.json",ref,mapping)

    def test_damaged_pdf_is_rejected(self):
        self.pdf.write_bytes(b'not a PDF')
        with self.assertRaises(ValueError):run(self.pdf,self.root/"out",FakeProvider())


if __name__=='__main__':unittest.main()
