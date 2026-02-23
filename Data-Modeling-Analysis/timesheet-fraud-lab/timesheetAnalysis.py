import pandas as pd
import numpy as np
from scipy import stats
# Visualización estadística low-code
import seaborn as sns
# requisito de seaborn
import matplotlib.pyplot as plt
# Algoritmo de clustering por similitud
from sklearn.cluster import KMeans
# Algoritmo de detección de anomalías, aleatoriza los datos y detecta los que se aislan rápido
from sklearn.ensemble import IsolationForest
# Normaliza datos para evitar sesgo a los números más altos
from sklearn.preprocessing import StandardScaler

df = pd.read_csv('output/timesheet_raw.csv')


def build_employee_features(df):
    features = df.groupby('employee_id').agg(
        department = ('department', 'first'),
        avg_hours = ('hours_reported', 'mean'),
        std_hours = ('hours_reported', 'std'),
        max_hours = ('hours_reported', 'max'),
        min_hours = ('hours_reported', 'min'),
        total_hours = ('hours_reported', 'sum')
    ).reset_index()

# la diferencia en escala no cambia la varianza de los viernes, es una
## buena medición que puede ser aplicada a todos los dias de la semana
### para mayor detección de outliers
    friday_avg = df[df['day_of_week'] == 'Friday'].groupby('employee_id')['hours_reported'].mean()
    non_friday_avg = df[df['day_of_week'] != 'Friday'].groupby('employee_id')['hours_reported'].mean()
    features['friday_ratio'] = (friday_avg / non_friday_avg).values

# Normaliza la dispersión por la media. Es útil porque permite comparar el desvío
## empleados con distintos niveles de horas.
### un desvío de 0.8 es mucho si la media es 4 pero poco si es 12
    features['coeff_variation'] = features ['std_hours'] / features ['avg_hours']

# proporción de dias donde hours % 1 == 0
## la posibilidad de obtener un entero en distribución continúa es bajisima
### que el promedio de las horas sea un entero sin decimales es manipulación
    round_pct = df.groupby('employee_id').apply(
        lambda x: (x['hours_reported'] % 1 == 0).mean()
    )
    features['round_pct'] = round_pct.values
    month_order = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6}
    df['month_num'] = df['month'].map(month_order)

# regresión lineal para ver el slope 
    def calc_slope(group):  
        monthly_avg = group.groupby('month_num')['hours_reported'].mean()
        if len(monthly_avg) < 2:
            return 0
        slope, _, _, _, _ = stats.linregress (monthly_avg.index, monthly_avg.values)
        return slope
    
    slopes = df.groupby('employee_id').apply(calc_slope)
    features['monthly_slope'] = slopes.values

    features['pct_outlier_days'] = df.groupby('employee_id').apply(
        lambda x: (x['z_score'].abs() < 2).mean()
    ).values

    truth = df.groupby('employee_id').agg(
        is_fraud=('is_fraud', 'first'),
        fraud_type=('fraud_type', 'first'),
    ).reset_index()

    features = features.merge(truth, on='employee_id')
    return features
features = build_employee_features(df)

# el 50% central de los datos es lo normal y cualquier valor que se aleje de ese rango
## mas de 1.5 es outlier
### q1 - 1.5*iqr corresponde al percentil 0.7% 
#### q3 + 15.iqr corresponde al percentil 99.3%
#### el cálculo captura el 99% y flaggea el 1% extremo
##### se complica al tener una muestra pequeña, por eso el calculo iqr == 0
def detect_outliers_iqr(features):
    # flags using interquartile method on multiple features

    # Q1 es el percentil 25, Q2 el 75
    # la diferencia entre percentiles es IQR,  el rango normal del 50% de los datos
    detection_cols = ['avg_hours', 'friday_ratio', 'coeff_variation',
                      'round_pct', 'monthly_slope', 'pct_outlier_days']
    features['iqr_flags'] = 0
## cualquier valor < q1 - 1.5 * IQR y cualquier valor > q3 + 1.5 * IQR es outlier
## se aplica IQR a cada feature y se calculan cuantas flags acumula cada empleado 
# iqr_flags = 3 significa que ese empleado es outlier en 3 de 6 metricas
    for col in detection_cols:
        Q1 = features[col].quantile(0.25)
        Q3 = features[col].quantile(0.75)
        IQR = Q3 - Q1

