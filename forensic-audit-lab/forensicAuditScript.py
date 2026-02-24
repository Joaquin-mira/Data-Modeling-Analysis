import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
import random
import os
import hashlib

random.seed(3003)
np.random.seed(3003)

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_NAME', 'auditoria'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '')
}

NUM_TRANSACTIONS = 15000
NUM_EMPLOYEES = 100
NUM_VENDORS = 70
APPROVAL_THRESHOLD = 5000
FRAUD_RATIO = 0.05


CATEGORIES = {
    'IT':        {'mean': 1800, 'std': 900,  'min': 50,  'max': 4800},
    'Logistics': {'mean': 1200, 'std': 600,  'min': 100, 'max': 4500},
    'Marketing': {'mean': 800,  'std': 400,  'min': 50,  'max': 3500},
    'Supplies':  {'mean': 400,  'std': 200,  'min': 20,  'max': 2000},
    'Travel':    {'mean': 1500, 'std': 700,  'min': 100, 'max': 4900},
}

FRAUD_TYPES = {
    'split_purchase':   'Fragments large purchases to stay below approval threshold',
    'duplicate_invoice': 'Submits the same invoice twice with minor variations',
    'ghost_vendor':     'Bills through a vendor that only invoices to one employee',
    'inflated_amount':  'Systematically inflates amounts above category average',
    'round_number':     'Submits suspiciously round amounts repeatedly',
}

def create_employees():
    employees = []
    fraud_types_list = list(FRAUD_TYPES.keys())
    num_fraudulent = len(fraud_types_list) * 2

    for i in range(NUM_EMPLOYEES):
        emp_id = f"EMP-{i+1:03d}"
        department = random.choice(list(CATEGORIES.keys()))

        if i < num_fraudulent:
            is_fraud = True
            fraud_type = fraud_types_list[i % len(fraud_types_list)]
        else: 
            is_fraud = False
            fraud_type = None

        employees.append({
            'employee_id': emp_id,
            'department': department,
            'is_fraud': is_fraud,
            'fraud_type': fraud_type,
        })
    random.shuffle(employees)
    return employees

def create_vendors(employees):
    vendors = []

    for i in range(NUM_VENDORS):
        vendors.append({
            'vendor_id': f"PROV-{i+1:03d}",
            'vendor_name': f"Vendor_{i+1}",
            'is_ghost': False,
            'exclusive_to': None,
        })
    
    ghost_employees = [e for e in employees if e['fraud_type'] == 'ghost_vendor']
    for i, emp in enumerate(ghost_employees):
        ghost_id = f"PROV-{NUM_VENDORS + i + 1:03d}"
        vendors.append({
            'vendor_id': ghost_id,
            'vendor_name': f"GhostCorp_{i+1}",
            'is_ghost': True,
            'exclusive_to': emp['employee_id'],
        })

    return vendors


def generate_amount(category):
    profile = CATEGORIES[category]
    mean, std = profile['mean'], profile['std']
    a = (profile['min'] - mean ) / std
    b = (profile ['max'] - mean ) / std
    return round(stats.truncnorm(a, b, loc=mean, scale=std).rvs(), 2)


def generate_date():
    month = random.randint(1, 12)
    if random.random() < 0.4:
        day = random.randint(25, 28)
    else:
        day = random.randint(1, 28)
    return datetime(2025, month, day)

def generate_invoice_number(vendor_id, date, seq):
    """Generate a realistic invoice number."""
    return f"INV-{vendor_id[-3:]}-{date.strftime('%Y%m%d')}-{seq:04d}"

