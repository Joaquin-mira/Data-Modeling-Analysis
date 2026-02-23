import random 
import string
import os
import psycopg2
from datetime import datetime, timedelta
from psycopg2.extras import execute_values

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_NAME', 'card_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD')
}

# Constants for data generation
# Fixed seed for reproducibility and debugging purposes.
# For a "production-like" run, delete it and modify line 30
SEED = 42
NUM_LEGITIMATE_TRANSACTIONS = 9999
NUM_CARD_TESTING_ATTACKS = 3

CARDS_PER_ATTACK_RANGE = (50, 150)
CARD_TEST_AMMOUNT_RANGE = (1, 5)
CARD_TEST_TIME_WINDOWS_MINUTES = 15

LEGITIMATE_AMMOUNT_RANGE = (10, 500)
LEGITIMATE_TIME_SPREAD_HOURS = 48

random.seed(SEED)

def generate_credit_card_number(bin_prefix=None): # Generates a realistic credit card number with a randomly selected BIN number
    if bin_prefix is None:
        bin_prefix = random.choice([
            '534892', # Mastercard Galicia
            '748963', # Visa Galicia
            '184637', # Mastercard Santander
            '923157', # Visa Santander
            '821850', # Mastercard BBVA
            '454172', # Visa BBVA 
        ])

    remaining = ''.join([str(random.randint(0, 9)) for _ in range(10)])
    return bin_prefix + remaining

def generate_ip_adress(): # Generates a realistic IP adress.
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"

def normalize_timestamp(dt):
    return dt.replace(microsecond=0)

def generate_legitimate_transactions(num_transactions, start_time):
# Ammounts between 1 and 5 dollars, spread every 15 minutes over the last 48 hours and with a specific card number and IP address.
    transactions = []
    recurring_customer_ips = [generate_ip_adress() for _ in range(num_transactions // 3)]
    for _ in range(num_transactions):
        random_offset = timedelta(
            hours = random.randint(0, LEGITIMATE_TIME_SPREAD_HOURS),
            minutes = random.randint(0, 59),
            seconds = random.randint(0, 59)
        )
        txn_time = normalize_timestamp(start_time + random_offset)
        ammount = round(random.uniform(*LEGITIMATE_AMMOUNT_RANGE), 2)

        if random.random() < 0.7 and recurring_customer_ips: # 70% chance to use a recurring customer IP
            ip = random.choice(recurring_customer_ips)
        else:            
            ip = generate_ip_adress()
        
        card = generate_credit_card_number()

        transactions.append({
            'timestamp': txn_time,
            'amount': ammount,
            'card_number': card,
            'bin': card[:6],
            'ip_address': ip,
            'customer_id': f"CUST{random.randint(1, 100):03d}",
            'is_fraud': False
        })
    return transactions

def generate_card_testing_attack(attack_id, start_time):
# Attacker has multiple cards with same BIN
# Does micro-payments to test card validity
# Using 1-3 IP addresses to avoid simple detection

    transactions = []
    num_cards = random.randint(*CARDS_PER_ATTACK_RANGE)
    attacker_ips = [generate_ip_adress() for _ in range(random.randint(1, 3))]
    stolen_bin = random.choice([
        '534892', # Mastercard Galicia
        '748963', # Visa Galicia
        '184637', # Mastercard Santander
        '923157', # Visa Santander
        '821850', # Mastercard BBVA
        '454172', # Visa BBVA
    ])

    attack_start = normalize_timestamp(start_time + timedelta(
        hours = random.randint(0, LEGITIMATE_TIME_SPREAD_HOURS - 1),
    ))
    current_time = attack_start

    for i in range(num_cards):
        seconds_increment = random.randint(3, 12)
        current_time = current_time + timedelta(seconds=seconds_increment)

        if (current_time - attack_start).total_seconds() > CARD_TEST_TIME_WINDOWS_MINUTES * 60:
            current_time = attack_start + timedelta(minutes=CARD_TEST_TIME_WINDOWS_MINUTES)

        amount = round(random.uniform(*CARD_TEST_AMMOUNT_RANGE), 2)
        ip = random.choice(attacker_ips)
        card = generate_credit_card_number(bin_prefix=stolen_bin)

    # Generate transaction item
        transactions.append({
            'timestamp': current_time,
            'amount': amount,
            'card_number': card,
            'bin': stolen_bin,
            'ip_address': ip,
            'customer_id': f"CUST{random.randint(1, 100):03d}",
            'is_fraud': True,
            'fraud_type': f'card_testing_attack_{attack_id} '
                })
    return transactions


def add_noise_to_fraud(fraud_transactions, noise_percentage=0.15):
    # Adds randomness to fraud transactions to make them less uniform and more realistic

    for txn in fraud_transactions:
        if random.random() < noise_percentage:
            if random.random() < 0.3:
                txn['amount'] = round(random.uniform(6, 10),2)
            if random.random() < 0.2:
                txn['timestamp'] += timedelta(minutes=random.randint(30, 60))
    
    return fraud_transactions

def create_database_if_not_exists():
    conn = psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        database=DB_CONFIG['database'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password']
    )
    conn.autocommit = True
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_CONFIG['database'],))
    exists = cursor.fetchone()
    if not exists:
        cursor.execute(f"CREATE DATABASE {DB_CONFIG['database']}")
        print(f"Database '{DB_CONFIG['database']}' created.")
    
    cursor.close()
    conn.close()