## Para resolver el problema de que la gran mayoría de valores son iguales
# Como el cálculo con IQR = 0 no da nada útil, se marca como outlier automáticamente
        if IQR == 0:
            median = features[col].median()
            is_outlier = features[col] != median
        else:
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            is_outlier = (features[col] < lower) | (features[col] > upper)
        features[f'outlier_{col}'] = is_outlier.astype(int)
        features ['iqr_flags'] += is_outlier.astype(int) 
# Ser outlier en 2 o más métricas es señal fuerte.
    features['iqr_suspect'] = features['iqr_flags'] >= 2
    return features

# En vez de modelar lo normal y ver que no encaja modela lo anómalo y lo aisla mediante cortes
## un punto anómalo en un área poco densa requiere muchos menos cortes para quedar aislado 
### que un punto en un área densa
#### el valor de contamination le dice el umbral de decisión en el percentil 20
def detect_anomalies_isolation_forest(features):
## el algoritmo construye puntos con features al azar y va "cortando" al azar para dividir datos
# los puntos normales están en zonas densas y no se aislan fácil, los outliers si
    detection_cols = ['avg_hours', 'friday_ratio', 'coeff_variation',
                      'round_pct', 'monthly_slope', 'pct_outlier_days']
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features[detection_cols])
# en la realidad el vlaor de contamination hay que ir probandolo
    iso_forest = IsolationForest(contamination=0.2, random_state=42)
    features['iso_prediction'] = iso_forest.fit_predict(X_scaled)
    features['iso_suspect'] = features ['iso_prediction'] == -1
    features ['iso_score'] = iso_forest.decision_function(X_scaled)
    return features


# KMeans es un algoritmo de clustering mediante calculos
## itera varias veces para dar con el mejor resultado
### un cluster de friday inflators se da por el friday_ratio alto y asi
#### con K=4 encontró un cluster de friday_inflators, uno de round, uno de gradual
##### y uno con todo lo demas, incluyendo burst y consistent porque 
##### no son lo suficientemente extremos individualmente en sus features
def cluster_employees (features, n_clusters=4):
    detection_cols = ['avg_hours', 'friday_ratio', 'coeff_variation',
                      'round_pct', 'monthly_slope', 'pct_outlier_days']
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features[detection_cols])
# KMeans ejecuta 10 posiciones iniciales y se queda con el mejor resultado
    kmeans = KMeans (n_clusters=n_clusters, random_state=42, n_init=10)
    features['cluster'] = kmeans.fit_predict(X_scaled)

    return features

    features = build_employee_features(df)
features = detect_outliers_iqr(features)
features = detect_anomalies_isolation_forest(features)
features = cluster_employees(features)

# IQR es explicable pero rigido / isolation forest es opaco / KMeans no rankea 
## se normalizan y se comparan datos
### IQR flags= enteros de 0 a 6 / isolation decimales de -0.16 a +0.13
#### cluster fraud proporcion de 0 a 1
#### este bloque normaliza los datos. emp con 0 flags -> 0.0
#### con 2 flags -> 0.33 // con 6/6 -> 1.0
def build_composite_score(features):
    features['iqr_score'] = features['iqr_flags'] / features ['iqr_flags'].max()
    features['iso_norm'] = 1 - (features['iso_score'] - features ['iso_score'].min()) / \
                            (features['iso_score'].max() - features['iso_score'].min())
    
    cluster_fraud_rate = features.groupby('cluster')['is_fraud'].mean()
    features['cluster_risk'] = features['cluster'].map(cluster_fraud_rate)

    features['risk_score'] = (
        0.35 * features['iqr_score'] +
        0.45 * features['iso_norm'] +
        0.25 * features['cluster_risk']
    )

    return features

features = build_employee_features(df)
features = detect_outliers_iqr(features)
features = detect_anomalies_isolation_forest(features)
features = cluster_employees(features)
features = build_composite_score(features)

# --- IQR Results (fixed) ---
print("=" * 70)
print("IQR METHOD (threshold >= 2)")
print("=" * 70)
iqr_suspects = features[features['iqr_suspect']]
print(f"Flagged: {len(iqr_suspects)} employees")
print(f"True positives: {iqr_suspects['is_fraud'].sum()} / {features['is_fraud'].sum()}")
print(f"False positives: {(~iqr_suspects['is_fraud']).sum()}")

