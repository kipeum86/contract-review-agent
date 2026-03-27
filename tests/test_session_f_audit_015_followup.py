import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


batch_module = load_module("batch_classify_followup", "scripts/batch_classify_and_publish.py")
coverage_module = load_module(
    "report_coverage_followup",
    ".claude/skills/index-manager/scripts/report-coverage.py",
)


class SessionFAudit015ClassifierTests(unittest.TestCase):
    def test_segment_clauses_maps_previous_investment_unmapped_patterns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "clean.md"
            md_path.write_text(
                "\n\n".join(
                    [
                        "(목적)\n본 계약은 투자자와 회사의 권리의무를 정한다.",
                        "(부채에 관한 사항)\n회사의 담보제공 및 입보 내역은 아래 기재와 같다.",
                        "(관계회사에 관한 사항)\n회사의 관계회사는 아래 기재와 같다.",
                        "(법령 위반, 소송 등에 관한 사항)\n회사는 인허가를 적법하게 보유하고 소송이 없다.",
                        "(기타)\n회사는 투자자 또는 그 실사관련 자문사들에게 제공한 주주명부 등 자료가 진실되고 중요한 사항을 생략하지 않았음을 확인한다.",
                        "(회사 등의 의무)\n회사는 후속투자와 같은 날 투자자에게 전환사채를 발행하여야 한다.",
                    ]
                ),
                encoding="utf-8",
            )

            structure = batch_module.parse_structure(md_path)
            clauses = batch_module.segment_clauses(md_path, structure, "ssa")

            heading_to_type = {clause["heading"]: clause["clause_type"] for clause in clauses}
            self.assertEqual(heading_to_type["목적"], "purpose")
            self.assertEqual(heading_to_type["부채에 관한 사항"], "indebtedness_liens")
            self.assertEqual(heading_to_type["관계회사에 관한 사항"], "affiliates_subsidiaries")
            self.assertEqual(heading_to_type["법령 위반, 소송 등에 관한 사항"], "litigation_regulatory_matters")
            self.assertEqual(heading_to_type["기타"], "disclosure_accuracy")
            self.assertEqual(heading_to_type["회사 등의 의무"], "obligations_general")

    def test_segment_clauses_applies_family_specific_patterns_for_employment_and_lease(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            employment_md = Path(tmpdir) / "employment.md"
            employment_md.write_text(
                "\n\n".join(
                    [
                        "(직무)\n근로자의 담당업무는 개발 및 운영이다.",
                        "(급여)\n기본급과 상여 및 복리후생은 별도로 정한다.",
                        "(근로시간)\n소정근로시간과 연장근로 기준은 회사 규정에 따른다.",
                        "(퇴직금)\n관련 법령에 따른 퇴직급여를 지급한다.",
                    ]
                ),
                encoding="utf-8",
            )

            lease_md = Path(tmpdir) / "lease.md"
            lease_md.write_text(
                "\n\n".join(
                    [
                        "(임대차 목적물)\n서울시 소재 사무실 전용면적 100평을 임대한다.",
                        "(차임 및 보증금)\n보증금과 월 차임은 다음과 같다.",
                        "(사용 목적)\n임차인은 사무실 용도로만 사용한다.",
                        "(수선의무)\n구조적 하자는 임대인이 수리한다.",
                        "(보증금 반환)\n임대인은 명도 후 14일 내 보증금을 반환한다.",
                    ]
                ),
                encoding="utf-8",
            )

            employment_clauses = batch_module.segment_clauses(
                employment_md,
                batch_module.parse_structure(employment_md),
                "employment",
            )
            lease_clauses = batch_module.segment_clauses(
                lease_md,
                batch_module.parse_structure(lease_md),
                "lease",
            )

            self.assertEqual(
                [clause["clause_type"] for clause in employment_clauses],
                [
                    "employee_duties",
                    "compensation_benefits",
                    "working_hours_overtime",
                    "severance_retirement",
                ],
            )
            self.assertEqual(
                [clause["clause_type"] for clause in lease_clauses],
                [
                    "premises_description",
                    "rent_deposit",
                    "permitted_use",
                    "maintenance_repairs",
                    "security_deposit_return",
                ],
            )


class SessionFAudit015CoverageTests(unittest.TestCase):
    def test_coverage_report_includes_top_unmapped_headings(self):
        report = coverage_module.build_coverage_report(
            family_policy={"families": [{"id": "ssa"}, {"id": "sha"}]},
            clause_taxonomy={"categories": []},
            documents_index={"documents": []},
            clauses_index={
                "clauses": [
                    {"contract_family": "ssa", "clause_type": "unmapped", "heading": "부채에 관한 사항"},
                    {"contract_family": "ssa", "clause_type": "unmapped", "heading": "(부채에 관한 사항)"},
                    {"contract_family": "sha", "clause_type": "unmapped", "heading": "목적"},
                ]
            },
        )

        self.assertEqual(report["top_unmapped_headings"][0], {"heading": "부채에 관한 사항", "count": 2})
        self.assertEqual(report["unmapped_headings_by_family"]["ssa"][0], {"heading": "부채에 관한 사항", "count": 2})
        self.assertEqual(report["unmapped_headings_by_family"]["sha"][0], {"heading": "목적", "count": 1})


class SessionFAudit015PolicyDocsTests(unittest.TestCase):
    def test_clause_taxonomy_contains_followup_domain_types(self):
        taxonomy = yaml.safe_load(
            (REPO_ROOT / "contract-review/library/policies/clause-taxonomy.yaml").read_text(encoding="utf-8")
        )
        clause_type_ids = {
            clause_type["id"]
            for category in taxonomy["categories"]
            for clause_type in category.get("clause_types", [])
        }

        for expected in {
            "purpose",
            "employee_duties",
            "compensation_benefits",
            "working_hours_overtime",
            "severance_retirement",
            "premises_description",
            "rent_deposit",
            "permitted_use",
            "maintenance_repairs",
            "security_deposit_return",
            "indebtedness_liens",
            "affiliates_subsidiaries",
            "litigation_regulatory_matters",
            "disclosure_accuracy",
        }:
            self.assertIn(expected, clause_type_ids)

    def test_review_guide_contains_lease_risk_reference(self):
        review_guide = (
            REPO_ROOT / ".claude/skills/review-domain-knowledge/references/review-guide.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Lease Contracts (임대차계약)", review_guide)
        self.assertIn("보증금 반환", review_guide)
        self.assertIn("원상복구", review_guide)


if __name__ == "__main__":
    unittest.main()