def upload_to_postgres(transactions):
    print (f"Uploading {len(transactions)} transactions to PostgreSQL...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        records = [
            (
                txn['timestamp'],
                txn['amount'],
                txn['card_number'],
                txn['bin'],
                txn['ip_address'],
                txn['customer_id'],
                txn['is_fraud'],
                txn.get('fraud_type')
          ) 
            for txn in transactions
     ]
        insert_query = """
         INSERT INTO transactions (timestamp, amount, card_number, bin, ip_address, customer_id, is_fraud, fraud_type)
         VALUES %s
        """

        execute_values(cursor, insert_query, records, page_size=1000)
        conn.commit()
        print("Upload complete.")
    
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error uploading to PostgreSQL: {e}")
        raise


def main():
    print("\n" + "="*70)
    print(" "*20 + "CARD TESTING FRAUD GENERATION")
    print("="*70 + "\n")

    base_time = datetime.now() - timedelta(days=2)

    print(F"Generating {NUM_LEGITIMATE_TRANSACTIONS} legitimate transactions...")
    legitimate = generate_legitimate_transactions(NUM_LEGITIMATE_TRANSACTIONS, base_time)
    print(f"Generated {len(legitimate)} legitimate transactions.")

    print(F" Generating {NUM_CARD_TESTING_ATTACKS} card testing attacks...")
    all_fraud = []
    for attack_id in range(1, NUM_CARD_TESTING_ATTACKS + 1):
        attack = generate_card_testing_attack(attack_id, base_time)
        print(f"Generated {len(attack)} transactions for attack {attack_id}.")
        all_fraud.extend(attack)

    print(f"generated {len(all_fraud)} fraud transactions.")

    print("Adding noise to fraud transactions...")
    all_transactions = legitimate + all_fraud
    all_transactions.sort(key=lambda x: x['timestamp'])

    print("Stats")
    print(f"Total transactions: {len(all_transactions)}")
    print(f"Total legitimate transactions: {len(legitimate)}")
    print(f"Total fraud transactions: {len(all_fraud)}")
    print(F"Fraud percentage: {len(all_fraud) / len(all_transactions) * 100:.2f}%\n")

    create_database_if_not_exists()
    
    upload_to_postgres(all_transactions)

    print ("\n" + "="*70)
    print("Generation complete")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()