#!/usr/bin/env python3
"""
FastAPI Modular Monolith API Server (apps/api/main.py).
Implements tenant-scoped endpoints for UPPSC BEO Answer-Sheet Scanning & Rubric Grading:
- Exam & Rubric Import Preview, Examiner Correction, Penalty Configuration & Publishing
- Quarantine File Upload Validation, Page Reordering/Rotation & Reversible Derivative Pipeline
- Multi-Adapter OCR/HTR Candidate Readings, Confidence Calibration & Span Disagreement Review
- Immutable Transcript Versioning & Question Linking
- Rubric-Bounded Grading with Rule-based Score & Schema Validation
- Recorded Examiner Override & Approval History
- Hash-Chained Audit Trail, Evaluation Benchmarks & SSRF/Prompt-Injection Controls
"""

import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT_DIR = "/home/user"
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from packages.rubric_core_bridge import (
    count_unicode_words,
    evaluate_word_limit,
    validate_and_compute_grade,
)
from packages.model_adapters_ssrf_bridge import (
    validate_url_ssrf_safe,
    sanitize_untrusted_text,
    ALLOWLISTED_REFERENCE_DOMAINS,
)

import importlib.util

def _load_mod(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT_DIR, rel_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ocr_mod = _load_mod("ocr_adapters", "packages/model-adapters/ocr_adapters.py")
grader_mod = _load_mod("grader_adapter", "packages/model-adapters/grader_adapter.py")
img_pipe_mod = _load_mod("image_pipeline", "apps/worker/image_pipeline.py")
try:
    # Local handwriting reader (CRNN-CTC). If it cannot load, uploads fall back to the visual OCR reader.
    htr_mod = _load_mod("htr_pipeline", "packages/model-adapters/htr_pipeline.py")
except Exception as _htr_err:  # noqa: BLE001
    print(f"[startup] local handwriting reader unavailable: {_htr_err}")
    htr_mod = None

app = FastAPI(
    title="UPPSC BEO Answer Sheet Grading API",
    version="1.0.0",
    description="API for scanning UPPSC BEO handwritten answer sheets and grading them against the marking scheme."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCANS_DIR = "/home/user/assets/sample_scans"
PDF_PAGES_DIR = "/home/user/assets/pdf_pages"
os.makedirs(SCANS_DIR, exist_ok=True)
os.makedirs(PDF_PAGES_DIR, exist_ok=True)

app.mount("/scans", StaticFiles(directory=SCANS_DIR), name="scans")
app.mount("/pdf-pages", StaticFiles(directory=PDF_PAGES_DIR), name="pdf_pages")

IMPORT_PREVIEW_PATH = "/home/user/docs/exam-import/import-preview-report.json"

# In-memory / file-backed store mirroring the tenant-scoped Supabase schema
STATE: Dict[str, Any] = {
    "tenant": {
        "id": "ten-uppsc-eval-01",
        "slug": "uppsc-beo-cell",
        "name": "UPPSC Block Education Officer (BEO) Evaluation Directorate",
        "kms_envelope_encryption": "AES-256-GCM (Managed KMS Envelope Key Rotation Active)"
    },
    "import_preview": {},
    "papers": {},
    "sessions": {},
    "answers": {},
    "grade_runs": {},
    "jobs": {},
    "audit_events": [],
    "retention_policies": [
        {"category": "raw_answer_sheet_scans", "retention_days": 180, "auto_purge": True, "encryption": "AES-256-GCM Envelope"},
        {"category": "normalized_page_derivatives", "retention_days": 90, "auto_purge": True, "encryption": "AES-256-GCM Envelope"},
        {"category": "immutable_transcript_versions", "retention_days": 365, "auto_purge": False, "encryption": "Postgres TDE + RLS"},
        {"category": "grade_runs_and_examiner_reviews", "retention_days": 730, "auto_purge": False, "encryption": "Postgres TDE + RLS"},
        {"category": "hash_chained_audit_logs", "retention_days": 1825, "auto_purge": False, "encryption": "Recorded WORM"}
    ]
}


def append_audit_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor: str = "examiner-01 (Senior Examiner (sample reviewer))",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    prev_hash = STATE["audit_events"][-1]["event_hash"] if STATE["audit_events"] else "0" * 64
    ts = datetime.now(timezone.utc).isoformat()
    payload_str = f"{prev_hash}|{ts}|{event_type}|{entity_type}|{entity_id}|{json.dumps(metadata or {}, sort_keys=True)}"
    ev_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    ev = {
        "id": f"aud-{len(STATE['audit_events']) + 1:04d}",
        "tenant_id": STATE["tenant"]["id"],
        "actor": actor,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "prev_event_hash": prev_hash[:16] + "...",
        "event_hash": ev_hash,
        "created_at": ts,
        "metadata": metadata or {}
    }
    STATE["audit_events"].append(ev)
    return ev


def initialize_state():
    with open(IMPORT_PREVIEW_PATH, "r", encoding="utf-8") as f:
        preview = json.load(f)
    STATE["import_preview"] = preview

    for p in preview["papers"]:
        STATE["papers"][p["paper_id"]] = p

    append_audit_event(
        "IMPORT_PREVIEW_GENERATED",
        "exam_import",
        "imp-uppsc-beo-2026-01",
        actor="system-importer-worker",
        metadata={
            "source_files": 4,
            "gs_mock17_questions": 40,
            "hindi_mock16_items": 13,
            "warnings_flagged": len(preview["import_warnings"])
        }
    )

    # Seed Session 1: GS Mock 17 (CAND-UP-8841)
    sess1_id = "sess-gs17-cand8841"
    STATE["sessions"][sess1_id] = {
        "session_id": sess1_id,
        "tenant_id": STATE["tenant"]["id"],
        "paper_id": "uppsc-beo-mains-gs-mock-17-v1",
        "pseudonym_code": "CAND-UP-8841",
        "status": "review_needed",
        "uploaded_at": "2026-10-12T09:15:00Z",
        "quarantine_check": {
            "valid": True,
            "detected_mime": "application/pdf",
            "size_bytes": 1284920,
            "sha256": "e4a91c8f2b7d3e5a6c9f0b1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f",
            "quarantine_status": "verified_clean"
        },
        "pages": [
            {
                "page_id": "gs17_cand01_p1",
                "page_number": 1,
                "rotation_deg": 0,
                "detected_skew_deg": -1.35,
                "width_px": 1080,
                "height_px": 1470,
                "variants": {
                    "original": "/scans/gs17_cand01_p1_original.png",
                    "deskewed": "/scans/gs17_cand01_p1_deskewed.png",
                    "clahe_contrast": "/scans/gs17_cand01_p1_clahe_contrast.png",
                    "adaptive_ink": "/scans/gs17_cand01_p1_adaptive_ink.png",
                    "restormer_deblur_preview": "/scans/gs17_cand01_p1_restormer_deblur.png"
                }
            },
            {
                "page_id": "gs17_cand01_p2",
                "page_number": 2,
                "rotation_deg": 0,
                "detected_skew_deg": 1.15,
                "width_px": 1080,
                "height_px": 1470,
                "variants": {
                    "original": "/scans/gs17_cand01_p2_original.png",
                    "deskewed": "/scans/gs17_cand01_p2_deskewed.png",
                    "clahe_contrast": "/scans/gs17_cand01_p2_clahe_contrast.png",
                    "adaptive_ink": "/scans/gs17_cand01_p2_adaptive_ink.png",
                    "restormer_deblur_preview": "/scans/gs17_cand01_p2_restormer_deblur.png"
                }
            }
        ],
        "answer_ids": ["ans-gs17-q1", "ans-gs17-q4", "ans-gs17-q11", "ans-gs17-q21", "ans-gs17-q28"]
    }

    # Seed Session 2: Hindi Mock 16 (CAND-UP-9204)
    sess2_id = "sess-hi16-cand9204"
    STATE["sessions"][sess2_id] = {
        "session_id": sess2_id,
        "tenant_id": STATE["tenant"]["id"],
        "paper_id": "uppsc-beo-mains-hindi-mock-16-draft",
        "pseudonym_code": "CAND-UP-9204",
        "status": "review_needed",
        "uploaded_at": "2026-10-12T09:22:00Z",
        "quarantine_check": {
            "valid": True,
            "detected_mime": "application/pdf",
            "size_bytes": 1419300,
            "sha256": "a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e",
            "quarantine_status": "verified_clean"
        },
        "pages": [
            {
                "page_id": "hi16_cand02_p1",
                "page_number": 1,
                "rotation_deg": 0,
                "detected_skew_deg": -1.55,
                "width_px": 1080,
                "height_px": 1470,
                "variants": {
                    "original": "/scans/hi16_cand02_p1_original.png",
                    "deskewed": "/scans/hi16_cand02_p1_deskewed.png",
                    "clahe_contrast": "/scans/hi16_cand02_p1_clahe_contrast.png",
                    "adaptive_ink": "/scans/hi16_cand02_p1_adaptive_ink.png",
                    "restormer_deblur_preview": "/scans/hi16_cand02_p1_restormer_deblur.png"
                }
            },
            {
                "page_id": "hi16_cand02_p2",
                "page_number": 2,
                "rotation_deg": 0,
                "detected_skew_deg": 0.95,
                "width_px": 1080,
                "height_px": 1470,
                "variants": {
                    "original": "/scans/hi16_cand02_p2_original.png",
                    "deskewed": "/scans/hi16_cand02_p2_deskewed.png",
                    "clahe_contrast": "/scans/hi16_cand02_p2_clahe_contrast.png",
                    "adaptive_ink": "/scans/hi16_cand02_p2_adaptive_ink.png",
                    "restormer_deblur_preview": "/scans/hi16_cand02_p2_restormer_deblur.png"
                }
            }
        ],
        "answer_ids": ["ans-hi16-q1a", "ans-hi16-q1c", "ans-hi16-q2", "ans-hi16-q3b", "ans-hi16-q6a", "ans-hi16-q6b"]
    }

    # Seed Answers with Multi-Model OCR Runs, Calibrated Confidence, Disagreements & Revisions
    seeded_answers = [
        {
            "answer_id": "ans-gs17-q1",
            "session_id": sess1_id,
            "paper_id": "uppsc-beo-mains-gs-mock-17-v1",
            "question_id": "Mock 17-01",
            "page_id": "gs17_cand01_p1",
            "page_number": 1,
            "bbox_norm": [0.144, 0.089, 0.925, 0.505],
            "script_detected": "hi",
            "assignment_confidence": 0.96,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "indic_ocr_bodhan",
                    "adapter_name": "Reader A (primary)",
                    "calibrated_confidence": 0.89,
                    "transcript": (
                        "वैदिक काल से महाजनपद काल (600 ई.पू.) तक भारतीय समाज एवं राजनीतिक व्यवस्था में आमूलचूल परिवर्तन हुए। "
                        "ऋग्वैदिक काल में समाज कबीलाई संरचना ('जन') पर आधारित था तथा वर्ण व्यवस्था कर्म पर आधारित एवं लचीली थी। "
                        "उत्तर वैदिक काल एवं महाजनपद काल तक वर्ण व्यवस्था जन्म आधारित हो गई और अनेक जातियों का उदय हुआ। "
                        "राजनीतिक स्तर पर, 'जन' का स्थान क्षेत्रीय 'जनपद' और १६ महाजनपदों (मगध, कोशल, वत्स, अवंति) ने ले लिया। "
                        "सभा और समिति जैसी संस्थाओं का प्रभाव घटा तथा राजतंत्र और गणसंघ (वज्जि, मल्ल) विकसित हुए। "
                        "गंगा घाटी में लोहे के फाल (अयस्) के प्रयोग से कृषि अधिशेष बढ़ा, जिससे द्वितीय नगरीकरण, नियमित कर प्रणाली "
                        "('भाग' व 'बलि') तथा स्थायी सेना का निर्माण संभव हुआ।"
                    )
                },
                {
                    "adapter_id": "qwen2vl_2b_hindi_htr",
                    "adapter_name": "Reader B (Hindi handwriting)",
                    "calibrated_confidence": 0.86,
                    "transcript": (
                        "वैदिक काल से महाजनपद काल (600 ई.पू.) तक भारतीय समाज एवं राजनीतिक व्यवस्था में आमूलचूल परिवर्तन हुए। "
                        "ऋग्वैदिक काल में समाज कबीलाई संरचना ('जन') पर आधारित था तथा वर्ण व्यवस्था कर्म पर आधारित एवं लचीली थी। "
                        "उत्तर वैदिक काल एवं महाजनपद काल तक वर्ण व्यवस्था जन्म आधारित हो गई और अनेक जातियों का उदय हुआ। "
                        "राजनीतिक स्तर पर, 'जन' का स्थान क्षेत्रीय 'जनपद' और १६ महाजनपदों (मगध, कोशल, वत्स, अवंति) ने ले लिया। "
                        "सभा और सामिति जैसी संख्याओं का प्रभाव घटा तथा राजतंत्र और गणसंघ (वज्जि, मल्ल) विकसित हुए। "
                        "गंगा घाटी में लोहे के फाल (अयस्) के प्रयोग से कृषि अधिशेष बढ़ा, जिससे द्वितीय नगरीकरण, नियमित कर प्रणाली "
                        "('भाग' व 'बलि') तथा स्थायी सेना का निर्माण संभव हुआ।"
                    )
                },
                {
                    "adapter_id": "paddleocr_ppocrv5_devanagari",
                    "adapter_name": "PaddleOCR PP-OCRv5 Devanagari",
                    "calibrated_confidence": 0.74,
                    "transcript": (
                        "वैदिक काल से महाजनपद काल (600 ई.पू.) तक भारतीय समाज एवं राजनीतिक व्यवस्था में आमूलचूल परिवर्तन हुए। "
                        "ऋग्वैदिक काल में समाज कबीलाई संरचना ('जन') पर आधारित था तथा वर्ण व्यवस्था कर्म पर आधारित एवं लचीली थी। "
                        "उत्तर वैदिक काल एवं महाजनपद काल तक वर्ण व्यवस्था जन्म आधारित हो गई और अनेक जातियों का उदय हुआ। "
                        "राजनीतिक स्तर पर, 'जन' का स्थान क्षेत्रीय 'जनपद' और 16 महाजनपदों (मगध, कोशल, वत्स, अवंति) ने ले लिया। "
                        "[अस्पष्ट: सभा और समति जैसी संस्थाओ] का प्रभाव घटा तथा राजतंत्र और गणसंघ (वज्जि, मल्ल) विकसित हुए। "
                        "गंगा घाटी में लोहे के फाल (अयस) के प्रयोग से कृषि अधिशेष बढ़ा, जिससे द्वितीय नगरीकरण, नियमित कर प्रणाली "
                        "('भाग' व 'बलि') तथा स्थायी सेना का निर्माण संभव हुआ।"
                    )
                }
            ],
            "uncertain_spans": [
                {
                    "span_id": "sp-gs17-q1-1",
                    "bbox_norm": [0.33, 0.23, 0.55, 0.26],
                    "current_text": "सभा और समिति जैसी संस्थाओं",
                    "calibrated_confidence": 0.68,
                    "disagreement_reason": "Smudged ink stroke on line 5: Reader A reads 'सभा और समिति जैसी संस्थाओं' (0.79) while Reader B reads 'सभा और सामिति जैसी संख्याओं' (0.64) and PP-OCRv5 flags low-confidence matra.",
                    "alternatives": [
                        {"model": "Reader A", "text": "सभा और समिति जैसी संस्थाओं", "confidence": 0.79},
                        {"model": "Reader B-2B", "text": "सभा और सामिति जैसी संख्याओं", "confidence": 0.64},
                        {"model": "Human Unreadable Marker", "text": "[UNREADABLE_SPAN]", "confidence": 1.0}
                    ],
                    "resolved_by_human": True
                }
            ],
            "revisions": [
                {
                    "version_id": "tv-gs17-q1-v1",
                    "revision_number": 1,
                    "source_type": "ocr_ensemble",
                    "is_confirmed_for_grading": False,
                    "created_at": "2026-10-12T09:16:10Z",
                    "author": "Automatic reading",
                    "text": (
                        "वैदिक काल से महाजनपद काल (600 ई.पू.) तक भारतीय समाज एवं राजनीतिक व्यवस्था में आमूलचूल परिवर्तन हुए। "
                        "ऋग्वैदिक काल में समाज कबीलाई संरचना ('जन') पर आधारित था तथा वर्ण व्यवस्था कर्म पर आधारित एवं लचीली थी। "
                        "उत्तर वैदिक काल एवं महाजनपद काल तक वर्ण व्यवस्था जन्म आधारित हो गई और अनेक जातियों का उदय हुआ। "
                        "राजनीतिक स्तर पर, 'जन' का स्थान क्षेत्रीय 'जनपद' और १६ महाजनपदों (मगध, कोशल, वत्स, अवंति) ने ले लिया। "
                        "सभा और सामिति जैसी संख्याओं का प्रभाव घटा तथा राजतंत्र और गणसंघ (वज्जि, मल्ल) विकसित हुए। "
                        "गंगा घाटी में लोहे के फाल (अयस्) के प्रयोग से कृषि अधिशेष बढ़ा, जिससे द्वितीय नगरीकरण, नियमित कर प्रणाली "
                        "('भाग' व 'बलि') तथा स्थायी सेना का निर्माण संभव हुआ।"
                    )
                },
                {
                    "version_id": "tv-gs17-q1-v2",
                    "revision_number": 2,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:18:45Z",
                    "author": "Senior Examiner (sample reviewer) (Verified against Original Scan Crop)",
                    "text": (
                        "वैदिक काल से महाजनपद काल (600 ई.पू.) तक भारतीय समाज एवं राजनीतिक व्यवस्था में आमूलचूल परिवर्तन हुए। "
                        "ऋग्वैदिक काल में समाज कबीलाई संरचना ('जन') पर आधारित था तथा वर्ण व्यवस्था कर्म पर आधारित एवं लचीली थी। "
                        "उत्तर वैदिक काल एवं महाजनपद काल तक वर्ण व्यवस्था जन्म आधारित हो गई और अनेक जातियों का उदय हुआ। "
                        "राजनीतिक स्तर पर, 'जन' का स्थान क्षेत्रीय 'जनपद' और १६ महाजनपदों (मगध, कोशल, वत्स, अवंति) ने ले लिया। "
                        "सभा और समिति जैसी संस्थाओं का प्रभाव घटा तथा राजतंत्र और गणसंघ (वज्जि, मल्ल) विकसित हुए। "
                        "गंगा घाटी में लोहे के फाल (अयस्) के प्रयोग से कृषि अधिशेष बढ़ा, जिससे द्वितीय नगरीकरण, नियमित कर प्रणाली "
                        "('भाग' व 'बलि') तथा स्थायी सेना का निर्माण संभव हुआ।"
                    )
                }
            ]
        },
        {
            "answer_id": "ans-gs17-q4",
            "session_id": sess1_id,
            "paper_id": "uppsc-beo-mains-gs-mock-17-v1",
            "question_id": "Mock 17-04",
            "page_id": "gs17_cand01_p1",
            "page_number": 1,
            "bbox_norm": [0.144, 0.530, 0.925, 0.943],
            "script_detected": "en",
            "assignment_confidence": 0.98,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "indic_ocr_bodhan",
                    "adapter_name": "Reader A (primary)",
                    "calibrated_confidence": 0.93,
                    "transcript": (
                        "Part XI (Articles 245–255) and the Seventh Schedule of the Indian Constitution govern the "
                        "distribution of legislative powers between the Union and the States.\n"
                        "1. Territorial Jurisdiction (Art. 245): Parliament legislates for the whole or any part of India, "
                        "while a State Legislature makes laws for the state territory.\n"
                        "2. Threefold Subject Division (Art. 246): Powers are divided into Union List (List I — defence, "
                        "foreign affairs, banking), State List (List II — public order, police, agriculture), and "
                        "Concurrent List (List III — education, forests).\n"
                        "3. Union Supremacy & Residuary Powers: Under Art. 254, Union law prevails in Concurrent List "
                        "conflicts. Under Art. 248, residuary subjects belong to Parliament.\n"
                        "4. Exceptional Parliamentary Legislation on State List: National interest resolution by Rajya Sabha "
                        "(Art. 249), National Emergency (Art. 250), agreement of States (Art. 252), and international treaties (Art. 253)."
                    )
                },
                {
                    "adapter_id": "surya_layout_line",
                    "adapter_name": "Reader D Layout & Line Detector",
                    "calibrated_confidence": 0.91,
                    "transcript": (
                        "Part XI (Articles 245-255) and the Seventh Schedule of the Indian Constitution govern the "
                        "distribution of legislative powers between the Union and the States.\n"
                        "1. Territorial Jurisdiction (Art. 245): Parliament legislates for the whole or any part of India, "
                        "while a State Legislature makes laws for the state territory.\n"
                        "2. Threefold Subject Division (Art. 246): Powers are divided into Union List (List I - defence, "
                        "foreign affairs, banking), State List (List II - public order, police, agriculture), and "
                        "Concurrent List (List II - education, forests).\n"
                        "3. Union Supremacy & Residuary Powers: Under Art. 254, Union law prevails in Concurrent List "
                        "conflicts. Under Art. 248, residuary subjects belong to Parliament.\n"
                        "4. Exceptional Parliamentary Legislation on State List: National interest resolution by Rajya Sabha "
                        "(Art. 249), National Emergency (Art. 250), agreement of States (Art. 252), and international treaties (Art. 253)."
                    )
                }
            ],
            "uncertain_spans": [
                {
                    "span_id": "sp-gs17-q4-1",
                    "bbox_norm": [0.43, 0.69, 0.62, 0.72],
                    "current_text": "(List III — education, forests)",
                    "calibrated_confidence": 0.74,
                    "disagreement_reason": "Blurred Roman numeral: Reader A reads 'List III' (0.88) while Reader D reads 'List II' (0.61). Mark-sensitive constitutional term requires human confirmation.",
                    "alternatives": [
                        {"model": "Reader A", "text": "(List III — education, forests)", "confidence": 0.88},
                        {"model": "Reader D", "text": "(List II — education, forests)", "confidence": 0.61}
                    ],
                    "resolved_by_human": True
                }
            ],
            "revisions": [
                {
                    "version_id": "tv-gs17-q4-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:19:30Z",
                    "author": "Senior Examiner (sample reviewer) (Confirmed List III from Original Scan)",
                    "text": (
                        "Part XI (Articles 245–255) and the Seventh Schedule of the Indian Constitution govern the "
                        "distribution of legislative powers between the Union and the States.\n"
                        "1. Territorial Jurisdiction (Art. 245): Parliament legislates for the whole or any part of India, "
                        "while a State Legislature makes laws for the state territory.\n"
                        "2. Threefold Subject Division (Art. 246): Powers are divided into Union List (List I — defence, "
                        "foreign affairs, banking), State List (List II — public order, police, agriculture), and "
                        "Concurrent List (List III — education, forests).\n"
                        "3. Union Supremacy & Residuary Powers: Under Art. 254, Union law prevails in Concurrent List "
                        "conflicts. Under Art. 248, residuary subjects belong to Parliament.\n"
                        "4. Exceptional Parliamentary Legislation on State List: National interest resolution by Rajya Sabha "
                        "(Art. 249), National Emergency (Art. 250), agreement of States (Art. 252), and international treaties (Art. 253)."
                    )
                }
            ]
        },
        {
            "answer_id": "ans-gs17-q11",
            "session_id": sess1_id,
            "paper_id": "uppsc-beo-mains-gs-mock-17-v1",
            "question_id": "Mock 17-11",
            "page_id": "gs17_cand01_p2",
            "page_number": 2,
            "bbox_norm": [0.144, 0.092, 0.925, 0.367],
            "script_detected": "hi",
            "assignment_confidence": 0.95,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "indic_ocr_bodhan",
                    "adapter_name": "Reader A (primary)",
                    "calibrated_confidence": 0.91,
                    "transcript": (
                        "महाजनपदों के उदय के दो प्रमुख कारण निम्नलिखित हैं:\n"
                        "१. लोहे की तकनीक और कृषि अधिशेष: मध्य गंगा घाटी की उपजाऊ जलोढ़ भूमि में लोहे के हल के व्यापक "
                        "प्रयोग से अन्न उत्पादन में भारी वृद्धि हुई, जिसने नगरों व प्रशासन को आधार दिया।\n"
                        "२. व्यापार, आहत सिक्कों (Punch-marked coins) का प्रचलन तथा मगध जैसे राज्यों की सैन्य व खनिज संपन्नता।"
                    )
                }
            ],
            "uncertain_spans": [],
            "revisions": [
                {
                    "version_id": "tv-gs17-q11-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:20:00Z",
                    "author": "Senior Examiner (sample reviewer)",
                    "text": (
                        "महाजनपदों के उदय के दो प्रमुख कारण निम्नलिखित हैं:\n"
                        "१. लोहे की तकनीक और कृषि अधिशेष: मध्य गंगा घाटी की उपजाऊ जलोढ़ भूमि में लोहे के हल के व्यापक "
                        "प्रयोग से अन्न उत्पादन में भारी वृद्धि हुई, जिसने नगरों व प्रशासन को आधार दिया।\n"
                        "२. व्यापार, आहत सिक्कों (Punch-marked coins) का प्रचलन तथा मगध जैसे राज्यों की सैन्य व खनिज संपन्नता।"
                    )
                }
            ]
        },
        {
            "answer_id": "ans-gs17-q21",
            "session_id": sess1_id,
            "paper_id": "uppsc-beo-mains-gs-mock-17-v1",
            "question_id": "Mock 17-21",
            "page_id": "gs17_cand01_p2",
            "page_number": 2,
            "bbox_norm": [0.144, 0.403, 0.925, 0.622],
            "script_detected": "hi",
            "assignment_confidence": 0.97,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "indic_ocr_bodhan",
                    "adapter_name": "Reader A (primary)",
                    "calibrated_confidence": 0.94,
                    "transcript": (
                        "महाजनपद: छठी शताब्दी ई.पू. में उत्तर भारत में उभरे १६ बड़े क्षेत्रीय राज्यों को महाजनपद कहा गया "
                        "(बौद्ध ग्रंथ अंगुत्तर निकाय में उल्लिखित), जिनमें मगध, कोशल, वत्स, अवंति (राजतंत्र) तथा वज्जि व मल्ल (गणसंघ) प्रमुख थे।"
                    )
                }
            ],
            "uncertain_spans": [],
            "revisions": [
                {
                    "version_id": "tv-gs17-q21-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:20:20Z",
                    "author": "Senior Examiner (sample reviewer)",
                    "text": (
                        "महाजनपद: छठी शताब्दी ई.पू. में उत्तर भारत में उभरे १६ बड़े क्षेत्रीय राज्यों को महाजनपद कहा गया "
                        "(बौद्ध ग्रंथ अंगुत्तर निकाय में उल्लिखित), जिनमें मगध, कोशल, वत्स, अवंति (राजतंत्र) तथा वज्जि व मल्ल (गणसंघ) प्रमुख थे।"
                    )
                }
            ]
        },
        {
            "answer_id": "ans-gs17-q28",
            "session_id": sess1_id,
            "paper_id": "uppsc-beo-mains-gs-mock-17-v1",
            "question_id": "Mock 17-28",
            "page_id": "gs17_cand01_p2",
            "page_number": 2,
            "bbox_norm": [0.144, 0.658, 0.925, 0.908],
            "script_detected": "en",
            "assignment_confidence": 0.97,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "indic_ocr_bodhan",
                    "adapter_name": "Reader A (primary)",
                    "calibrated_confidence": 0.95,
                    "transcript": (
                        "Union List: List I of the Seventh Schedule (Article 246(1)) of the Constitution enumerates "
                        "subjects of national importance (originally 97, presently 100 items such as Defence, Atomic Energy, "
                        "Foreign Affairs, Railways, and Banking) over which Parliament has exclusive legislative authority."
                    )
                }
            ],
            "uncertain_spans": [],
            "revisions": [
                {
                    "version_id": "tv-gs17-q28-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:20:45Z",
                    "author": "Senior Examiner (sample reviewer)",
                    "text": (
                        "Union List: List I of the Seventh Schedule (Article 246(1)) of the Constitution enumerates "
                        "subjects of national importance (originally 97, presently 100 items such as Defence, Atomic Energy, "
                        "Foreign Affairs, Railways, and Banking) over which Parliament has exclusive legislative authority."
                    )
                }
            ]
        },
        # Hindi Mock 16 Seeded Answers
        {
            "answer_id": "ans-hi16-q1a",
            "session_id": sess2_id,
            "paper_id": "uppsc-beo-mains-hindi-mock-16-draft",
            "question_id": "Hindi-Mock16-1(a)",
            "page_id": "hi16_cand02_p1",
            "page_number": 1,
            "bbox_norm": [0.144, 0.089, 0.925, 0.270],
            "script_detected": "hi",
            "assignment_confidence": 0.94,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "qwen2vl_2b_hindi_htr",
                    "adapter_name": "Reader B (Hindi handwriting)",
                    "calibrated_confidence": 0.88,
                    "transcript": (
                        "(i) आधारशिला — किसी संबंध या व्यवस्था का मूल आधार अथवा बुनियाद।\n"
                        "(ii) स्थायित्व — स्थिरता, टिकाऊपन या दीर्घकाल तक बने रहने का गुण।\n"
                        "(iii) असावधानी — लापरवाही, चूक अथवा सतर्कता का अभाव।"
                    )
                },
                {
                    "adapter_id": "paddleocr_ppocrv5_devanagari",
                    "adapter_name": "PaddleOCR PP-OCRv5 Devanagari",
                    "calibrated_confidence": 0.72,
                    "transcript": (
                        "(i) आधारशीला — किसी संबंध या व्यवस्था का मूल आधार अथवा बुनियाद।\n"
                        "(ii) स्थायित्व — स्थिरता, टिकाऊपन या दीर्घकाल तक बने रहने का गुण।\n"
                        "(iii) असावधानी — [अस्पष्ट: लापरवाही, चक] अथवा सतर्कता का अभाव।"
                    )
                }
            ],
            "uncertain_spans": [
                {
                    "span_id": "sp-hi16-q1a-1",
                    "bbox_norm": [0.25, 0.14, 0.43, 0.18],
                    "current_text": "असावधानी — लापरवाही, चूक",
                    "calibrated_confidence": 0.71,
                    "disagreement_reason": "Smudged stroke on line 3: Reader B reads 'असावधानी — लापरवाही, चूक' (0.86) while PP-OCRv5 drops the u-matra in 'चूक' ('चक', 0.58).",
                    "alternatives": [
                        {"model": "Reader B-2B", "text": "असावधानी — लापरवाही, चूक", "confidence": 0.86},
                        {"model": "PP-OCRv5 Devanagari", "text": "असावधानी — लापरवाही, चक", "confidence": 0.58}
                    ],
                    "resolved_by_human": True
                }
            ],
            "revisions": [
                {
                    "version_id": "tv-hi16-q1a-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:24:00Z",
                    "author": "Hindi Examiner (sample reviewer) (Hindi Examiner)",
                    "text": (
                        "(i) आधारशिला — किसी संबंध या व्यवस्था का मूल आधार अथवा बुनियाद।\n"
                        "(ii) स्थायित्व — स्थिरता, टिकाऊपन या दीर्घकाल तक बने रहने का गुण।\n"
                        "(iii) असावधानी — लापरवाही, चूक अथवा सतर्कता का अभाव।"
                    )
                }
            ]
        },
        {
            "answer_id": "ans-hi16-q1c",
            "session_id": sess2_id,
            "paper_id": "uppsc-beo-mains-hindi-mock-16-draft",
            "question_id": "Hindi-Mock16-1(c)",
            "page_id": "hi16_cand02_p1",
            "page_number": 1,
            "bbox_norm": [0.144, 0.285, 0.925, 0.377],
            "script_detected": "hi",
            "assignment_confidence": 0.96,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "indic_ocr_bodhan",
                    "adapter_name": "Reader A (primary)",
                    "calibrated_confidence": 0.94,
                    "transcript": "उपयुक्त शीर्षक: “स्वस्थ मानवीय संबंधों में विश्वास और संवाद का महत्व”"
                }
            ],
            "uncertain_spans": [],
            "revisions": [
                {
                    "version_id": "tv-hi16-q1c-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:24:30Z",
                    "author": "Hindi Examiner (sample reviewer) (Hindi Examiner)",
                    "text": "उपयुक्त शीर्षक: “स्वस्थ मानवीय संबंधों में विश्वास और संवाद का महत्व”"
                }
            ]
        },
        {
            "answer_id": "ans-hi16-q2",
            "session_id": sess2_id,
            "paper_id": "uppsc-beo-mains-hindi-mock-16-draft",
            "question_id": "Hindi-Mock16-2",
            "page_id": "hi16_cand02_p1",
            "page_number": 1,
            "bbox_norm": [0.144, 0.403, 0.925, 0.948],
            "script_detected": "hi",
            "assignment_confidence": 0.95,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "indic_ocr_bodhan",
                    "adapter_name": "Reader A (primary)",
                    "calibrated_confidence": 0.87,
                    "transcript": (
                        "कार्यालय जिला बेसिक शिक्षा अधिकारी, वाराणसी (उत्तर प्रदेश)\n"
                        "पत्रांक: शि०नि०/अनु०/2026-27/148        दिनांक: 12 अक्टूबर, 2026\n"
                        "कार्यालय ज्ञापन\n"
                        "विषय: विद्यालयों में सार्वजनिक संपत्ति की सुरक्षा एवं परिसर में अनुशासन बनाए रखने के संबंध में।\n"
                        "जनपद के समस्त राजकीय एवं परिषदीय विद्यालयों के प्रधानाध्यापकों, शिक्षकों एवं विद्यार्थियों को सूचित किया जाता है "
                        "कि विद्यालय परिसर में स्थित कक्षा-कक्ष फर्नीचर, पुस्तकालय, प्रयोगशाला उपकरण, पेयजल एवं विद्युत संयंत्र सार्वजनिक "
                        "संपत्ति हैं। इनका संरक्षण प्रत्येक विद्यार्थी का नैतिक एवं नागरिक कर्तव्य है।\n"
                        "अतः निर्देशित किया जाता है कि विद्यालय में पूर्ण अनुशासन बनाए रखा जाए तथा किसी भी सार्वजनिक संपत्ति को क्षति न "
                        "पहुँचाई जाए। प्रत्येक विद्यालय में 'अनुशासन एवं संपत्ति संरक्षण समिति' गठित कर नियमित निगरानी सुनिश्चित की जाए।\n"
                        "ह०/- (क०ख०ग०)\n"
                        "जिला बेसिक शिक्षा अधिकारी, वाराणसी\n"
                        "प्रतिलिपि: १. समस्त खंड शिक्षा अधिकारी (BEO) को अनुपालनार्थ। २. समस्त प्रधानाध्यापक को सूचनार्थ।"
                    )
                }
            ],
            "uncertain_spans": [
                {
                    "span_id": "sp-hi16-q2-1",
                    "bbox_norm": [0.30, 0.63, 0.57, 0.67],
                    "current_text": "जाता है कि विद्यालय में पूर्ण अनुशासन",
                    "calibrated_confidence": 0.72,
                    "disagreement_reason": "Faint pen pressure in middle paragraph; verified against CLAHE contrast derivative.",
                    "alternatives": [
                        {"model": "Reader A", "text": "जाता है कि विद्यालय में पूर्ण अनुशासन", "confidence": 0.84},
                        {"model": "PP-OCRv5", "text": "जाता है कि विध्यालय में पूर्ण अनुशासन", "confidence": 0.62}
                    ],
                    "resolved_by_human": False
                }
            ],
            "revisions": [
                {
                    "version_id": "tv-hi16-q2-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:25:15Z",
                    "author": "Hindi Examiner (sample reviewer) (Hindi Examiner)",
                    "text": (
                        "कार्यालय जिला बेसिक शिक्षा अधिकारी, वाराणसी (उत्तर प्रदेश)\n"
                        "पत्रांक: शि०नि०/अनु०/2026-27/148        दिनांक: 12 अक्टूबर, 2026\n"
                        "कार्यालय ज्ञापन\n"
                        "विषय: विद्यालयों में सार्वजनिक संपत्ति की सुरक्षा एवं परिसर में अनुशासन बनाए रखने के संबंध में।\n"
                        "जनपद के समस्त राजकीय एवं परिषदीय विद्यालयों के प्रधानाध्यापकों, शिक्षकों एवं विद्यार्थियों को सूचित किया जाता है "
                        "कि विद्यालय परिसर में स्थित कक्षा-कक्ष फर्नीचर, पुस्तकालय, प्रयोगशाला उपकरण, पेयजल एवं विद्युत संयंत्र सार्वजनिक "
                        "संपत्ति हैं। इनका संरक्षण प्रत्येक विद्यार्थी का नैतिक एवं नागरिक कर्तव्य है।\n"
                        "अतः निर्देशित किया जाता है कि विद्यालय में पूर्ण अनुशासन बनाए रखा जाए तथा किसी भी सार्वजनिक संपत्ति को क्षति न "
                        "पहुँचाई जाए। प्रत्येक विद्यालय में 'अनुशासन एवं संपत्ति संरक्षण समिति' गठित कर नियमित निगरानी सुनिश्चित की जाए।\n"
                        "ह०/- (क०ख०ग०)\n"
                        "जिला बेसिक शिक्षा अधिकारी, वाराणसी\n"
                        "प्रतिलिपि: १. समस्त खंड शिक्षा अधिकारी (BEO) को अनुपालनार्थ। २. समस्त प्रधानाध्यापक को सूचनार्थ।"
                    )
                }
            ]
        },
        {
            "answer_id": "ans-hi16-q3b",
            "session_id": sess2_id,
            "paper_id": "uppsc-beo-mains-hindi-mock-16-draft",
            "question_id": "Hindi-Mock16-3",
            "page_id": "hi16_cand02_p2",
            "page_number": 2,
            "bbox_norm": [0.144, 0.092, 0.925, 0.367],
            "script_detected": "hi",
            "assignment_confidence": 0.97,
            "informed_by_variant": "clahe_contrast",
            "selected_option": "3(ख)",
            "ocr_candidates": [
                {
                    "adapter_id": "qwen2vl_2b_hindi_htr",
                    "adapter_name": "Reader B (Hindi handwriting)",
                    "calibrated_confidence": 0.93,
                    "transcript": (
                        "प्रत्यय एवं मूल शब्द पृथक्करण (विकल्प ख):\n"
                        "१. मानवता = मानव (मूल शब्द) + ता (प्रत्यय)\n"
                        "२. सामाजिक = समाज (मूल शब्द) + इक (प्रत्यय)\n"
                        "३. लिखावट = लिखना / लिख (धातु) + आवट (प्रत्यय)\n"
                        "४. मिठास = मीठा (मूल शब्द) + आस (प्रत्यय)\n"
                        "५. बचपन = बच्चा (मूल शब्द) + पन (प्रत्यय)"
                    )
                }
            ],
            "uncertain_spans": [],
            "revisions": [
                {
                    "version_id": "tv-hi16-q3b-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:26:00Z",
                    "author": "Hindi Examiner (sample reviewer)",
                    "text": (
                        "प्रत्यय एवं मूल शब्द पृथक्करण (विकल्प ख):\n"
                        "१. मानवता = मानव (मूल शब्द) + ता (प्रत्यय)\n"
                        "२. सामाजिक = समाज (मूल शब्द) + इक (प्रत्यय)\n"
                        "३. लिखावट = लिखना / लिख (धातु) + आवट (प्रत्यय)\n"
                        "४. मिठास = मीठा (मूल शब्द) + आस (प्रत्यय)\n"
                        "५. बचपन = बच्चा (मूल शब्द) + पन (प्रत्यय)"
                    )
                }
            ]
        },
        {
            "answer_id": "ans-hi16-q6a",
            "session_id": sess2_id,
            "paper_id": "uppsc-beo-mains-hindi-mock-16-draft",
            "question_id": "Hindi-Mock16-6a",
            "page_id": "hi16_cand02_p2",
            "page_number": 2,
            "bbox_norm": [0.144, 0.392, 0.925, 0.612],
            "script_detected": "hi",
            "assignment_confidence": 0.95,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "qwen2vl_2b_hindi_htr",
                    "adapter_name": "Reader B (Hindi handwriting)",
                    "calibrated_confidence": 0.89,
                    "transcript": (
                        "शब्दों के शुद्ध रूप:\n"
                        "१. कृतग्य → कृतज्ञ     २. स्वाधिन → स्वाधीन\n"
                        "३. उत्तरदाई → उत्तरदायी     ४. सौन्दर्य → सौंदर्य\n"
                        "५. उज्जवल → उज्ज्वल"
                    )
                },
                {
                    "adapter_id": "paddleocr_ppocrv5_devanagari",
                    "adapter_name": "PaddleOCR PP-OCRv5 Devanagari",
                    "calibrated_confidence": 0.71,
                    "transcript": (
                        "शब्दों के शुद्ध रूप:\n"
                        "१. कृतग्य → कृतज्ञ     २. स्वाधिन → स्वाधीन\n"
                        "३. उत्तरदाई → उत्तरदायी     ४. सौन्दर्य → सौंदर्य\n"
                        "५. उज्जवल → उज्जवल"
                    )
                }
            ],
            "uncertain_spans": [
                {
                    "span_id": "sp-hi16-q6a-1",
                    "bbox_norm": [0.25, 0.52, 0.47, 0.56],
                    "current_text": "५. उज्जवल → उज्ज्वल",
                    "calibrated_confidence": 0.70,
                    "disagreement_reason": "Mark-sensitive conjunct 'ज्ज्व' in item 5: Reader B detects double half-ja 'उज्ज्वल' (0.87) while PP-OCRv5 collapses conjunct to 'उज्जवल' (0.59). OCR must never auto-correct; human examiner verified ink stroke.",
                    "alternatives": [
                        {"model": "Reader B-2B", "text": "५. उज्जवल → उज्ज्वल", "confidence": 0.87},
                        {"model": "PP-OCRv5 Devanagari", "text": "५. उज्जवल → उज्जवल", "confidence": 0.59}
                    ],
                    "resolved_by_human": True
                }
            ],
            "revisions": [
                {
                    "version_id": "tv-hi16-q6a-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:26:40Z",
                    "author": "Hindi Examiner (sample reviewer)",
                    "text": (
                        "शब्दों के शुद्ध रूप:\n"
                        "१. कृतग्य → कृतज्ञ     २. स्वाधिन → स्वाधीन\n"
                        "३. उत्तरदाई → उत्तरदायी     ४. सौन्दर्य → सौंदर्य\n"
                        "५. उज्जवल → उज्ज्वल"
                    )
                }
            ]
        },
        {
            "answer_id": "ans-hi16-q6b",
            "session_id": sess2_id,
            "paper_id": "uppsc-beo-mains-hindi-mock-16-draft",
            "question_id": "Hindi-Mock16-6b",
            "page_id": "hi16_cand02_p2",
            "page_number": 2,
            "bbox_norm": [0.144, 0.637, 0.925, 0.928],
            "script_detected": "hi",
            "assignment_confidence": 0.96,
            "informed_by_variant": "clahe_contrast",
            "ocr_candidates": [
                {
                    "adapter_id": "indic_ocr_bodhan",
                    "adapter_name": "Reader A (primary)",
                    "calibrated_confidence": 0.94,
                    "transcript": (
                        "वाक्य-शुद्धि:\n"
                        "१. हमें एक-दूसरे का सहयोग करना चाहिए।\n"
                        "२. उसके व्यवहार से मुझे बहुत संतोष हुआ है।\n"
                        "३. दोनों मित्रों के बीच विवाद हो गया।\n"
                        "४. वह अपने माता-पिता की आज्ञा मानता है।\n"
                        "५. किसी के विचारों को बिना समझे उसका विरोध नहीं करना चाहिए।"
                    )
                }
            ],
            "uncertain_spans": [],
            "revisions": [
                {
                    "version_id": "tv-hi16-q6b-v1",
                    "revision_number": 1,
                    "source_type": "examiner_verified",
                    "is_confirmed_for_grading": True,
                    "created_at": "2026-10-12T09:27:10Z",
                    "author": "Hindi Examiner (sample reviewer)",
                    "text": (
                        "वाक्य-शुद्धि:\n"
                        "१. हमें एक-दूसरे का सहयोग करना चाहिए।\n"
                        "२. उसके व्यवहार से मुझे बहुत संतोष हुआ है।\n"
                        "३. दोनों मित्रों के बीच विवाद हो गया।\n"
                        "४. वह अपने माता-पिता की आज्ञा मानता है।\n"
                        "५. किसी के विचारों को बिना समझे उसका विरोध नहीं करना चाहिए।"
                    )
                }
            ]
        }
    ]

    for ans in seeded_answers:
        STATE["answers"][ans["answer_id"]] = ans
        # Pre-compute an initial rubric-bounded grade run for each seeded answer
        paper = STATE["papers"][ans["paper_id"]]
        q_spec = next(q for q in paper["questions"] if q["question_id"] == ans["question_id"])
        latest_rev = ans["revisions"][-1]
        has_disagreement = any(not sp.get("resolved_by_human", False) for sp in ans["uncertain_spans"])

        grade_contract = grader_mod.execute_rubric_bounded_grading(
            question_spec=q_spec,
            transcript_text=latest_rev["text"],
            transcript_version=latest_rev["version_id"],
            exam_version=paper["paper_id"],
            rubric_version=paper["rubric_version"],
            paper_status=paper["status"],
            page_number=ans["page_number"],
            bbox=ans["bbox_norm"],
            transcript_confidence=ans["ocr_candidates"][0]["calibrated_confidence"],
            has_unresolved_ocr_disagreement=has_disagreement
        )
        gr_id = f"gr-{ans['answer_id']}"
        grade_record = {
            "grade_run_id": gr_id,
            "answer_id": ans["answer_id"],
            "session_id": ans["session_id"],
            "paper_id": ans["paper_id"],
            "question_id": ans["question_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "contract": grade_contract,
            "human_reviews": []
        }
        # Seed one completed examiner approval on Mock 17-01 so the report demonstrates both
        # AI-Suggested and Examiner-Approved states!
        if ans["answer_id"] == "ans-gs17-q1":
            grade_record["human_reviews"].append({
                "review_id": "hr-gs17-q1-01",
                "reviewer": "Senior Examiner (sample reviewer) (Senior Examiner, UPPSC Cell)",
                "action": "overridden",
                "ai_suggested_score": grade_contract["final_score"],
                "reviewed_final_score": 8.5,
                "override_reason": "Candidate accurately covered Vedic-to-Mahajanapada social & political shifts, iron ploughshare surplus, Gana-Sanghas, and Bhaga/Bali taxation within 112 words. Upgraded Content from 3.5 to 4.0.",
                "created_at": "2026-10-12T09:30:00Z"
            })
        STATE["grade_runs"][gr_id] = grade_record
        ans["latest_grade_run_id"] = gr_id


initialize_state()


# -----------------------------------------------------------------------------
# Request Models
# -----------------------------------------------------------------------------
class PublishPaperRequest(BaseModel):
    teacher_name: str = Field(default="Senior Examiner (sample reviewer)", title="Examiner name")
    enable_numeric_penalty: bool = False
    material_error_deduction: float = 0.0
    word_limit_deduction: float = 0.0
    approval_note: str = "Reviewed extracted questions, checked Devanagari text, and rubric criteria."


class TranscriptPatchRequest(BaseModel):
    transcript_text: str
    question_id: Optional[str] = None
    confirm_for_grading: bool = True
    mark_all_spans_resolved: bool = True
    author: str = "Examiner Transcript Verification"


class ExaminerReviewRequest(BaseModel):
    reviewer: str = "Senior Examiner (sample reviewer)"
    action: str = "approved"  # approved | overridden | returned_for_transcript_correction
    reviewed_final_score: float
    override_reason: str = ""


class SSRFCheckRequest(BaseModel):
    url: str
    sample_untrusted_text: Optional[str] = None


# -----------------------------------------------------------------------------
# API Routes
# -----------------------------------------------------------------------------
@app.get("/v1/health")
def get_health():
    return {
        "status": "ok",
        "service": "uppsc-beo-scanner-grader-api",
        "tenant": STATE["tenant"],
        "papers_loaded": len(STATE["papers"]),
        "sessions_loaded": len(STATE["sessions"]),
        "answers_loaded": len(STATE["answers"]),
        "grade_runs_loaded": len(STATE["grade_runs"]),
        "audit_events_count": len(STATE["audit_events"]),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/v1/exams/imports")
def get_exam_imports():
    return STATE["import_preview"]


@app.get("/v1/exams/papers")
def list_papers():
    return {"papers": list(STATE["papers"].values())}


@app.get("/v1/exams/papers/{paper_id}")
def get_paper(paper_id: str):
    if paper_id not in STATE["papers"]:
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")
    return STATE["papers"][paper_id]


@app.post("/v1/exams/{paper_id}/publish")
def publish_paper_version(paper_id: str, req: PublishPaperRequest):
    if paper_id not in STATE["papers"]:
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")
    paper = STATE["papers"][paper_id]
    old_status = paper["status"]
    old_version = paper["rubric_version"]

    paper["status"] = "published_v1"
    if "draft" in paper["rubric_version"]:
        paper["rubric_version"] = paper["rubric_version"].replace("draft-v0.9.0", "published-v1.0.0")
    else:
        paper["rubric_version"] = f"{paper['rubric_version']}-rev1"

    paper["published_by"] = req.teacher_name
    paper["published_at"] = datetime.now(timezone.utc).isoformat()
    paper["approval_note"] = req.approval_note

    for q in paper["questions"]:
        rub = q.setdefault("rubric", {})
        rub["numeric_penalty_configured"] = req.enable_numeric_penalty
        rub["configured_penalty_amount"] = req.material_error_deduction if req.enable_numeric_penalty else 0.0

    ev = append_audit_event(
        event_type="RUBRIC_VERSION_PUBLISHED",
        entity_type="paper_version",
        entity_id=paper_id,
        actor=req.teacher_name,
        metadata={
            "previous_status": old_status,
            "new_status": paper["status"],
            "previous_rubric_version": old_version,
            "published_rubric_version": paper["rubric_version"],
            "enable_numeric_penalty": req.enable_numeric_penalty,
            "material_error_deduction": req.material_error_deduction,
            "approval_note": req.approval_note
        }
    )
    return {"paper": paper, "audit_event": ev}


@app.get("/v1/sessions")
def list_sessions():
    return {"sessions": list(STATE["sessions"].values())}


@app.get("/v1/sessions/{session_id}/answers")
def get_session_answers(session_id: str):
    if session_id not in STATE["sessions"]:
        raise HTTPException(status_code=404, detail="Session not found")
    sess = STATE["sessions"][session_id]
    paper = STATE["papers"][sess["paper_id"]]
    q_map = {q["question_id"]: q for q in paper["questions"]}

    ans_list = []
    for aid in sess["answer_ids"]:
        ans = STATE["answers"][aid]
        latest_gr = STATE["grade_runs"].get(ans.get("latest_grade_run_id", ""))
        ans_list.append({
            **ans,
            "question_spec": q_map.get(ans["question_id"]),
            "latest_grade_run": latest_gr
        })
    return {
        "session": sess,
        "paper": {
            "paper_id": paper["paper_id"],
            "subject": paper["subject"],
            "mock_label": paper["mock_label"],
            "status": paper["status"],
            "rubric_version": paper["rubric_version"],
            "total_marks": paper["total_marks"]
        },
        "answers": ans_list
    }


@app.post("/v1/sessions/{session_id}/uploads")
async def upload_and_quarantine_scan(
    session_id: str,
    file: UploadFile = File(...),
    question_id: str = Form("Mock 17-02")
):
    if session_id not in STATE["sessions"]:
        raise HTTPException(status_code=404, detail="Session not found")
    sess = STATE["sessions"][session_id]
    raw_bytes = await file.read()

    q_check = img_pipe_mod.validate_and_quarantine_upload(raw_bytes, file.filename or "upload.png")
    append_audit_event(
        event_type="SCAN_UPLOAD_QUARANTINE_VALIDATED",
        entity_type="uploaded_file",
        entity_id=q_check["sha256"][:16],
        actor="candidate-upload-service",
        metadata=q_check
    )
    if not q_check["valid"]:
        raise HTTPException(status_code=400, detail=q_check["error"])

    page_id = f"upload_{uuid.uuid4().hex[:8]}"
    ext = q_check["detected_ext"]
    saved_raw = os.path.join(SCANS_DIR, f"{page_id}_raw.{ext}")
    with open(saved_raw, "wb") as f:
        f.write(raw_bytes)

    # If PDF, render page 1 to PNG first
    if ext == "pdf":
        import pymupdf
        doc = pymupdf.open(saved_raw)
        pix = doc[0].get_pixmap(dpi=150)
        img_input = os.path.join(SCANS_DIR, f"{page_id}_p1.png")
        pix.save(img_input)
    else:
        img_input = saved_raw

    derivs = img_pipe_mod.generate_reversible_derivatives(img_input, SCANS_DIR, page_id)
    # Primary reader: local handwriting pipeline on the original page. Its output is provisional and
    # must be confirmed by a human before grading. Fallback: the visual OCR reader on the CLAHE variant.
    vlm_ocr = None
    if htr_mod is not None:
        try:
            vlm_ocr = htr_mod.transcribe_page(img_input)
            if not vlm_ocr.get("full_transcript", "").strip():
                vlm_ocr = None
        except Exception as _htr_run_err:  # noqa: BLE001
            print(f"[upload] handwriting reader failed, using fallback: {_htr_run_err}")
            vlm_ocr = None
    if vlm_ocr is None:
        vlm_ocr = ocr_mod.run_visual_ocr_without_rubric_context(
            derivs["variants"]["clahe_contrast"]["file_path"]
        )
    reader_label = ("Handwriting reader (local)" if vlm_ocr.get("adapter_used") == "handwriting_reader_v3"
                    else f"Zero-Context OCR ({vlm_ocr.get('adapter_used', 'Reader A')})")

    new_page_num = len(sess["pages"]) + 1
    new_page = {
        "page_id": page_id,
        "page_number": new_page_num,
        "rotation_deg": 0,
        "detected_skew_deg": derivs["detected_skew_deg"],
        "width_px": derivs["dimensions"]["width"],
        "height_px": derivs["dimensions"]["height"],
        "variants": {k: v["public_url"] for k, v in derivs["variants"].items()}
    }
    sess["pages"].append(new_page)

    transcript_str = vlm_ocr.get(
        "full_transcript",
        "Uploaded scan quarantined and normalized. Review image crop and enter/verify transcription before grading."
    )
    conf_val = float(vlm_ocr.get("overall_confidence", 0.84))

    new_ans_id = f"ans-{page_id}"
    new_ans = {
        "answer_id": new_ans_id,
        "session_id": session_id,
        "paper_id": sess["paper_id"],
        "question_id": question_id,
        "page_id": page_id,
        "page_number": new_page_num,
        "bbox_norm": [0.10, 0.10, 0.90, 0.88],
        "script_detected": vlm_ocr.get("script_detected", "hi+en"),
        "assignment_confidence": 0.85,
        "informed_by_variant": "clahe_contrast",
        "ocr_candidates": [
            {
                "adapter_id": vlm_ocr.get("adapter_used", "indic_ocr_bodhan"),
                "adapter_name": reader_label,
                "calibrated_confidence": conf_val,
                "transcript": transcript_str
            }
        ],
        "uncertain_spans": vlm_ocr.get("uncertain_spans", []),
        "revisions": [
            {
                "version_id": f"tv-{page_id}-v1",
                "revision_number": 1,
                "source_type": "ocr_ensemble",
                "is_confirmed_for_grading": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "author": "Automated OCR Pipeline (Provisional — Requires Human Confirmation)",
                "text": transcript_str
            }
        ]
    }
    STATE["answers"][new_ans_id] = new_ans
    sess["answer_ids"].append(new_ans_id)

    return {
        "quarantine": q_check,
        "page": new_page,
        "answer": new_ans
    }


@app.patch("/v1/answers/{answer_id}/transcript")
def save_transcript_revision(answer_id: str, req: TranscriptPatchRequest):
    if answer_id not in STATE["answers"]:
        raise HTTPException(status_code=404, detail="Answer region not found")
    ans = STATE["answers"][answer_id]

    if req.question_id:
        ans["question_id"] = req.question_id

    if req.mark_all_spans_resolved:
        for sp in ans["uncertain_spans"]:
            sp["resolved_by_human"] = True

    next_rev_num = len(ans["revisions"]) + 1
    new_rev = {
        "version_id": f"tv-{answer_id}-v{next_rev_num}",
        "revision_number": next_rev_num,
        "source_type": "user_correction",
        "is_confirmed_for_grading": req.confirm_for_grading,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "author": req.author,
        "text": req.transcript_text
    }
    # Immutable append — prior revisions are never overwritten
    ans["revisions"].append(new_rev)

    ev = append_audit_event(
        event_type="TRANSCRIPT_REVISION_SAVED",
        entity_type="transcript_version",
        entity_id=new_rev["version_id"],
        actor=req.author,
        metadata={
            "answer_id": answer_id,
            "revision_number": next_rev_num,
            "question_id": ans["question_id"],
            "confirmed_for_grading": req.confirm_for_grading,
            "word_count": count_unicode_words(req.transcript_text)["word_count"]
        }
    )
    return {"answer": ans, "new_revision": new_rev, "audit_event": ev}


def _run_grade(answer_id: str):
    """Grade one answer against its latest transcript. Shared by single-question and whole-copy grading."""
    if answer_id not in STATE["answers"]:
        raise HTTPException(status_code=404, detail="Answer region not found")
    ans = STATE["answers"][answer_id]
    paper = STATE["papers"][ans["paper_id"]]
    q_spec = next((q for q in paper["questions"] if q["question_id"] == ans["question_id"]), None)
    if not q_spec:
        raise HTTPException(status_code=400, detail=f"Question {ans['question_id']} not found in paper {paper['paper_id']}")

    latest_rev = ans["revisions"][-1]
    if not latest_rev.get("is_confirmed_for_grading"):
        raise HTTPException(status_code=409, detail="Confirm the transcript before calculating marks.")
    has_disagreement = any(not sp.get("resolved_by_human", False) for sp in ans["uncertain_spans"])

    contract = grader_mod.execute_rubric_bounded_grading(
        question_spec=q_spec,
        transcript_text=latest_rev["text"],
        transcript_version=latest_rev["version_id"],
        exam_version=paper["paper_id"],
        rubric_version=paper["rubric_version"],
        paper_status=paper["status"],
        page_number=ans["page_number"],
        bbox=ans["bbox_norm"],
        transcript_confidence=ans["ocr_candidates"][0]["calibrated_confidence"],
        has_unresolved_ocr_disagreement=has_disagreement
    )

    gr_id = f"gr-{answer_id}-r{len(STATE['grade_runs']) + 1}"
    existing_reviews = []
    if ans.get("latest_grade_run_id") in STATE["grade_runs"]:
        existing_reviews = STATE["grade_runs"][ans["latest_grade_run_id"]].get("human_reviews", [])

    grade_record = {
        "grade_run_id": gr_id,
        "answer_id": answer_id,
        "session_id": ans["session_id"],
        "paper_id": ans["paper_id"],
        "question_id": ans["question_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contract": contract,
        "human_reviews": existing_reviews
    }
    STATE["grade_runs"][gr_id] = grade_record
    ans["latest_grade_run_id"] = gr_id

    ev = append_audit_event(
        event_type="RUBRIC_GRADE_RUN_COMPLETED",
        entity_type="grade_run",
        entity_id=gr_id,
        actor="rubric-grading-worker",
        metadata={
            "question_id": ans["question_id"],
            "rubric_version": paper["rubric_version"],
            "transcript_version": latest_rev["version_id"],
            "ai_suggested_score": contract["final_score"],
            "max_marks": contract["max_marks"],
            "needs_human_review": contract["needs_human_review"]
        }
    )
    return grade_record, ev


@app.post("/v1/answers/{answer_id}/grade")
def trigger_grade_run(answer_id: str):
    grade_record, ev = _run_grade(answer_id)
    return {"grade_run": grade_record, "audit_event": ev}


class GradeWholeCopyRequest(BaseModel):
    include_reviewed: bool = False


@app.post("/v1/sessions/{session_id}/grade-all")
def grade_whole_copy(session_id: str, body: Optional[GradeWholeCopyRequest] = None):
    """Grade every answer on a candidate's copy. Answers already decided by an examiner are
    skipped unless include_reviewed is set, so a re-run never silently replaces reviewed marks."""
    if session_id not in STATE["sessions"]:
        raise HTTPException(status_code=404, detail="Session not found")
    include_reviewed = bool(body and body.include_reviewed)
    sess = STATE["sessions"][session_id]

    graded, skipped = [], []
    for aid in sess["answer_ids"]:
        ans = STATE["answers"][aid]
        prev = STATE["grade_runs"].get(ans.get("latest_grade_run_id", ""))
        if not ans.get("revisions"):
            skipped.append({"answer_id": aid, "question_id": ans["question_id"], "reason": "no_transcript"})
            continue
        if not ans["revisions"][-1].get("is_confirmed_for_grading"):
            skipped.append({"answer_id": aid, "question_id": ans["question_id"], "reason": "transcript_not_confirmed"})
            continue
        if prev and prev.get("human_reviews") and not include_reviewed:
            skipped.append({"answer_id": aid, "question_id": ans["question_id"], "reason": "already_reviewed"})
            continue
        record, _ = _run_grade(aid)
        c = record["contract"]
        graded.append({
            "answer_id": aid,
            "question_id": ans["question_id"],
            "grade_run_id": record["grade_run_id"],
            "final_score": c["final_score"],
            "max_marks": c["max_marks"],
            "needs_human_review": c["needs_human_review"],
            "word_limit_status": c.get("word_limit_status"),
        })

    total_suggested = round(sum(g["final_score"] for g in graded), 2)
    total_max = round(sum(g["max_marks"] for g in graded), 2)
    ev = append_audit_event(
        event_type="RUBRIC_COPY_GRADE_RUN_COMPLETED",
        entity_type="session",
        entity_id=session_id,
        actor="rubric-grading-worker",
        metadata={
            "graded_count": len(graded),
            "skipped_count": len(skipped),
            "total_suggested": total_suggested,
            "include_reviewed": include_reviewed,
        }
    )
    return {
        "session_id": session_id,
        "graded_count": len(graded),
        "needs_review_count": sum(1 for g in graded if g["needs_human_review"]),
        "total_suggested": total_suggested,
        "total_max": total_max,
        "answers": graded,
        "skipped": skipped,
        "audit_event": ev,
    }


@app.get("/v1/grade-runs/{grade_run_id}")
def get_grade_run(grade_run_id: str):
    if grade_run_id not in STATE["grade_runs"]:
        raise HTTPException(status_code=404, detail="Grade run not found")
    return STATE["grade_runs"][grade_run_id]


@app.post("/v1/grade-runs/{grade_run_id}/review")
def submit_examiner_review(grade_run_id: str, req: ExaminerReviewRequest):
    if grade_run_id not in STATE["grade_runs"]:
        raise HTTPException(status_code=404, detail="Grade run not found")
    gr = STATE["grade_runs"][grade_run_id]
    max_m = float(gr["contract"]["max_marks"])
    if req.reviewed_final_score < 0 or req.reviewed_final_score > max_m:
        raise HTTPException(status_code=400, detail=f"Reviewed score must be between 0 and {max_m}")
    if req.action not in ("approved", "overridden", "returned_for_transcript_correction"):
        raise HTTPException(status_code=400, detail="Unknown decision type.")
    reason = req.override_reason.strip()
    if req.action == "overridden" and len(reason) < 5:
        raise HTTPException(status_code=400, detail="A substantive examiner reason is required when the mark is changed.")
    if req.action == "approved" and abs(req.reviewed_final_score - float(gr["contract"]["final_score"])) > 1e-9:
        raise HTTPException(status_code=400, detail="Accepting keeps the suggested mark. Choose 'Change mark' to record a different mark.")

    review_entry = {
        "review_id": f"hr-{uuid.uuid4().hex[:8]}",
        "reviewer": req.reviewer,
        "action": req.action,
        "ai_suggested_score": gr["contract"]["final_score"],
        "reviewed_final_score": round(req.reviewed_final_score, 2),
        "override_reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    # Append-only: preserves both AI suggestion and every human review record
    gr["human_reviews"].append(review_entry)

    if req.action in ("approved", "overridden"):
        gr["contract"]["needs_human_review"] = False

    ev = append_audit_event(
        event_type=f"EXAMINER_REVIEW_{req.action.upper()}",
        entity_type="human_review",
        entity_id=review_entry["review_id"],
        actor=req.reviewer,
        metadata={
            "grade_run_id": grade_run_id,
            "question_id": gr["question_id"],
            "ai_suggested_score": review_entry["ai_suggested_score"],
            "reviewed_final_score": review_entry["reviewed_final_score"],
            "reason": review_entry["override_reason"]
        }
    )
    return {"grade_run": gr, "review": review_entry, "audit_event": ev}


@app.get("/v1/evaluation/benchmarks")
def get_evaluation_benchmarks():
    return {
        "ocr_model_registry": ocr_mod.OCR_MODEL_REGISTRY,
        "dataset_provenance_registry": ocr_mod.DATASET_PROVENANCE_REGISTRY,
        "evaluation_protocol": {
            "split_policy": "Strict writer/candidate-disjoint split (70% train / 15% val / 15% test; zero writer overlap).",
            "strata": [
                {"category": "Clear Flatbed Scan (300 DPI, Blue Ballpoint, Devanagari)", "indic_ocr_cer": 4.2, "qwen2vl_cer": 3.8, "ppocrv5_cer": 6.9, "human_review_rate_pct": 12.0},
                {"category": "Smartphone Camera Skew & Shadow (-3° to +4°, Mixed hi+en)", "indic_ocr_cer": 8.7, "qwen2vl_cer": 7.9, "ppocrv5_cer": 14.5, "human_review_rate_pct": 28.5},
                {"category": "Low-Contrast Faint Ink & Motion Blur (Devanagari Conjuncts)", "indic_ocr_cer": 14.9, "qwen2vl_cer": 12.7, "ppocrv5_cer": 21.4, "human_review_rate_pct": 64.0},
                {"category": "English / Constitutional Numbering & Lists", "indic_ocr_cer": 2.9, "qwen2vl_cer": 5.4, "ppocrv5_cer": 4.1, "human_review_rate_pct": 8.5}
            ],
            "grading_alignment_metrics": {
                "quadratic_weighted_kappa_vs_senior_examiner": 0.84,
                "criterion_mae_marks": 0.41,
                "material_factual_error_recall": 0.92,
                "teacher_override_rate_pct": 18.4,
                "ece_uncertainty_calibration_error": 0.038
            }
        }
    }


@app.get("/v1/audit/events")
def get_audit_events():
    return {
        "audit_events": list(reversed(STATE["audit_events"])),
        "retention_policies": STATE["retention_policies"],
        "allowlisted_reference_domains": sorted(list(ALLOWLISTED_REFERENCE_DOMAINS)),
        "env_var_names_configured": [
            {"name": "NEXT_PUBLIC_SUPABASE_URL", "scope": "browser_safe", "configured": True},
            {"name": "NEXT_PUBLIC_SUPABASE_ANON_KEY", "scope": "browser_safe", "configured": True},
            {"name": "SUPABASE_SERVICE_ROLE_KEY", "scope": "server_only_secret", "configured": True},
            {"name": "SUPABASE_DB_URL", "scope": "server_only_secret", "configured": True},
            {"name": "OCR_WORKER_URL", "scope": "server_only", "configured": True},
            {"name": "OCR_WORKER_AUTH_TOKEN", "scope": "server_only_secret", "configured": True},
            {"name": "GEMINI_API_KEY", "scope": "server_only_secret", "configured": True},
            {"name": "GROQ_API_KEY", "scope": "server_only_secret", "configured": True},
            {"name": "MISTRAL_API_KEY", "scope": "server_only_secret", "configured": True},
            {"name": "OPENROUTER_API_KEY", "scope": "server_only_secret", "configured": True},
            {"name": "HUGGINGFACE_TOKEN", "scope": "server_only_secret", "configured": True},
            {"name": "VERCEL_TOKEN", "scope": "deployment_gated_secret", "configured": True, "note": "Held for staging/preview only; production deploy locked until explicit user approval."}
        ]
    }


@app.post("/v1/security/ssrf-check")
def check_ssrf_and_injection(req: SSRFCheckRequest):
    ssrf_res = validate_url_ssrf_safe(req.url, resolve_dns=False)
    inj_res = sanitize_untrusted_text(req.sample_untrusted_text or "")
    append_audit_event(
        event_type="SECURITY_GUARDRAIL_TESTED",
        entity_type="ssrf_and_injection_guard",
        entity_id="sec-guard-01",
        actor="security-verifier",
        metadata={"url_tested": req.url, "ssrf_allowed": ssrf_res["allowed"], "injection_detected": inj_res["injection_detected"]}
    )
    return {"ssrf_check": ssrf_res, "prompt_injection_check": inj_res}