# --- Composite Ranking ---
print("\n" + "=" * 70)
print("COMPOSITE RISK SCORE - TOP 15")
print("=" * 70)
top15 = features.nlargest(15, 'risk_score')[
    ['employee_id', 'department', 'risk_score', 'iqr_flags', 'iso_score', 
     'cluster', 'is_fraud', 'fraud_type']
]
print(top15.to_string(index=False))

def create_visualizations(df, features):


    sns.set_style('whitegrid')
    fig, axes = plt.subplots(2, 2, figsize=(14,10))
    fig.suptitle('Timesheet Fraud Detection - Statistical Analysis', fontsize=14, fontweight='bold')

    sns.boxplot(data=df, x='is_fraud', y='hours_reported', ax=axes[0,0])
    axes[0, 0].set_title('Hours Distribution: Legit vs Fraud')
    axes[0, 0].set_xticklabels(['Legitimate', 'Fraudulent'])

    fraud_only = features[features['is_fraud'] == True]
    legit_sample = features[features['is_fraud'] == False].head(5)
    comparison = pd.concat([fraud_only, legit_sample])

    sns.barplot(data=comparison, x='employee_id', y='friday_ratio',
                hue='fraud_type', dodge=False, ax=axes[0,1])
    axes[0, 1].set_title('Friday Ratio by Employee')
    axes[0,1].tick_params(axis='x', rotation=45)
    axes[0,1].axhline(y=1.0, color='red', linestyle='--', alpha=0.5)

    colors= ['red' if f else 'steelblue' for f in features['is_fraud']]
    axes[1, 0].bar(range(len(features)),
                         features.sort_values('risk_score', ascending=False)['risk_score'].values,
                         color= [colors[i] for i in features.sort_values('risk_score', ascending=False).index]
                        )
    
    axes[1, 0].set_title('Composite Risk Score (red = actual fraud)')
    axes[1, 0].set_xlabel('Employees Sorted by Risk')
    axes[1, 0].axhline(y=0.5, color= 'orange', linestyle='--', label='Threshold')
    axes[1, 0].legend()

    scatter = axes [1, 1].scatter(features['avg_hours'], features['friday_ratio'],
                                  c=features['cluster'], cmap='Set1',
                                  s=100, edgecolor='black', linewidth=0.5)
    
    fraud_mask = features['is_fraud'] == True
    axes[1, 1].scatter(features[fraud_mask]['avg_hours'], features[fraud_mask]['friday_ratio'],
                       marker='x', s=200, c='black', linewidths=2, label='Fraud')
    
    axes[1, 1].set_title('CLuster: Avg Hours vs Friday Ratio')
    axes[1, 1].set_xlabel('Average Hours')
    axes[1, 1].set_ylabel('Friday Ratio')
    axes[1, 1].legend()

    plt.tight_layout()
    import os
    os.makedirs('images', exist_ok=True)

    plt.savefig('images/fraud_analysis_chart.png', dpi=150, bbox_inches='tight')
    print("Saved: images/fraud_analysis_chart.png")
    plt.close()

    fig, ax = plt.subplots(figsize=(12, 8 ))

    heatmap_cols = ['avg_hours', 'std_hours', 'friday_ratio', 'coeff_variation',
                    'round_pct', 'monthly_slope', 'pct_outlier_days', 'risk_score']
    
    heatmap_data = features.set_index('employee_id')[heatmap_cols]
    heatmap_data = heatmap_data.sort_values('risk_score', ascending=False)
    heatmap_normalized = (heatmap_data - heatmap_data.min()) / (heatmap_data.max()- heatmap_data.min())

    sns.heatmap(heatmap_normalized, cmap='YlOrRd', annot=heatmap_data.round(2),
                fmt='', linewidths=0.5, ax=ax, cbar_kws={'label': 'Normalized Value'})
    ax.set_title('Employee Risk Heatmap (sorted by risk score)')

    plt.tight_layout()
    plt.savefig('images/fraud_heatmap.png', dpi=150, bbox_inches='tight')
    print("Saved: images/fraud_heatmap.png")
    plt.close()

create_visualizations(df, features)


# las visualizaciones muestran:
## boxplot: las medianas de fraude y legítimo son distintas pero se solapan
### por lo que se necesitan mas features para separar

## friday ratio: muestra los outlier de dos empleados

## risk score: el threshold pierde los 3 fraudes con bajo score
### pero agrupa bien 7 fraudes

## heatmap: es la visualización más rica