# Excel Fraud Detection — Formula Guide

Reference guide for detecting 5 fraud types in `transactions.csv` using Excel formulas.

**Setup:** Data → Get Data → From Text/CSV → select `transactions.csv` → Load.  
Rename the table to `txn` (Table Design → Table Name).

> The columns `is_fraud`, `fraud_type`, `z_score`, `pair_frequency`, `employee_total_spend`, and `cat_percentile` exist for validation only. In a real investigation you wouldn't have these — every formula below uses only the 7 observable columns.

---

## Column Map

| Column | Letter | Name |
|---|---|---|
| A | A | transaction_id |
| B | B | date |
| C | C | employee_id |
| D | D | vendor_id |
| E | E | amount |
| F | F | category |
| G | G | invoice_number |

Data starts in row 2, last row = 15188. Adjust ranges to your dataset.

---

## 1. Split Purchase Detection

**What:** One employee fragments a large purchase into multiple smaller transactions to avoid the $5,000 approval threshold.

**Signal:** Same employee + vendor + date → individual amounts < $5,000 but combined total > $5,000.

**In this dataset:** EMP-001 has 6 split events, EMP-003/EMP-008 also involved. Fragments range from $800–$3,200 each, but grouped totals reach $5,900–$7,900.

### Helper columns

**H2 — Grouping key** (employee + vendor + date):
```
=C2&"|"&D2&"|"&TEXT(B2,"YYYY-MM-DD")
```

**I2 — Group count** (how many transactions share this key):
```
=COUNTIF(H:H, H2)
```

**J2 — Group total** (combined amount for this key):
```
=SUMIF(H:H, H2, E:E)
```

**K2 — Split flag:**
```
=IF(AND(J2>5000, E2<5000, I2>1), "SPLIT", "")
```

### What this catches

A transaction is flagged when: the employee billed the same vendor multiple times on the same day, each individual amount is under $5,000, but the total exceeds the threshold. For example, EMP-001 billed PROV-004 five times on 2025-01-25 for a total of $6,454 — each fragment under $1,800.

### Alternative: SUMPRODUCT (no helper columns)

To check a single row without creating helper columns:
```
=SUMPRODUCT((C$2:C$15188=C2)*(D$2:D$15188=D2)*(B$2:B$15188=B2)*(E$2:E$15188))
```
This returns the total amount for the same employee+vendor+date. If it's > 5,000 and the current row's amount is < 5,000, it's a split.

---

## 2. Duplicate Invoice Detection

**What:** The same invoice is submitted twice, sometimes with a slightly different amount (±3%) or a few days apart.

**Signal:** Same `invoice_number` appearing more than once.

**In this dataset:** 16 invoice numbers appear exactly twice. EMP-002 and EMP-007 are the two fraudsters. The duplicate typically has an amount within 3% of the original and a date 1–5 days later.

### Helper columns

**L2 — Invoice count:**
```
=COUNTIF(G:G, G2)
```
If > 1, this invoice number is duplicated.

**M2 — Duplicate flag:**
```
=IF(L2>1, "DUPLICATE", "")
```

### Finding near-duplicates (same vendor, similar amount, close date)

For cases where the invoice number was changed but the amounts are suspiciously similar:

**N2 — Near-duplicate count** (same vendor, amount within 3%, date within 5 days, different transaction):
```
=SUMPRODUCT(
    (D$2:D$15188=D2)*
    (ABS(E$2:E$15188-E2)/E2<0.03)*
    (ABS(B$2:B$15188-B2)<=5)*
    (A$2:A$15188<>A2)
)
```
Returns 0 = unique, ≥1 = potential duplicate. Heavy formula — apply to a filtered subset if slow on 15K rows.

### Quick validation

Filter column L for values > 1. You should see 32 rows (16 pairs). Sort by `invoice_number` to see originals next to their duplicates.

---

## 3. Ghost Vendor Detection

**What:** A fake vendor that only bills to one employee. The employee creates a shell company and submits fraudulent invoices through it.

**Signal:** A vendor where 100% of transactions come from a single employee.

**In this dataset:** PROV-071 only bills EMP-008 (15 transactions, avg $3,426). PROV-072 only bills EMP-003 (15 transactions). All other vendors bill multiple employees.

### Approach: Pivot Table (recommended)

1. Insert → PivotTable from `txn`
2. Rows: `vendor_id`
3. Values:
   - Count of `transaction_id`
   - Count of `employee_id` (change to **Distinct Count** — requires Data Model: PivotTable Options → "Add this data to the Data Model")
4. Sort by Distinct Count ascending
5. Vendors with Distinct Count = 1 → ghost vendor candidates

### Approach: Helper columns

**O2 — Vendor+Employee pair key:**
```
=D2&"|"&C2
```

**P2 — First occurrence of this pair:**
```
=IF(COUNTIF(O$2:O2, O2)=1, 1, 0)
```
Marks 1 only the first time each vendor-employee pair appears (running distinct count trick).

**Q2 — Unique employees per vendor:**
```
=SUMIF(D:D, D2, P:P)
```
Total distinct employees for this vendor.

**R2 — Ghost flag:**
```
=IF(Q2=1, "GHOST VENDOR", "")
```

### Additional ghost vendor signals to check manually

Once you identify the ghost vendor, investigate further:

**Average amount** — ghost vendors tend to bill high amounts consistently:
```
=AVERAGEIF(D:D, "PROV-071", E:E)
```
Returns ~$3,426 for PROV-071 (above the dataset average of ~$1,200).

