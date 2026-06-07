"""Curate a gold-standard corpus of municipal/federal legal PDFs.

Outputs:
- curated_corpus/ (renamed PDFs)
- curated_corpus_manifest.jsonl
- curated_corpus_summary.md
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit(
        "Missing dependency 'pypdf'. Install with: pip install -r requirements.txt"
    ) from exc


SELECTIONS = [
    ("KTM_NAT_001", "federal", "national_law", "स्थानीय सरकार सञ्चालन ऐन, २०७४", "ktm", "01_स्थानीय-सरकार-सञ्चालन-ऐन-२०७४.pdf"),
    ("KTM_NAT_002", "federal", "national_law", "राष्ट्रिय परिचयपत्र तथा पञ्जीकरण ऐन, २०७६", "ktm", "01_राष्ट्रिय-परिचयपत्र-तथा-पञ्जीकरण-ऐन-२०७६.pdf"),
    ("KTM_NAT_003", "federal", "national_law", "नेपाल नागरिकता ऐन, २०६३", "ktm", "01_नेपाल-नागरिकता-ऐन-२०६३.pdf"),
    ("KTM_NAT_004", "federal", "national_law", "मुलुकी देवानी संहिता ऐन, २०७४", "ktm", "01_मुलुकी-देवानी-संहिता-ऐन-२०७४.pdf"),
    ("KTM_NAT_005", "federal", "national_law", "मुलुकी देवानी कार्यविधि संहिता, २०७४", "ktm", "01_मुलुकी-देवानी-कार्यविधि-संहिता-२०७४.pdf"),
    ("KTM_NAT_006", "federal", "national_law", "मुलुकी फौजदारी कार्यविधि संहिता, २०७४", "ktm", "01_मुलुकी-फौजदारी-कार्यविधि-संहिता-२०७४.pdf"),
    ("KTM_NAT_007", "federal", "national_law", "भूउपयोग सम्बन्धि ऐन, २०७६", "ktm", "01_भूउपयोग-सम्बन्धि-ऐन-२०७६.pdf"),
    ("KTM_NAT_008", "federal", "national_law", "नागरिक अधिकार ऐन, २०१२", "ktm", "01_नागरिक-अधिकार-ऐन-२०१२.pdf"),
    ("KTM_NAT_009", "federal", "national_law", "प्रशासकीय कार्यविधि नियमित गर्ने ऐन, २०१३", "ktm", "01_प्रशासकीय-कार्यविधि-नियमित-गर्ने-ऐन-२०१३.pdf"),
    ("KTM_MUN_001", "kathmandu", "municipal_bylaw", "भवन निर्माण प्रमाणीकरण कार्यविधि, २०७३", "ktm", "01_भवन-निर्माण-प्रमाणिकरण-कार्यविधि-२०७३.pdf"),
    ("KTM_MUN_002", "kathmandu", "municipal_bylaw", "वडा कार्यालय प्रस्तावित कार्यविधि, २०७०", "ktm", "01_वडा-कार्यलयको-प्रस्तावित-कार्यविधि-२०७०.pdf"),
    ("KTM_MUN_003", "kathmandu", "municipal_bylaw", "कार्य सञ्चालन निर्देशिका, २०७४", "ktm", "01_कार्य-संचालन-निर्देशिका-२०७४.pdf"),
    ("KTM_MUN_004", "kathmandu", "administrative_procedure", "पुनर्निर्माण सम्बन्धी गुनासो व्यवस्थापन कार्यविधि, २०७४", "ktm", "01_पुननिर्माण-सम्बन्धी-गुनासो-व्यवस्थापन-कार्यविधि-२०७४.pdf"),
    ("KTM_MUN_005", "kathmandu", "administrative_procedure", "जन्म–मृत्यु तथा व्यक्तिगत घटना दर्ता गर्ने ऐन, २०३३", "ktm", "01_जन्म-मृत्यु-तथा-व्यक्तिगत-घटना-दर्ता-गर्ने-ऐन-२०३३.pdf"),
    ("KTM_MUN_006", "kathmandu", "administrative_procedure", "केही सार्वजनिक लिखत प्रमाणीकरण कार्यविधि ऐन, २०६३", "ktm", "01_केही-सार्वजनिक-लिखत-प्रमाणीकरण-कार्यविधि-ऐन-२०६३.pdf"),
    ("KTM_MUN_007", "kathmandu", "administrative_procedure", "प्रदेश स्तरका केही सार्वजनिक लिखत प्रमाणीकरण (पहिलो संशोधन) ऐन, २०७५", "ktm", "01_प्रदेश-स्तरका-केही-सार्वजनिक-लिखत-प्रमाणिकरणपहिलो-संशोधन-ऐन-२०७५.pdf"),
    ("KTM_MUN_008", "kathmandu", "municipal_bylaw", "बिभूषण सिफारिश तथा सम्मान सम्बन्धी ऐन, २०७६", "ktm", "01_बिभुषण-सिफारिश-तथा-सम्मान-र-पदक-सम्बन्धी-ऐन-२०७६.pdf"),
    ("KTM_FIN_001", "kathmandu", "financial_doc", "काठमाडौं महानगरपालिका आर्थिक ऐन, २०७४", "ktm", "01_काठमाडौं-महानगरपालिका-आर्थिक-ऐन-२०७४-1.pdf"),
    ("KTM_FIN_002", "kathmandu", "financial_doc", "कामपा आर्थिक ऐन, २०७८", "ktm", "01_कामपा-आर्थिक-ऐन-२०७८-1.pdf"),
    ("KTM_FIN_003", "kathmandu", "financial_doc", "काठमाडौं महानगरपालिका विनियोजन ऐन, २०७४", "ktm", "01_काठमाडौं-महानगरपालिका-विनियोजन-ऐन-२०७४.pdf"),
    ("KTM_FIN_004", "kathmandu", "financial_doc", "आर्थिक कार्यविधि तथा वित्तीय उत्तरदायित्व ऐन, २०७६", "ktm", "01_आर्थिक-कार्यविधि-तथा-वित्तीय-उत्तरदायित्व-ऐन-२०७६.pdf"),
    ("KTM_MUN_009", "kathmandu", "municipal_bylaw", "कर तथा गैरकर राजस्व सम्बन्धी ऐन, २०७५", "ktm", "01_कर-तथा-गैरकर-राजश्व-सम्बन्धी-ऐन-२०७५.pdf"),
    ("LMC_MUN_001", "lalitpur", "municipal_bylaw", "वडा सञ्चालन सम्बन्धी कार्यविधि, २०८१", "lmc", "वडा सञ्चालन सम्बन्धी कार्यविधि, २०८१ .pdf"),
    ("LMC_MUN_002", "lalitpur", "administrative_procedure", "घर जग्गा बहाल कर व्यवस्थापन कार्यविधि, २०८०", "lmc", "घर जग्गा बहाल कर व्यबस्थापन कार्यविधि, २०८०.pdf"),
    ("LMC_MUN_003", "lalitpur", "financial_doc", "कर तथा गैरकर राजस्व सम्बन्धी ऐन, २०८०", "lmc", "कर तथा गैरकर राजस्व सम्बन्धी ऐन, २०८०.pdf"),
    ("LMC_MUN_004", "lalitpur", "financial_doc", "व्यवसाय कर सम्बन्धी कार्यविधि, २०८०", "lmc", "व्यवसाय कर सम्बन्धी कार्यविधि, २०८०.pdf"),
    ("LMC_MUN_005", "lalitpur", "administrative_procedure", "उपभोक्ता समिति गठन परिचालन तथा व्यवस्थापन कार्यविधि, २०७८", "lmc", "उपभोक्ता समिति गठन परिचालन तथा व्यवस्थापन कार्यविधि, २०७८.pdf"),
    ("LMC_MUN_006", "lalitpur", "municipal_bylaw", "नगर सभाबाट गठित समितिहरुको कार्य सञ्चालन कार्यविधि, २०७५", "lmc", "ललितपुर महानगरपालिका नगर सभाबाट गठित समितिहरुको कार्य संचालन सम्वन्धी कार्यविधि २०७५.pdf"),
    ("LMC_MUN_007", "lalitpur", "administrative_procedure", "मेलमिलाप सम्बन्धी कार्य सञ्चालन निर्देशिका, २०८०", "lmc", "ललितपुर महानगरपालिका मेलमिलाप सम्बन्धी कार्य सञ्चालन निर्देशिका २०८०.pdf"),
    ("LMC_MUN_008", "lalitpur", "municipal_bylaw", "जग्गा विकास सम्बन्धी मापदण्ड, २०७६", "lmc", "ललितपुर महानगरपालिकाको जग्गा विकास सम्बन्धी मापदण्ड २०७६.pdf"),
    ("LMC_MUN_009", "lalitpur", "municipal_bylaw", "बस्ती विकास तथा भवन निर्माण आधारभूत मापदण्ड, २०७८", "lmc", "बस्ती विकास तथा भवन निर्माण सम्बन्धी आधारभूत निर्माण (दो सं) मापदण्ड, २०७८(1).pdf"),
    ("LMC_FIN_001", "lalitpur", "financial_doc", "आर्थिक कार्यविधि नियमित तथा व्यवस्थित गर्न बनेको ऐन, २०७५", "lmc", "आर्थिक कार्यविधि नियमित तथा व्यवस्थित गर्न बनेको ऐन २०७५.pdf"),
    ("LMC_MUN_010", "lalitpur", "administrative_procedure", "प्रशासकीय कार्यविधि ऐन, २०७५", "lmc", "प्रसशाकीय कार्यविधि ऐन २०७५.pdf"),
    ("LMC_FIN_002", "lalitpur", "financial_doc", "स्थानीय राजश्व परामर्श समितिको कार्य सञ्चालन कार्यविधि, २०८०", "lmc", "स्थानीय राजश्व परामर्श समितिको कार्य सञ्चालन कार्यविधि, २०८०.pdf"),
    ("LMC_FIN_003", "lalitpur", "financial_doc", "विपद् व्यवस्थापन कोष (सञ्चालन) कार्यविधि, २०८०", "lmc", "विपद् व्यवस्थापन कोष (सञ्चालन) कार्यविधि २०८०_0.pdf"),
    ("LMC_MUN_011", "lalitpur", "administrative_procedure", "करार सेवामा कर्मचारी पदपूर्ति सम्बन्धी कार्यविधि, २०८०", "lmc", "करार सेवामा कर्मचारी पदपूर्ति गर्ने सम्बन्धी कार्यविधि, २०८० .pdf"),
    ("LMC_MUN_012", "lalitpur", "administrative_procedure", "अपाङ्गता भएका व्यक्तिको परिचयपत्र वितरण", "lmc", "अपाङ्गता भएका व्यक्तिको परिचयपत्र वितरण.pdf"),
    ("BKT_MUN_001", "bhaktapur", "municipal_bylaw", "घर/भवन नक्सा पास तथा सूचिकरण कार्यविधि, २०७७", "bkt", "९ भक्तपुर नगरपालिका घर।भवनको नक्सा पास र सूचिकरकरण सम्बन्धी कार्यविधि २०७७.pdf"),
    ("BKT_MUN_002", "bhaktapur", "municipal_bylaw", "नक्सा पास सम्बन्धी संक्षिप्त, २०८०", "bkt", "४ नक्सा पास सम्बन्धी संक्षिप्त २०८०.pdf"),
    ("BKT_MUN_003", "bhaktapur", "financial_doc", "बहाल कर निर्देशिका, २०७९", "bkt", "४ भनपा बहाल कर निर्देशिका २०७९.pdf"),
    ("BKT_MUN_004", "bhaktapur", "administrative_procedure", "करारमा कर्मचारी व्यवस्थापन कार्यविधि, २०७५", "bkt", "१० भक्तपुर नगरपालिकामा करारमा कर्मचारी व्यवस्थापन गर्ने सम्बन्धी कार्यविधि २०७५.pdf"),
    ("BKT_MUN_005", "bhaktapur", "administrative_procedure", "प्रशासकीय कार्यविधि नियमित गर्ने ऐन", "bkt", "३ भक्तपुर नगरपालिकाको प्रशासकीय कार्यविधि नियमित गर्ने ऐन.pdf"),
    ("BKT_MUN_006", "bhaktapur", "administrative_procedure", "स्थानीय राजपत्र सम्बन्धी कार्यविधि, २०७५", "bkt", "४ भक्तपुर नगरपालिकाको स्थानीय राजपत्रसम्बन्धी कार्यविधि २०७५.pdf"),
    ("BKT_FIN_001", "bhaktapur", "financial_doc", "वडास्तरीय बजेट परिचालन तथा कार्यान्वयन कार्यविधि, २०७४", "bkt", "1. वडास्तरीय बजेट परिचालन तथा कार्यान्वयन सम्बन्धी कार्यविधि २०७४.pdf"),
    ("BKT_MUN_007", "bhaktapur", "administrative_procedure", "सवारी दर्ता तथा संचालन ऐन, २०७६", "bkt", "१० भक्तपुर नगरपालिका सवारी दर्ता तथा संचालन गर्न बनेको एन २०७६.pdf"),
    ("BKT_MUN_008", "bhaktapur", "administrative_procedure", "विपद् जोखिम न्यूनीकरण तथा व्यवस्थापन ऐन, २०७५", "bkt", "९ भक्तपुर नगरपालिकामा विपद् जोखिम न्यूनीकरण तथा व्यवस्थापन गर्न बनेको ऐन, २०७५.pdf"),
    ("BKT_FIN_002", "bhaktapur", "financial_doc", "विपद् व्यवस्थापन कोष परिचालन निर्देशिका, २०७६", "bkt", "९ भक्तपुर नगरपालिका विपद् व्यवस्थापन कोष परिचालन निर्देशिका २०७६.pdf"),
    ("BKT_FIN_003", "bhaktapur", "financial_doc", "भक्तपुर नगरपालिका आर्थिक ऐन, २०८२", "bkt", "भक्तपुर नगरपालिकाको आर्थिक ऐन २०८२.pdf"),
    ("BKT_FIN_004", "bhaktapur", "financial_doc", "भक्तपुर नगरपालिका विनियोजन ऐन, २०८१", "bkt", "2 भक्तपुर नगरपालिकाको विनियोजन ऐन २०८१.pdf"),
    ("BKT_FIN_005", "bhaktapur", "financial_doc", "सामाजिक सुरक्षा भत्ता वितरण कार्यविधि, २०७७", "bkt", "सामाजिक सुरक्षा भत्ता वितरण कार्यविधि २०७७.pdf"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument(
        "--ktm-root",
        type=Path,
        default=base / "kathmandu_laws_scrape_20260528_124219",
        help="Kathmandu scrape root directory.",
    )
    parser.add_argument(
        "--lmc-root",
        type=Path,
        default=base / "kathmandu_laws_scrape_20260528_132227",
        help="Lalitpur scrape root directory.",
    )
    parser.add_argument(
        "--bkt-root",
        type=Path,
        default=base / "kathmandu_laws_scrape_20260528_133926",
        help="Bhaktapur scrape root directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=base / "curated_corpus",
        help="Directory to write curated PDFs.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=base / "curated_corpus_manifest.jsonl",
        help="Manifest JSONL output path.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=base / "curated_corpus_summary.md",
        help="Summary markdown output path.",
    )
    return parser.parse_args()


def normalized_name(doc_id: str, title: str) -> str:
    name = f"{doc_id.lower()}_{title}.pdf"
    return name.replace(" ", "_").replace("/", "-").replace("।", "")


def build_name_map() -> dict[str, str]:
    return {doc_id: normalized_name(doc_id, title) for doc_id, _, _, title, _, _ in SELECTIONS}


def main() -> None:
    args = parse_args()
    roots = {"ktm": args.ktm_root, "lmc": args.lmc_root, "bkt": args.bkt_root}

    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    name_map = build_name_map()
    records = []
    missing = []

    for doc_id, source, category, title, root_key, filename in SELECTIONS:
        root = roots[root_key]
        matches = list(root.rglob(filename))
        if not matches:
            hint = filename.replace(".pdf", "")
            matches = [p for p in root.rglob("*.pdf") if hint in p.name]
        if not matches:
            missing.append((doc_id, filename, root))
            continue

        src = matches[0]
        dest = args.output_dir / name_map[doc_id]
        shutil.copy2(src, dest)

        reader = PdfReader(str(dest))
        page_count = len(reader.pages)
        text_sample = ""
        for page in reader.pages[:3]:
            text_sample += page.extract_text() or ""
        format_type = "text_based" if len(text_sample.strip()) > 200 else "scanned"

        if "नक्सा" in title or "भवन" in title or "जग्गा" in title:
            notes = "Includes building/land verification and permit workflows."
        elif "कर" in title or "राजस्व" in title or "आर्थिक" in title or "विनियोजन" in title:
            notes = "Contains tax/finance procedures and approval workflows."
        elif "कार्यविधि" in title or "निर्देशिका" in title:
            notes = "Procedural guidelines for municipal verification or recommendation."
        elif "सिफारिश" in title:
            notes = "Recommendation/sifarish related administrative procedures."
        else:
            notes = "Baseline legal reference for administrative verification workflows."

        records.append(
            {
                "doc_id": doc_id,
                "source": source,
                "category": category,
                "title": title,
                "file_path": str(dest),
                "format_type": format_type,
                "language": "ne",
                "page_count": page_count,
                "relevance_notes": notes,
            }
        )

    if missing:
        missing_lines = "\n".join(f"- {doc_id}: {fname} ({root})" for doc_id, fname, root in missing)
        raise SystemExit(f"Missing files:\n{missing_lines}")

    if not 30 <= len(records) <= 50:
        raise SystemExit(f"Expected 30–50 documents, got {len(records)}")

    with args.manifest.open("w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")

    cat_counts = Counter(r["category"] for r in records)
    source_counts = Counter(r["source"] for r in records)
    format_counts = Counter(r["format_type"] for r in records)

    summary_lines = [
        "# Curated Corpus Summary",
        "",
        f"Total documents: {len(records)}",
        "",
        "## Counts by Category",
    ]
    for key, value in cat_counts.items():
        summary_lines.append(f"- {key}: {value}")
    summary_lines += ["", "## Counts by Source"]
    for key, value in source_counts.items():
        summary_lines.append(f"- {key}: {value}")
    summary_lines += ["", "## Format Breakdown"]
    for key, value in format_counts.items():
        summary_lines.append(f"- {key}: {value}")
    summary_lines += ["", "## Documents"]
    for rec in records:
        summary_lines.append(
            f"- {rec['doc_id']} | {rec['source']} | {rec['category']} | {rec['title']} | {rec['format_type']} | {rec['page_count']} pages"
        )

    args.summary.write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"Curated {len(records)} documents -> {args.output_dir}")
    print(f"Manifest -> {args.manifest}")
    print(f"Summary -> {args.summary}")


if __name__ == "__main__":
    main()