def generate_legitimate_transactions(employees, vendors, num_transactions):
    """Generate legitimate transactions with realistic distributions."""
    transactions = []
    regular_vendors = [v for v in vendors if not v['is_ghost']]
    legit_employees = [e for e in employees if not e['is_fraud']]
    # Fraudulent employees also generate legitimate transactions
    all_employees = employees

    for i in range(num_transactions):
        emp = random.choice(all_employees)
        vendor = random.choice(regular_vendors)
        category = emp['department']
        date = generate_date()
        amount = generate_amount(category)

        transactions.append({
            'transaction_id': i + 1,
            'date': date.strftime('%Y-%m-%d'),
            'employee_id': emp['employee_id'],
            'vendor_id': vendor['vendor_id'],
            'amount': amount,
            'category': category,
            'invoice_number': generate_invoice_number(vendor['vendor_id'], date, i),
            'is_fraud': False,
            'fraud_type': None,
        })

    return transactions
def inject_split_purchases(employees, vendors, start_id):
    transactions = []
    fraudsters = [e for e in employees if e['fraud_type'] == 'split_purchase']
    regular_vendors = [v for v in vendors if not v['is_ghost']]
    tx_id = start_id

    for emp in fraudsters:
        for event in range(6):
            date = generate_date()
            vendor = random.choice(regular_vendors)
            total = random.uniform (5500, 8000)
            num_fragments = random.randint (3,5)

            fragments = []
            remaining = total
            for j in range(num_fragments - 1):
                frag = round (random.uniform(800, APPROVAL_THRESHOLD * 0.9 / num_fragments * 2), 2)
                frag = min(frag, remaining - (num_fragments - j - 1) * 100)
                fragments.append(frag)
                remaining -= frag
            fragments.append(round(remaining, 2))

            for j, amount in enumerate(fragments):
                transactions.append({
                    'transaction_id': tx_id,
                    'date': date.strftime('%Y-%m-%d'),
                    'employee_id': emp['employee_id'],
                    'vendor_id': vendor['vendor_id'],
                    'amount': amount,
                    'category': emp['department'],
                    'invoice_number': generate_invoice_number(vendor['vendor_id'], date, tx_id),
                    'is_fraud': True,
                    'fraud_type': 'split_purchase',
                })
                tx_id += 1
                
    return transactions, tx_id

def inject_duplicate_invoices(employees, vendors, start_id):
    transactions = []
    fraudsters = [e for e in employees if e['fraud_type'] == 'duplicate_invoice']
    regular_vendors = [v for v in vendors if not v['is_ghost']]
    tx_id = start_id 
    for emp in fraudsters:
        for event in range(8):
            date = generate_date()
            vendor = random.choice(regular_vendors)
            amount = round(random.uniform(1500, 4500), 2)
            inv_num = generate_invoice_number(vendor['vendor_id'], date, tx_id)

            transactions.append({
                'transaction_id': tx_id,
                'date': date.strftime('%Y-%m-%d'),
                'employee_id': emp['employee_id'],
                'vendor_id': vendor['vendor_id'],
                'amount': amount,
                'category': emp['department'],
                'invoice_number': inv_num,
                'is_fraud': True,
                'fraud_type': 'duplicate_invoice',
            })
            tx_id += 1

            dup_date = date + timedelta(days=random.randint(1, 5))
            dup_amount = round(amount * random.uniform(0.97, 1.03), 2)

            transactions.append({
                'transaction_id': tx_id,
                'date': dup_date.strftime('%Y-%m-%d'),
                'employee_id': emp['employee_id'],
                'vendor_id': vendor['vendor_id'],
                'amount': dup_amount,
                'category': emp['department'],
                'invoice_number': inv_num,  
                'is_fraud': True,
                'fraud_type': 'duplicate_invoice',
            })
            tx_id += 1

    return transactions, tx_id

