"""
Builds backend/data/wwi_smoke_test.csv: questions about WideWorldImporters
with a reference (gold) SQL query each. Answers are computed by running the
gold SQL, so they always match the restored database.

    python backend/scripts/build_wwi_smoke_test.py
"""
import os
import sys
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agents.db_utils import connect_to_db  # noqa: E402

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "wwi_smoke_test.csv")

# (difficulty, question, gold SQL)
QUESTIONS = [
    ("easy", "How many customers are there?",
     "SELECT COUNT(*) FROM Sales.Customers"),
    ("easy", "How many stock items are there?",
     "SELECT COUNT(*) FROM Warehouse.StockItems"),
    ("easy", "How many orders were placed in 2015?",
     "SELECT COUNT(*) FROM Sales.Orders WHERE YEAR(OrderDate) = 2015"),
    ("medium", "Which customer category has the most customers?",
     """SELECT TOP 1 cc.CustomerCategoryName
        FROM Sales.Customers AS c
        JOIN Sales.CustomerCategories AS cc ON c.CustomerCategoryID = cc.CustomerCategoryID
        GROUP BY cc.CustomerCategoryName ORDER BY COUNT(*) DESC"""),
    ("medium", "Which supplier supplies the most stock items?",
     """SELECT TOP 1 s.SupplierName
        FROM Warehouse.StockItems AS si
        JOIN Purchasing.Suppliers AS s ON si.SupplierID = s.SupplierID
        GROUP BY s.SupplierName ORDER BY COUNT(*) DESC"""),
    ("medium", "Which salesperson took the most orders?",
     """SELECT TOP 1 p.FullName
        FROM Sales.Orders AS o
        JOIN Application.People AS p ON o.SalespersonPersonID = p.PersonID
        GROUP BY p.FullName ORDER BY COUNT(*) DESC"""),
    ("medium", "How many customers have a delivery address in California?",
     """SELECT COUNT(*)
        FROM Sales.Customers AS c
        JOIN Application.Cities AS ci ON c.DeliveryCityID = ci.CityID
        JOIN Application.StateProvinces AS sp ON ci.StateProvinceID = sp.StateProvinceID
        WHERE sp.StateProvinceName = 'California'"""),
    ("hard", "Which stock item had the highest total quantity ordered?",
     """SELECT TOP 1 si.StockItemName
        FROM Sales.OrderLines AS ol
        JOIN Warehouse.StockItems AS si ON ol.StockItemID = si.StockItemID
        GROUP BY si.StockItemName ORDER BY SUM(ol.Quantity) DESC"""),
    ("hard", "What were total sales excluding tax (invoice line quantity times unit price) "
             "for invoices dated in 2015, rounded to two decimals?",
     """SELECT CAST(ROUND(SUM(il.Quantity * il.UnitPrice), 2) AS decimal(18, 2))
        FROM Sales.InvoiceLines AS il
        JOIN Sales.Invoices AS i ON il.InvoiceID = i.InvoiceID
        WHERE YEAR(i.InvoiceDate) = 2015"""),
    ("hard", "Which sales territory had the most orders in 2016?",
     """SELECT TOP 1 sp.SalesTerritory
        FROM Sales.Orders AS o
        JOIN Sales.Customers AS c ON o.CustomerID = c.CustomerID
        JOIN Application.Cities AS ci ON c.DeliveryCityID = ci.CityID
        JOIN Application.StateProvinces AS sp ON ci.StateProvinceID = sp.StateProvinceID
        WHERE YEAR(o.OrderDate) = 2016
        GROUP BY sp.SalesTerritory ORDER BY COUNT(*) DESC"""),
]


def main():
    load_dotenv()
    engine = connect_to_db()
    rows = []
    with engine.connect() as connection:
        for difficulty, question, sql in QUESTIONS:
            answer = connection.execute(text(sql)).scalar()
            rows.append({"Question": question, "Answer": answer,
                         "Difficulty": difficulty, "SQL": " ".join(sql.split())})
            print(f"[{difficulty}] {question} -> {answer}")
    pd.DataFrame(rows).to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(rows)} questions to {os.path.abspath(OUT_PATH)}")


if __name__ == "__main__":
    main()
