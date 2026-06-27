import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "collegebrain.db")

def init_db():
    print("[Database] Initializing CollegeBrain Database Engine...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Colleges Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS colleges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        institute_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        city TEXT NOT NULL,
        state TEXT DEFAULT 'Maharashtra',
        country TEXT DEFAULT 'India',
        university TEXT NOT NULL,
        is_autonomous BOOLEAN DEFAULT 0,
        infrastructure_score REAL DEFAULT 0.0,
        avg_placement_lpa REAL DEFAULT 0.0,
        highest_placement_lpa REAL DEFAULT 0.0,
        median_placement_lpa REAL DEFAULT 0.0,
        mass_recruiter_percent INTEGER DEFAULT 0,
        alumni_network_score REAL DEFAULT 0.0,
        city_avg_pg_cost INTEGER DEFAULT 0,
        allows_spot_round BOOLEAN DEFAULT 1,
        hostel_rating REAL DEFAULT 0.0,
        mess_rating REAL DEFAULT 0.0,
        minority_status TEXT DEFAULT 'Non-Minority'
    )
    """)

    # 2. Programs Table (Branches)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS programs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        college_id INTEGER,
        choice_code TEXT UNIQUE NOT NULL,
        branch_name TEXT NOT NULL,
        is_nba_accredited BOOLEAN DEFAULT 0,
        FOREIGN KEY(college_id) REFERENCES colleges(id)
    )
    """)

    # 3. Cutoffs Table (The Core Matrix)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cutoffs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        program_id INTEGER,
        year INTEGER NOT NULL,
        exam_type TEXT NOT NULL, -- e.g. MHT-CET, JEE, DSE
        category TEXT NOT NULL,  -- e.g. GOPEN, LOPEN, OBC, SC, ST
        round_number INTEGER,
        cutoff_percentile REAL NOT NULL,
        state_merit_list INTEGER,
        FOREIGN KEY(program_id) REFERENCES programs(id)
    )
    """)

    # 4. Fees Table (Category specific)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        college_id INTEGER,
        category TEXT NOT NULL,
        tuition_fee INTEGER NOT NULL,
        development_fee INTEGER NOT NULL,
        hostel_fee INTEGER DEFAULT 0,
        mess_fee INTEGER DEFAULT 0,
        other_fees INTEGER DEFAULT 0,
        FOREIGN KEY(college_id) REFERENCES colleges(id)
    )
    """)

    conn.commit()
    conn.close()
    print("[Database] Initialization complete. Schema deployed.")

if __name__ == "__main__":
    init_db()