def inject_ghost_vendor(employees, vendors, start_id): 
    transactions = []
    fraudsters = [e for e in employees if e['fraud_type'] == 'ghost_vendor']
    ghost_vendors = [v for v in vendors if v['is_ghost']]
    tx_id = start_id

    for emp in fraudsters:
        ghost = next((v for v in ghost_vendors if v['exclusive_to'] == emp['employee_id']), None)
        if not ghost:
            continue

        for event in range(15):
            date = generate_date()
            amount = round(random.uniform(2000, 4800), 2)

            transactions.append({
                'transaction_id': tx_id,
                'date': date.strftime('%Y-%m-%d'),
                'employee_id': emp['employee_id'],
                'vendor_id': ghost['vendor_id'],
                'amount': amount,
                'category': emp['department'],
                'invoice_number': generate_invoice_number(ghost['vendor_id'], date, tx_id),
                'is_fraud': True,
                'fraud_type': 'ghost_vendor',
            })
            tx_id += 1

    return transactions, tx_id

def inject_inflated_amounts(employees, vendors, start_id): 
    transactions = []
    fraudsters = [e for e in employees if e['fraud_type'] == 'inflated_amount']
    regular_vendors = [v for v in vendors if not v['is_ghost']]
    tx_id = start_id

    for emp in fraudsters:
        for event in range(20):
            date = generate_date()
            vendor = random.choice(regular_vendors)
            category = emp['department']
            base_amount = generate_amount(category)
            inflated = round(base_amount * random.uniform(1.4, 1.8), 2)
            inflated = min(inflated, 4900)  # Stay below threshold to avoid auto-review

            transactions.append({
                'transaction_id': tx_id,
                'date': date.strftime('%Y-%m-%d'),
                'employee_id': emp['employee_id'],
                'vendor_id': vendor['vendor_id'],
                'amount': inflated,
                'category': category,
                'invoice_number': generate_invoice_number(vendor['vendor_id'], date, tx_id),
                'is_fraud': True,
                'fraud_type': 'inflated_amount',
            })
            tx_id += 1

    return transactions, tx_id

def inject_round_numbers(employees, vendors, start_id):
    transactions = []
    fraudsters = [e for e in employees if e['fraud_type'] == 'round_number']
    regular_vendors = [v for v in vendors if not v['is_ghost']]
    tx_id = start_id
    round_amounts = [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500]

    for emp in fraudsters:
        for event in range(20):
            date = generate_date()
            vendor = random.choice(regular_vendors)
            amount = float(random.choice(round_amounts))

            transactions.append({
                'transaction_id': tx_id,
                'date': date.strftime('%Y-%m-%d'),
                'employee_id': emp['employee_id'],
                'vendor_id': vendor['vendor_id'],
                'amount': amount,
                'category': emp['department'],
                'invoice_number': generate_invoice_number(vendor['vendor_id'], date, tx_id),
                'is_fraud': True,
                'fraud_type': 'round_number',
            })
            tx_id += 1

    return transactions, tx_id


def add_statistical_features(df):

    # Zcore
    cat_stats = df.groupby('category')['amount'].agg(['mean', 'std']).reset_index()
    cat_stats.columns = ['category', 'cat_mean', 'cat_std']
    df = df.merge(cat_stats, on='category')
    df['z_score'] = (df['amount'] - df['cat_mean']) / df['cat_std']

    # Pair frequency 
    pair_freq = df.groupby(['employee_id', 'vendor_id']).size().reset_index(name='pair_frequency')
    df = df.merge(pair_freq, on=['employee_id', 'vendor_id'])

    # Employee total spend
    emp_spend = df.groupby('employee_id')['amount'].sum().reset_index(name='employee_total_spend')
    df = df.merge(emp_spend, on='employee_id')

    # Percentile rank within category
    df['cat_percentile'] = df.groupby('category')['amount'].rank(pct=True)

    # Clean up helper columns
    df.drop(columns=['cat_mean', 'cat_std'], inplace=True)

    return df

