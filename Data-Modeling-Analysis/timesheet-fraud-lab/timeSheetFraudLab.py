import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
import random

random.seed(42)
np.random.seed(42)

NUM_EMPLOYEES = 50
NUM_MONTHS = 6 
WORKDAYS_PER_MONTH = 20


DEPARTMENTS = {
    'Engineering': {'mean_hours': 8.2, 'std': 0.8},
    'Sales': {'mean_hours': 7.8, 'std': 1.0},
    'Marketing': {'mean_hours': 7.5, 'std': 0.7},
    'Finance': {'mean_hours': 8.0, 'std': 0.6},
    'Operations': {'mean_hours': 8.5, 'std': 0.9},
}

FRAUD_TYPES = {
    'consistent_padding': 'always adds 1-2 extra hours',
    'friday_inflator': 'inflates hours on Fridays',
    'round_number': 'always reports round numbers',
    'gradual_increase': 'gradually increases hours over time',
    'burst_padding': 'normal weeks + padded weeks',
}



def create_employees(num_employees, fraud_ratio=0.2):
    employees = []
    num_fraudulent = int(num_employees * fraud_ratio)
    fraud_types_list = list(FRAUD_TYPES.keys())

    for i in range (num_employees):
        emp_id = f"EMP-{i+1:03d}"
        department = random.choice(list(DEPARTMENTS.keys()))

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
            'fraud_type': fraud_type
        })

    random.shuffle(employees)
    return employees



def generate_workdays(year, month):
    first_day = datetime (year, month, 1)
    if month == 12:
        last_day = datetime (year + 1, 1, 1)
    else:
        last_day = datetime (year, month + 1, 1) 

    workdays = []
    current = first_day
    while current < last_day:
        if current.weekday() < 5:
            workdays.append(current)
        current += timedelta(days=1)
    return workdays 



def generate_hours(employee, workdays, month_index):

    dept = employee['department']
    mean_h = DEPARTMENTS[dept]['mean_hours']
    std_h = DEPARTMENTS[dept]['std']

    base_distribution = stats.truncnorm(
        (4- mean_h) / std_h,
        (12 - mean_h) / std_h,
        loc = mean_h,
        scale = std_h
    )

    hours = base_distribution.rvs(size=len(workdays))

    if employee['is_fraud']:
        hours = apply_fraud_pattern(
            hours, workdays, employee['fraud_type'], month_index    
        )
    
    return np.round(hours, 2)



def apply_fraud_pattern(hours, workdays, fraud_type, month_index):
    modified = hours.copy()

    if fraud_type == 'consistent_padding':
        padding = np.random.uniform(1.0, 2.0, size=len(hours))
        modified = hours + padding

    elif fraud_type == 'friday_inflator':
        for i, day in enumerate(workdays):
            if day.weekday() == 4:
                modified[i] = hours[i] + np.random.uniform(2.0, 4.0)

    elif fraud_type == 'round_number':
        modified = np.array([random.choice([8.0, 9.0, 10.0]) for _ in hours])

    elif fraud_type == 'gradual_increase':
        monthly_bump = 0.5 * month_index
        modified = hours + monthly_bump

    elif fraud_type == 'burst_padding':
        burst_mask = np.random.random(len(hours)) < 0.2
        burst_amount = np.random.uniform(3.0, 5.0, size=len(hours))
    
    modified = np.clip(modified, 4.0, 16.0)
    return modified

def build_full_dataset(employees):
    all_records = []

    for month_idx in range(NUM_MONTHS):
        month = month_idx + 1
        workdays = generate_workdays (2024, month)

        for emp in employees:
            hours = generate_hours(emp, workdays, month_idx)

            for day, h in zip(workdays, hours):
                all_records.append({
                    'employee_id': emp['employee_id'],
                    'department': emp['department'],
                    'date': day.strftime('%Y-%m-%d'),
                    'day_of_week': day.strftime('%A'),
                    'month': day.strftime ('%B'),
                    'hours_reported': h,
                    'is_fraud': emp['is_fraud'],
                    'fraud_type': emp['fraud_type'],
                })
    df = pd.DataFrame(all_records)
    return df


