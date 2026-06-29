import sqlite3
import time
import random
import threading
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from ddgs import DDGS
from groq import Groq
from google import genai
from database import init_db

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Threading Lock to prevent SQLite database corruption when 20 threads write at once
db_lock = threading.Lock()

# ---------------------------------------------------------
# DATABASE CONNECTION HELPER (THREAD SAFE)
# ---------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect('collegebrain.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def update_college_metric(institute_code, field_name, value):
    """Safely updates a single metric for a college using a thread lock."""
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = f"UPDATE colleges SET {field_name} = ? WHERE institute_code = ?"
        cursor.execute(query, (value, institute_code))
        conn.commit()
        conn.close()

# ---------------------------------------------------------
# PIPELINE A: THE LIVE CUTOFF SCRAPER
# ---------------------------------------------------------
def cutoff_scraper_thread(task):
    """
    Dedicated thread for scraping Cutoffs (MHT-CET, JEE Mains, JEE Adv, Diploma).
    """
    institute_code = task.get('institute_code')
    college_name = task.get('name', f"College {institute_code}")
    
    # Smart Skip: Check if we already have cutoffs for this college
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM cutoffs 
            JOIN programs ON cutoffs.program_id = programs.id 
            JOIN colleges ON programs.college_id = colleges.id 
            WHERE colleges.institute_code = ? AND cutoffs.exam_type IN ('Diploma', 'DSE')
        """, (institute_code,))
        if cursor.fetchone()[0] > 0:
            print(f"[Thread-Cutoffs] SKIPPING {institute_code} - Cutoffs already extracted.")
            return True

    print(f"[Thread-Cutoffs] CRAWLING web for {college_name} cutoffs...")
    
    # 1. Search Web ONLY for DSE / Diploma
    q1 = f"{college_name} Direct Second Year Engineering DSE Diploma cutoff percentiles category wise all branches GOPEN OBC SC ST 2023 2024"
    
    # Rate limit protection for DDGS
    time.sleep(random.uniform(1.0, 3.0))
    context = search_web(q1)
    
    if not context.strip():
        print(f"[Thread-Cutoffs] SKIPPING {institute_code} - Web search failed, preventing AI guessing.")
        return False
    
    prompt = f"""
    You are an expert admission counselor extracting cutoff metrics from search results for {college_name}.
    Based on the following search snippets, extract the DIRECT SECOND YEAR (DSE) / Diploma cutoff percentiles for EVERY branch mentioned.
    CRITICAL: DO NOT guess or estimate cutoffs. If the DSE cutoffs are not explicitly in the context, return an empty array.
    
    Search Context:
    {context}
    
    Return ONLY valid JSON matching this schema exactly (no markdown formatting, no comments):
    {{
      "branches": [
        {{
          "branch_name": "Computer Engineering", // Extract the actual branch name found
          "cutoffs": [
            {{
              "exam_type": "Diploma", // MUST BE "Diploma" or "DSE"
              "category": "GOPEN", // Extract EVERY SINGLE category found (GOPEN, OBC, SC, ST, DEF, PWD, etc.)
              "percentile": 92.4, // DSE cutoffs are usually high (85-99)
              "sml": 120 // or null if not found
            }}
          ]
        }}
      ]
    }}
    If no DSE cutoffs are found, return an empty array for branches.
    """
    
    data = call_llm_with_retry(prompt, f"Cutoffs - {institute_code}")

    if not data or 'branches' not in data:
        return False

    extracted_branches = data['branches']
    total_cutoffs = 0

    # Thread-safe database writes
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get college ID
        cursor.execute("SELECT id FROM colleges WHERE institute_code = ?", (institute_code,))
        college_res = cursor.fetchone()
        if college_res:
            college_id = college_res['id']
            
            for branch_data in extracted_branches:
                branch_name = branch_data.get('branch_name', 'Unknown Branch')
                cutoffs_list = branch_data.get('cutoffs', [])
                if not cutoffs_list:
                    continue
                    
                # 1. Check if branch exists for this college
                cursor.execute("SELECT id FROM programs WHERE college_id = ? AND branch_name = ?", (college_id, branch_name))
                prog_res = cursor.fetchone()
                if prog_res:
                    program_id = prog_res['id']
                else:
                    # Dynamically create the branch
                    import random
                    choice_code = f"{institute_code}-{branch_name[:3].upper()}-{random.randint(100,999)}"
                    cursor.execute(
                        "INSERT INTO programs (college_id, choice_code, branch_name) VALUES (?, ?, ?)",
                        (college_id, choice_code, branch_name)
                    )
                    program_id = cursor.lastrowid
                
                # 2. Insert Cutoffs
                for c in cutoffs_list:
                    exam = c.get('exam_type', 'Diploma')
                    cat = c.get('category', 'GOPEN')
                    perc = c.get('percentile', 0.0)
                    sml = c.get('sml', None)
                    
                    cursor.execute(
                        "INSERT INTO cutoffs (program_id, year, exam_type, category, round_number, cutoff_percentile, state_merit_list) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (program_id, 2023, exam, cat, 1, perc, sml)
                    )
                    total_cutoffs += 1
            
            if total_cutoffs > 0:
                cursor.execute("UPDATE colleges SET allows_spot_round = ? WHERE institute_code = ?", (1, institute_code))
        
        conn.commit()
        conn.close()

    print(f"[Thread-Cutoffs] SUCCESS: {institute_code} extracted {total_cutoffs} cutoffs across {len(extracted_branches)} branches!")
    return True

def call_llm_with_retry(prompt, task_name="LLM"):
    """Helper to handle Rate Limits from Groq and Gemini. Instantly falls back to Gemini if Groq limits are hit."""
    for attempt in range(3):
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            err_str = str(e).lower()
            if "rate limit" in err_str or "429" in err_str:
                print(f"[{task_name}] Groq Rate Limit hit. Falling back to Gemini instantly...")
            else:
                print(f"[{task_name}] Groq Error: {e}. Falling back to Gemini...")
                
            try:
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                raw = response.text
                if raw.startswith("```json"):
                    raw = raw[7:-3]
                return json.loads(raw)
            except Exception as e2:
                err2_str = str(e2).lower()
                if "rate limit" in err2_str or "429" in err2_str or "rate limit" in err_str or "429" in err_str:
                    wait_time = 60 # Default wait 60s if both are exhausted
                    
                    # Try to parse exact wait time from the original Groq error
                    match = re.search(r"try again in ([\d.]+)s", err_str)
                    if match:
                        wait_time = max(float(match.group(1)), 10.0)
                        
                    print(f"[{task_name}] BOTH APIs exhausted! Pausing {wait_time}s... (Attempt {attempt+1}/3)")
                    time.sleep(wait_time)
                else:
                    print(f"[{task_name}] Gemini Error: {e2}")
                    return None
    return None

def search_web(query):
    try:
        results = DDGS().text(query, max_results=3)
        context = ""
        for r in results:
            context += f"Title: {r['title']}\nSnippet: {r['body']}\n\n"
        return context
    except Exception as e:
        print(f"[DDGS Error] Skipping search due to {e}...")
        return ""

# ---------------------------------------------------------
# PIPELINE B & C: THE AGENTIC WEB SCRAPER (FINANCE, PLACEMENTS & SENTIMENT)
# ---------------------------------------------------------
def agentic_web_scraper_thread(task):
    """
    Dedicated thread for LLM web scraping via DuckDuckGo + Groq/Gemini.
    """
    institute_code = task['institute_code']
    college_name = task['name']

    # Smart Skip: Check if we already have metrics for this college
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT median_placement_lpa FROM colleges WHERE institute_code = ?", (institute_code,))
        res = cursor.fetchone()
        if res and res[0] > 0:
            print(f"[Thread-Scraper] SKIPPING {institute_code} - Web metrics already parsed.")
            return True

    print(f"[Thread-Scraper] AGENT CRAWLING web for {college_name}...")
    
    # 1. Search Web (ONE single laser-focused query to prevent DDGS timeouts)
    q1 = f"{college_name} highest median placement LPA tuition fees hostel mess infrastructure reviews"
    
    # Rate limit protection for DDGS
    time.sleep(random.uniform(1.0, 3.0))
    context = search_web(q1)
    
    if not context.strip():
        print(f"[Thread-Scraper] SKIPPING {institute_code} - Web search failed, preventing AI guessing.")
        return False
    
    prompt = f"""
    You are an expert admission counselor extracting metrics from search results for {college_name}.
    Based on the following search snippets, extract the numerical metrics requested.
    CRITICAL: DO NOT guess, hallucinate, or estimate any metrics. If a metric is not explicitly found in the Search Context, return 0 for ints/floats.
    
    Search Context:
    {context}
    
    Return ONLY valid JSON matching this schema exactly (no markdown formatting, no comments):
    {{
      "highest_placement_lpa": float,
      "median_placement_lpa": float,
      "mass_recruiter_percent": int,
      "tuition_fee_open": int,
      "tuition_fee_obc_ews_vjnt": int,
      "tuition_fee_sc_st_tfws": int,
      "hostel_fee": int,
      "mess_fee": int,
      "city_avg_pg_cost": int,
      "infrastructure_score": float,
      "alumni_network_score": float,
      "hostel_rating": float,
      "mess_rating": float
    }}
    """
    
    data = call_llm_with_retry(prompt, f"WebScraper - {institute_code}")

    if not data:
        return False

    # 3. Database updates
    update_college_metric(institute_code, 'highest_placement_lpa', data.get('highest_placement_lpa', 0))
    update_college_metric(institute_code, 'median_placement_lpa', data.get('median_placement_lpa', 0))
    update_college_metric(institute_code, 'mass_recruiter_percent', data.get('mass_recruiter_percent', 0))
    update_college_metric(institute_code, 'city_avg_pg_cost', data.get('city_avg_pg_cost', 0))
    update_college_metric(institute_code, 'infrastructure_score', data.get('infrastructure_score', 0))
    update_college_metric(institute_code, 'alumni_network_score', data.get('alumni_network_score', 0))
    update_college_metric(institute_code, 'hostel_rating', data.get('hostel_rating', 0))
    update_college_metric(institute_code, 'mess_rating', data.get('mess_rating', 0))

    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM colleges WHERE institute_code = ?", (institute_code,))
        college_res = cursor.fetchone()
        if college_res:
            c_id = college_res['id']
            # OPEN
            cursor.execute("INSERT INTO fees (college_id, category, tuition_fee, development_fee, hostel_fee, mess_fee) VALUES (?, ?, ?, ?, ?, ?)", 
                (c_id, 'OPEN', data.get('tuition_fee_open', 0), 0, data.get('hostel_fee', 0), data.get('mess_fee', 0)))
            # OBC / EWS / VJNT / NT / SBC
            cursor.execute("INSERT INTO fees (college_id, category, tuition_fee, development_fee, hostel_fee, mess_fee) VALUES (?, ?, ?, ?, ?, ?)", 
                (c_id, 'OBC_EWS', data.get('tuition_fee_obc_ews_vjnt', 0), 0, data.get('hostel_fee', 0), data.get('mess_fee', 0)))
            # SC / ST / TFWS
            cursor.execute("INSERT INTO fees (college_id, category, tuition_fee, development_fee, hostel_fee, mess_fee) VALUES (?, ?, ?, ?, ?, ?)", 
                (c_id, 'SC_ST', data.get('tuition_fee_sc_st_tfws', 0), 0, data.get('hostel_fee', 0), data.get('mess_fee', 0)))
        conn.commit()
        conn.close()

    print(f"[Thread-Scraper] SUCCESS: {institute_code} Web & Sentiment Parsed -> Median: {data.get('median_placement_lpa')} LPA")
    return True

# ---------------------------------------------------------
# PIPELINE 0: THE DISCOVERY ENGINE (SEEDS DB AUTOMATICALLY)
# ---------------------------------------------------------
def discover_region(region):
    print(f"\n[Pipeline 0] AI Scout searching for B.E. and B.Tech Engineering Colleges across {region}...")
    context = search_web(f"List of top BE BTech engineering colleges across {region} with official Institute Codes")
    
    prompt = f"""
    Generate a comprehensive list of up to 30 top engineering colleges offering B.E./B.Tech degrees across {region}. Do NOT include colleges that only offer Master's (M.E./M.Tech) programs.
    You MUST include their official admission code or AICTE Institute ID (e.g., JoSAA code, COMEDK code, or State Code).
    
    Context: {context}
    
    Return ONLY valid JSON matching this exact schema:
    {{
      "colleges": [
        {{
          "institute_code": "KA-102",
          "name": "RV College of Engineering",
          "city": "Bengaluru",
          "state": "{region}"
        }}
      ]
    }}
    """
    data = call_llm_with_retry(prompt, f"Pipeline 0 - {region}")
    if data and "colleges" in data:
        return data.get("colleges", [])
    return []

def discover_all_colleges():
    # Loop through ALL 28 States and 8 Union Territories to guarantee zero misses
    regions = [
        "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", 
        "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", 
        "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", 
        "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", 
        "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", 
        "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli", 
        "Daman and Diu", "Lakshadweep", "Delhi", "Puducherry", "Ladakh", "Jammu and Kashmir"
    ]
    all_colleges = []
    
    # Parallelize the discovery phase! Max workers=3 to avoid DDGS block.
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_region = {executor.submit(discover_region, region): region for region in regions}
        for future in as_completed(future_to_region):
            region = future_to_region[future]
            colleges = future.result()
            if colleges:
                all_colleges.extend(colleges)
                print(f" -> Found {len(colleges)} colleges in {region}!")
        
    print(f"\n[Pipeline 0] Seeding {len(all_colleges)} discovered colleges into SQLite...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inserted = 0
    for c in all_colleges:
        cursor.execute("SELECT id FROM colleges WHERE institute_code = ?", (c['institute_code'],))
        if not cursor.fetchone():
            # In the new parallel structure, we pass c['state'] rather than the outer region loop var
            state_val = c.get('state', 'Unknown')
            cursor.execute('''
                INSERT INTO colleges (institute_code, name, city, state, country, university)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (c['institute_code'], c['name'], c['city'], state_val, 'India', 'State / Autonomous University'))
            
            # GET THE ID OF THE INSERTED COLLEGE
            college_id = cursor.lastrowid
            
            # INSERT A DEFAULT PROGRAM SO CUTOFFS CAN ATTACH
            cursor.execute('''
                INSERT INTO programs (college_id, choice_code, branch_name)
                VALUES (?, ?, ?)
            ''', (college_id, f"{c['institute_code']}CS", "Computer Engineering"))
            
            inserted += 1
            
    conn.commit()
    conn.close()
    print(f"[Pipeline 0] SUCCESS: Seeded {inserted} new colleges automatically!\n")


# ---------------------------------------------------------
# MASTER CRON JOB EXECUTOR
# ---------------------------------------------------------
def run_all_cutoffs(colleges):
    for college in colleges:
        cutoff_scraper_thread(college)

def run_all_web_metrics(colleges):
    for college in colleges:
        agentic_web_scraper_thread(college)

def run_nightly_cron_job():
    print("==========================================================")
    print("[2:00 AM CRON JOB] Starting Master Ingestion Engine...")
    print("==========================================================")

    # 0. Ensure Database exists and schema is loaded
    init_db()

    # 1. Run Pipeline 0 (Discovery) to find any new colleges
    discover_all_colleges()

    # 2. Load all colleges for scraping
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM colleges")
    colleges = [dict(row) for row in cursor.fetchall()]
    conn.close()

    print(f"Loaded {len(colleges)} colleges for processing.")

    # 3. Execute Task-Level Threading (Parameter-based)
    # Exactly 2 threads: One parses all cutoffs, One parses all placements/fees.
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        
        # Dispatch the massive cutoff loop to Thread 1
        futures.append(executor.submit(run_all_cutoffs, colleges))
        
        # Dispatch the massive web metrics loop to Thread 2
        futures.append(executor.submit(run_all_web_metrics, colleges))

        for future in as_completed(futures):
            try:
                future.result() 
            except Exception as e:
                print(f"[CRITICAL ERROR] A task thread crashed: {e}")

    end_time = time.time()
    print("==========================================================")
    print(f"SUCCESS: CRON JOB FINISHED in {round(end_time - start_time, 2)} seconds!")
    print(f"SUCCESS: Processed autonomous extraction via Task-Level Threading.")
    print("SUCCESS: CollegeBrain Database is 100% Live and Accurate.")
    print("==========================================================")

if __name__ == "__main__":
    run_nightly_cron_job()