def create_visualizations(df):
    """Generate analysis charts."""
    import seaborn as sns
    import matplotlib.pyplot as plt

    os.makedirs('output', exist_ok=True)
    sns.set_style('whitegrid')
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Forensic Audit — Data Overview', fontsize=14, fontweight='bold')

    # 1. Amount distribution by fraud type
    df_viz = df.copy()
    df_viz['label'] = df_viz['is_fraud'].map({True: 'Fraudulent', False: 'Legitimate'})
    sns.boxplot(data=df_viz, x='label', y='amount', ax=axes[0, 0],
                hue='label', palette={'Legitimate': '#3498db', 'Fraudulent': '#e74c3c'}, legend=False)
    axes[0, 0].set_title('Amount Distribution: Legit vs Fraud')
    axes[0, 0].set_xlabel('')

    # 2. Amount distribution by category
    sns.boxplot(data=df, x='category', y='amount', ax=axes[0, 1],
                palette='Set2')
    axes[0, 1].set_title('Amount Distribution by Category')
    axes[0, 1].tick_params(axis='x', rotation=30)

    # 3. Transactions per month
    df_temp = df.copy()
    df_temp['month'] = pd.to_datetime(df_temp['date']).dt.month
    df_temp['label'] = df_temp['is_fraud'].map({True: 'Fraud', False: 'Legit'})
    monthly = df_temp.groupby(['month', 'label']).size().reset_index(name='count')
    sns.barplot(data=monthly, x='month', y='count', hue='label', ax=axes[1, 0],
                palette={'Legit': '#3498db', 'Fraud': '#e74c3c'})
    axes[1, 0].set_title('Transactions per Month')

    # 4. Employee-vendor pair frequency (top 20)
    pair_freq = df.groupby(['employee_id', 'vendor_id']).size().reset_index(name='count')
    top_pairs = pair_freq.nlargest(20, 'count')
    top_pairs['pair'] = top_pairs['employee_id'] + ' → ' + top_pairs['vendor_id']
    # Color ghost vendor pairs
    fraud_pairs = df[df['fraud_type'] == 'ghost_vendor'][['employee_id', 'vendor_id']].drop_duplicates()
    fraud_pair_set = set(zip(fraud_pairs['employee_id'], fraud_pairs['vendor_id']))
    colors = ['#e74c3c' if (r['employee_id'], r['vendor_id']) in fraud_pair_set
              else '#3498db' for _, r in top_pairs.iterrows()]
    axes[1, 1].barh(top_pairs['pair'], top_pairs['count'], color=colors)
    axes[1, 1].set_title('Top 20 Employee-Vendor Pairs (red = ghost)')
    axes[1, 1].invert_yaxis()

    plt.tight_layout()
    plt.savefig('output/forensic_audit_overview.png', dpi=150, bbox_inches='tight')
    print("Saved: output/forensic_audit_overview.png")
    plt.close()

    # Heatmap: fraud type signatures
    fig, ax = plt.subplots(figsize=(12, 6))
    fraud_summary = df[df['is_fraud']].groupby('fraud_type').agg(
        avg_amount=('amount', 'mean'),
        std_amount=('amount', 'std'),
        avg_zscore=('z_score', 'mean'),
        avg_pair_freq=('pair_frequency', 'mean'),
        total_transactions=('transaction_id', 'count'),
        avg_percentile=('cat_percentile', 'mean'),
    )
    # Normalize for heatmap
    fraud_norm = (fraud_summary - fraud_summary.min()) / (fraud_summary.max() - fraud_summary.min())
    sns.heatmap(fraud_norm, annot=fraud_summary.round(2), fmt='', cmap='YlOrRd',
                linewidths=0.5, ax=ax, cbar_kws={'label': 'Normalized Value'})
    ax.set_title('Fraud Type Signatures (normalized heatmap)')

    plt.tight_layout()
    plt.savefig('output/forensic_fraud_signatures.png', dpi=150, bbox_inches='tight')
    print("Saved: output/forensic_fraud_signatures.png")
    plt.close()


# =============================================================================
# EXPORT
# =============================================================================

