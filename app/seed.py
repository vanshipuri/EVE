"""Seed demo data: 3 centres, 6 tests, priced links. Idempotent."""

from app.db.session import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.models.centre import Centre
from app.models.centre_test import CentreTest
from app.models.diagnostic_test import DiagnosticTest

CENTRES = [
    {"name": "EVE Diagnostics - Koramangala", "location": "Koramangala, Bengaluru", "phone": "080-41120001"},
    {"name": "EVE Diagnostics - Andheri", "location": "Andheri West, Mumbai", "phone": "022-48930002"},
    {"name": "EVE Diagnostics - Sector 62", "location": "Sector 62, Noida", "phone": "0120-4560003"},
]

TESTS = [
    {"name": "Complete Blood Count", "code": "CBC", "description": "Hemoglobin, WBC, platelets & more", "category": "Pathology"},
    {"name": "Lipid Profile", "code": "LIPID", "description": "Cholesterol, triglycerides, HDL/LDL", "category": "Pathology"},
    {"name": "HbA1c (Glycated Hemoglobin)", "code": "HBA1C", "description": "3-month average blood sugar", "category": "Pathology"},
    {"name": "Thyroid Profile (T3/T4/TSH)", "code": "THYROID", "description": "Complete thyroid function panel", "category": "Pathology"},
    {"name": "Chest X-Ray", "code": "XRAY_CHEST", "description": "Digital chest radiograph", "category": "Radiology"},
    {"name": "Abdominal Ultrasound", "code": "USG_ABD", "description": "Whole abdomen ultrasound scan", "category": "Radiology"},
]

PRICES = {
    # centre_index -> {test_code: price}
    0: {"CBC": 299, "LIPID": 799, "HBA1C": 499, "THYROID": 699, "XRAY_CHEST": 450, "USG_ABD": 1200},
    1: {"CBC": 349, "LIPID": 849, "THYROID": 749, "XRAY_CHEST": 500},
    2: {"CBC": 279, "HBA1C": 479, "USG_ABD": 1100, "LIPID": 779},
}


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Centre).count():
            print("Seed: data already present, skipping.")
            return
        centres = []
        for c in CENTRES:
            centre = Centre(**c)
            db.add(centre)
            centres.append(centre)
        db.flush()

        tests_by_code = {}
        for t in TESTS:
            test = DiagnosticTest(**t)
            db.add(test)
            db.flush()
            tests_by_code[t["code"]] = test

        for ci, price_map in PRICES.items():
            for code, price in price_map.items():
                db.add(
                    CentreTest(
                        centre_id=centres[ci].id,
                        test_id=tests_by_code[code].id,
                        price=price,
                        currency="INR",
                        is_available=True,
                    )
                )
        db.commit()
        print(f"Seed: {len(centres)} centres, {len(tests_by_code)} tests created.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