def add_statistical_columns(df):
    monthly = df.groupby(['employee_id', 'month']).agg(
        monthly_mean= ('hours_reported', 'mean'),
        monthly_std = ('hours_reported', 'std'),
        monthly_total = ('hours_reported', 'sum'),
        days_worked = ('hours_reported', 'count'),
    ).reset_index()

    global_stats = df.groupby('employee_id').agg(
        global_mean=('hours_reported', 'mean'),
        global_std=('hours_reported', 'std'),
    ).reset_index()

    df= df.merge(global_stats, on='employee_id')

    
    df['z_score'] = (df['hours_reported'] - df['global_mean']) / df['global_std']
    
    df['dept_percentile'] = df.groupby('department')['hours_reported'].rank(pct=True)

    return df, monthly

def export_data (df, monthly_stats, employees):
    import os
    os.makedirs('output', exist_ok=True)

    df.to_csv('output/timesheet_raw.csv', index=False)
    print (f"Exported: output/timesheet_raw.csv ({len(df)} rows)")
    with pd.ExcelWriter('output/timesheet_analysis.xlsx', engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Daily_Records', index=False)
        monthly_stats.to_excel(writer, sheet_name='Monthly_Summary', index=False)

        profiles = df.groupby(['employee_id', 'department', 'is_fraud', 'fraud_type']).agg(
            avg_hours=('hours_reported', 'mean'),
            std_hours=('hours_reported', 'std'),
            total_hours=('hours_reported', 'sum'),
            max_hours=('hours_reported', 'max'),
            min_hours=('hours_reported', 'min'),
            avg_zscore=('z_score', 'mean'),
            days_above_z2=('z_score', lambda x: (x > 2).sum()),
        ).reset_index()
        profiles.to_excel(writer, sheet_name='Employee_Profiles', index=False)

        truth=pd.DataFrame(employees)[['employee_id', 'is_fraud', 'fraud_type']]
        truth.to_excel(writer, sheet_name="Ground Truth", index=False)
    print(f"Exported: output/timesheet_analysis.xlsx (4 sheets)")
    print(f"\nSheets: Daily_Records, Monthly_Summary, Employee_Profiles, Ground_Truth")
    
    return profiles   

employees = create_employees(NUM_EMPLOYEES)
df = build_full_dataset(employees)
df, monthly_stats = add_statistical_columns(df)
profiles = export_data(df, monthly_stats, employees)

print(f"\n--- FINAL SUMMARY ---")
print(f"Total records: {len(df)}")
print(f"Employees: {df['employee_id'].nunique()}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"\nEmployee Profiles (top 10 by avg z-score):")
top_suspicious = profiles.nlargest(10, 'avg_zscore')[['employee_id','department','avg_hours','std_hours','avg_zscore','days_above_z2','is_fraud','fraud_type']]
print(top_suspicious.to_string(index=False))


# consistent padding desplaza la media hacia arriba pero mantiene
## la distribución intacta porque el padding es uniforme
### El zcore no lo detecta, hay que comparar entre empleados.

# friday inflator crea una distribución bimodal, normal de lunes a jueves
## y los viernes siguen otra campana de gauss desplazada
### esto lo hace detectable filtrando por día de semana

# round number destruye la forma normal de la distribución 
## solo tiene una distribución discreta con 3 valores: 8, 9 y 10
### el coeficiente de variación es anormalmente bajo y el porcentaje de redondos es 100%

# gradual increase introduce una tendencia temporal, 
## la distribucion es normal en enero pero es +2.5 en junio
### la regresion lineal captrua esta pendiente positiva significativa

# burst padding crea una distribución con cola pesada a la derecha
## la mayoría de los días son normales pero hay picos esporádicos
### dificil de detectar, requiere mirar la proporcipon de outliers individuales