**Transaction count:**
```
=COUNTIF(D:D, "PROV-071")
```
Returns 15. High volume + single employee = strong signal.

---

## 4. Inflated Amount Detection

**What:** Employee systematically submits amounts 40–80% above the category average.

**Signal:** Consistently high z-score within the same category. One or two inflated transactions can be legitimate — a pattern of them across months is the red flag.

**In this dataset:** Two employees with `inflated_amount` fraud. Their amounts are consistently in the 75th+ percentile for their category.

### Helper columns

**S2 — Category average:**
```
=AVERAGEIF(F:F, F2, E:E)
```

**T2 — Category standard deviation:**
```
=STDEV(IF(F$2:F$15188=F2, E$2:E$15188))
```
⚠️ **Array formula** — press **Ctrl+Shift+Enter** (not just Enter). In Excel 365 it auto-spills.

**U2 — Z-score:**
```
=(E2-S2)/T2
```
Z-score > 2 means the amount is more than 2 standard deviations above the category average.

**V2 — Inflated flag:**
```
=IF(U2>2, "INFLATED", "")
```

### Employee-level analysis (more powerful)

A single inflated transaction doesn't mean fraud. The pattern matters. Create a summary per employee:

In a new sheet, list unique employee IDs in column A. Then:

**B2 — Average z-score for this employee:**
```
=AVERAGEIF(txn[employee_id], A2, txn[z_score])
```
(Uses the pre-calculated z_score column. If working without it, use the manual z-score from column U.)

**C2 — Count of transactions with z > 2:**
```
=COUNTIFS(txn[employee_id], A2, txn[z_score], ">"&2)
```

**D2 — Total transactions:**
```
=COUNTIF(txn[employee_id], A2)

```

**E2 — Percentage of inflated transactions:**
```
=C2/D2
```

Employees with > 20% of their transactions above z = 2 are suspicious.

---

## 5. Round Number Detection

**What:** Employee always submits exact round amounts ($500, $1,000, $1,500, etc.). Real expenses almost never land on perfectly round numbers.

**Signal:** The amount has zero cents AND is a multiple of 500.

**In this dataset:** Two employees submit only round amounts (500, 1000, 1500, 2000, 2500, 3000, 4000, 4500). 40 transactions total.

### Helper columns

**W2 — Is round number?**
```
=IF(AND(MOD(E2,1)=0, MOD(E2,500)=0), 1, 0)
```
Checks two things: no decimal component (MOD by 1 = 0) and divisible by 500.

**X2 — Round flag:**
```
=IF(W2=1, "ROUND", "")
```

### Employee-level analysis

Again, one round number is nothing. The pattern is the signal. In a summary sheet:

**B2 — Count of round transactions:**
```
=SUMPRODUCT((txn[employee_id]=A2)*((MOD(txn[amount],1)=0)*(MOD(txn[amount],500)=0)))
```

**C2 — Total transactions:**
```
=COUNTIF(txn[employee_id], A2)
```

**D2 — Round percentage:**
```
=B2/C2
```

Normal employees might have 1–3% round transactions by chance. Employees with > 30% are highly suspicious. The two fraudulent employees in this dataset have close to 100% round numbers in their fraud transactions.

---

## 6. Composite Employee Risk Scoring

Combine all signals into a single risk score per employee. Build this in a new sheet.

**Column A:** Unique employee IDs

**Column B — Split score** (count of split-flagged transactions):
```
=COUNTIFS(txn[employee_id],A2,K:K,"SPLIT")
```
(References column K from the split detection helper.)

**Column C — Duplicate score:**
```
=COUNTIFS(txn[employee_id],A2,M:M,"DUPLICATE")
```

**Column D — Ghost score:**
```
=COUNTIFS(txn[employee_id],A2,R:R,"GHOST VENDOR")
```

**Column E — Inflated score** (count of z > 2):
```
=COUNTIFS(txn[employee_id],A2,V:V,"INFLATED")
```

**Column F — Round score:**
```
=COUNTIFS(txn[employee_id],A2,X:X,"ROUND")
```

**Column G — Total flags:**
```
=SUM(B2:F2)
```

**Column H — Risk level:**
```
=IF(G2>=10,"CRITICAL",IF(G2>=5,"HIGH",IF(G2>=2,"MEDIUM","LOW")))
```

### Conditional formatting

1. Select column G → Home → Conditional Formatting → Color Scales (red = high, green = low)
2. Select column H → Conditional Formatting → Highlight Cell Rules:
   - Text Contains "CRITICAL" → dark red fill
   - Text Contains "HIGH" → orange fill
   - Text Contains "MEDIUM" → yellow fill

Sort by column G descending. The top 10 employees should include all 10 fraudulent employees if the detection formulas are working correctly.

---

## Quick Validation Checklist

After building all helper columns, verify against `ground_truth.csv`:

| Fraud Type | Expected | How to Verify |
|---|---|---|
| split_purchase | 45 flagged rows | Filter column K = "SPLIT" |
| duplicate_invoice | 32 flagged rows | Filter column M = "DUPLICATE" |
| ghost_vendor | 30 flagged rows | Filter column R = "GHOST VENDOR" |
| inflated_amount | ~30-40 flagged rows | Filter column V = "INFLATED" (some legit outliers expected) |
| round_number | 40 flagged rows | Filter column X = "ROUND" |

> **Note:** Inflated amount detection will have some false positives — legitimate transactions can also have high z-scores. This is expected and realistic. The employee-level analysis (Section 4) is what separates one-off outliers from systematic fraud.