def export_to_csv(df, employees, vendors):
    """Export to CSV files."""
    os.makedirs('output', exist_ok=True)

    df.to_csv('output/transactions.csv', index=False)
    print(f"Exported: output/transactions.csv ({len(df)} rows)")

    pd.DataFrame(employees).to_csv('output/employees.csv', index=False)
    print(f"Exported: output/employees.csv ({len(employees)} rows)")

    pd.DataFrame(vendors).to_csv('output/vendors.csv', index=False)
    print(f"Exported: output/vendors.csv ({len(vendors)} rows)")

    # Ground truth summary
    truth = df[df['is_fraud']].groupby('fraud_type').agg(
        num_transactions=('transaction_id', 'count'),
        num_employees=('employee_id', 'nunique'),
        avg_amount=('amount', 'mean'),
        total_amount=('amount', 'sum'),
    ).reset_index()
    truth.to_csv('output/ground_truth.csv', index=False)
    print(f"Exported: output/ground_truth.csv")


def export_to_postgres(df):
    """Export to PostgreSQL."""
    try:
        from sqlalchemy import create_engine
        db_url = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        engine = create_engine(db_url)

        df.to_sql('transactions', engine, if_exists='replace', index=False)
        print(f"[+] Loaded {len(df)} rows into PostgreSQL table 'transactions'")
    except Exception as e:
        print(f"[!] PostgreSQL export failed: {e}")
        print("    CSV files are still available in output/")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("  FORENSIC AUDIT — DATA GENERATION")
    print("=" * 70)

    # Create entities
    print("\n[*] Creating employees and vendors...")
    employees = create_employees()
    vendors = create_vendors(employees)

    fraud_emps = [e for e in employees if e['is_fraud']]
    print(f"    {NUM_EMPLOYEES} employees ({len(fraud_emps)} fraudulent)")
    print(f"    {len(vendors)} vendors ({len([v for v in vendors if v['is_ghost']])} ghost)")

    # Generate legitimate transactions
    print(f"\n[*] Generating {NUM_TRANSACTIONS} legitimate transactions...")
    legitimate = generate_legitimate_transactions(employees, vendors, NUM_TRANSACTIONS)

    # Inject fraud
    print("[*] Injecting fraud patterns...")
    next_id = NUM_TRANSACTIONS + 1

    splits, next_id = inject_split_purchases(employees, vendors, next_id)
    print(f"    Split purchases: {len(splits)} transactions")

    duplicates, next_id = inject_duplicate_invoices(employees, vendors, next_id)
    print(f"    Duplicate invoices: {len(duplicates)} transactions")

    ghosts, next_id = inject_ghost_vendor(employees, vendors, next_id)
    print(f"    Ghost vendor: {len(ghosts)} transactions")

    inflated, next_id = inject_inflated_amounts(employees, vendors, next_id)
    print(f"    Inflated amounts: {len(inflated)} transactions")

    rounds, next_id = inject_round_numbers(employees, vendors, next_id)
    print(f"    Round numbers: {len(rounds)} transactions")

    # Combine and shuffle
    all_fraud = splits + duplicates + ghosts + inflated + rounds
    all_transactions = legitimate + all_fraud
    random.shuffle(all_transactions)

    df = pd.DataFrame(all_transactions)

    # Add statistical features
    print("\n[*] Calculating statistical features...")
    df = add_statistical_features(df)

    # Summary
    total_fraud = df['is_fraud'].sum()
    print(f"\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total transactions: {len(df)}")
    print(f"  Legitimate: {len(df) - total_fraud}")
    print(f"  Fraudulent: {total_fraud} ({total_fraud/len(df)*100:.1f}%)")
    print(f"\n  Fraud breakdown:")
    for ft in df[df['is_fraud']].groupby('fraud_type').size().items():
        print(f"    {ft[0]}: {ft[1]} transactions")

    # Export
    print(f"\n[*] Exporting...")
    export_to_csv(df, employees, vendors)
#    export_to_postgres(df)

    # Visualize
    print("\n[*] Generating visualizations...")
    create_visualizations(df)

    print(f"\n{'=' * 70}")
    print("  GENERATION COMPLETE")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
