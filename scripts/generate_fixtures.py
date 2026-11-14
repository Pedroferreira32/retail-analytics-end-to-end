"""Build small, explicitly SYNTHETIC CSVs covering Olist join and delivery edge cases."""

import csv
from pathlib import Path

from retail_analytics.contracts import CONTRACTS


def generate(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    rows = {
        "customers": [
            [
                f"c{i}",
                "u1" if i in (1, 6) else f"u{i}",
                "01000" if i % 2 else "20000",
                "sao paulo" if i % 2 else "rio de janeiro",
                "SP" if i % 2 else "RJ",
            ]
            for i in range(1, 7)
        ],
        "orders": [
            [
                "o1",
                "c1",
                "delivered",
                "2018-01-01 10:00:00",
                "2018-01-01 11:00:00",
                "2018-01-02 12:00:00",
                "2018-01-10 18:00:00",
                "2018-01-10 00:00:00",
            ],
            [
                "o2",
                "c2",
                "delivered",
                "2018-01-02 10:00:00",
                "2018-01-02 11:00:00",
                "2018-01-03 12:00:00",
                "2018-01-11 12:00:00",
                "2018-01-10 00:00:00",
            ],
            ["o3", "c3", "canceled", "2018-01-03 10:00:00", "", "", "", "2018-01-20 00:00:00"],
            [
                "o4",
                "c4",
                "shipped",
                "2018-01-04 10:00:00",
                "2018-01-04 11:00:00",
                "2018-01-05 12:00:00",
                "",
                "2018-01-20 00:00:00",
            ],
            ["o5", "c5", "created", "2018-02-02 10:00:00", "", "", "", "2018-02-20 00:00:00"],
            [
                "o6",
                "c6",
                "delivered",
                "2018-02-01 10:00:00",
                "2018-02-01 11:00:00",
                "2018-02-02 12:00:00",
                "2018-02-03 12:00:00",
                "2018-02-05 00:00:00",
            ],
        ],
        "items": [
            ["o1", 1, "p1", "s1", "2018-01-04 00:00:00", "10.10", "1.00"],
            ["o1", 2, "p2", "s2", "2018-01-04 00:00:00", "20.20", "2.00"],
            ["o2", 1, "p1", "s1", "2018-01-04 00:00:00", "100.00", "10.00"],
            ["o3", 1, "p2", "s2", "2018-01-04 00:00:00", "999.99", "0.00"],
            ["o4", 1, "p1", "s1", "2018-01-06 00:00:00", "50.00", "5.00"],
            ["o6", 1, "p3", "s1", "2018-02-03 00:00:00", "0.01", "0.00"],
        ],
        "payments": [
            ["o1", 1, "credit_card", 1, "20.00"],
            ["o1", 2, "voucher", 1, "13.30"],
            ["o2", 1, "credit_card", 2, "110.00"],
            ["o3", 1, "boleto", 1, "999.99"],
            ["o4", 1, "credit_card", 1, "55.00"],
            ["o6", 1, "voucher", 0, "0.01"],
        ],
        "reviews": [
            ["r1", "o1", 1, "old", "synthetic", "2018-01-10 00:00:00", "2018-01-11 10:00:00"],
            ["r2", "o1", 5, "new", "synthetic", "2018-01-10 00:00:00", "2018-01-12 10:00:00"],
            # Same review ID on a different order is legal in the source.
            ["r2", "o2", 2, "", "", "2018-01-11 00:00:00", "2018-01-12 10:00:00"],
        ],
        "products": [
            ["p1", "beleza_saude", 10, 20, 1, 300, 10, 20, 30],
            ["p2", "casa", 10, 20, 1, 300, 10, 20, 30],
            ["p3", "", "", "", "", "", "", "", ""],
        ],
        "sellers": [["s1", "01000", "sao paulo", "SP"], ["s2", "20000", "rio de janeiro", "RJ"]],
        "translation": [["beleza_saude", "health_beauty"], ["casa", "home"]],
        "geolocation": [
            ["01000", -23.5, -46.6, "sao paulo", "SP"],
            ["01000", -23.6, -46.7, "sao paulo", "SP"],
            ["20000", -22.9, -43.2, "rio de janeiro", "RJ"],
        ],
    }
    for name, contract in CONTRACTS.items():
        with (destination / contract.filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(contract.columns)
            writer.writerows(rows[name])


if __name__ == "__main__":
    generate(Path("tests/fixtures/olist"))
