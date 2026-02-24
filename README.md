# Data Modeling & Analysis

Projects focused on data modeling, statistical analysis, and anomaly detection applied to fraud investigation scenarios. Built with Python (pandas, scipy, scikit-learn), SQL, and Excel.

---

## Projects

### [Timesheet Fraud Detection Lab](./timesheet-fraud-lab/)

End-to-end fraud detection pipeline that generates synthetic timesheet data with 5 injected fraud patterns, applies statistical methods (IQR, Isolation Forest, KMeans) to detect them, and outputs results to an Excel dashboard with live formulas and conditional formatting.

**Stack:** Python, pandas, scipy, scikit-learn, seaborn, openpyxl

![Fraud Analysis](./timesheet-fraud-lab/images/fraud_analysis_chart.png)

---

### [Card Testing Fraud Detection](./card-testing-detection/)

Simulates card testing attacks against a payment processing database, then uses three layers of SQL analytical queries (velocity analysis, rapid-fire detection, BIN pattern analysis) to detect them using CTEs, window functions, and composite scoring.

**Stack:** Python, PostgreSQL, SQL (CTEs, Window Functions, CASE scoring)

---

### [Financial Forensic Audit Lab](./forensic-audit-lab/)

Generates ~15,000 realistic transactions with 5 injected fraud patterns (split purchase, duplicate invoice, ghost vendor, inflated amount, round number) and detects them using Excel formulas, Pivot Tables, and Power Query. Includes an N8N workflow that runs all 5 SQL detections in parallel and feeds results to an AI agent for automated classification and executive summary generation.

**Stack:** Python, scipy, pandas, Excel (Formulas, Pivot Tables, Power Query), PostgreSQL, N8N, Gemma (Ollama)

![Forensic Audit](./forensic-audit-lab/images/forensic_audit_overview.png)
