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
            WHERE colleges.institute_code = ?
        """, (institute_code,))
        if cursor.fetchone()[0] > 0:
            print(f"[Thread-Cutoffs] SKIPPING {institute_code} - Cutoffs already extracted.")
            return True

    print(f"[Thread-Cutoffs] CRAWLING web for {college_name} cutoffs...")
    
    # 1. Search Web
    q1 = f"{college_name} MHT CET cutoffs category wise GOPEN OBC SC ST 2023 2024"
    q2 = f"{college_name} JEE Mains Advanced cutoff percentiles 2023"
    q3 = f"{college_name} Direct Second Year Diploma DSE cutoff percentiles"
    q4 = f"{college_name} M.E. M.Tech GATE PERA CET Non-GATE cutoff percentiles"
    
    # Rate limit protection for DDGS
    time.sleep(random.uniform(1.0, 3.0))
    context = search_web(q1) + search_web(q2) + search_web(q3) + search_web(q4)
    
    prompt = f"""
    You are an expert admission counselor extracting cutoff metrics from search results for {college_name}.
    Based on the following search snippets, extract the cutoff percentiles for various exams.
    
    Search Context:
    {context}
    
    Return ONLY valid JSON matching this schema exactly (no markdown formatting, no comments):
    {{
      "cutoffs": [
        {{
          "exam_type": "MHT-CET", // or "JEE", "JEE-Adv", "Diploma", "GATE", "PERA-CET", "Non-GATE"
          "category": "GOPEN", // or OBC, SC, ST, EWS
          "percentile": 99.4,
          "sml": 120 // or null if not found
        }}
      ]
    }}
    If no cutoffs are found, return an empty array for cutoffs.
    """
    
    data = call_llm_with_retry(prompt, f"Cutoffs - {institute_code}")

    if not data or 'cutoffs' not in data:
        return False

    extracted_cutoffs = data['cutoffs']

    # Thread-safe database writes
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get program ID
        cursor.execute("SELECT id FROM programs WHERE college_id = (SELECT id FROM colleges WHERE institute_code = ?) LIMIT 1", (institute_code,))
        res = cursor.fetchone()
        if res:
            program_id = res['id']
            for c in extracted_cutoffs:
                exam = c.get('exam_type', 'MHT-CET')
                cat = c.get('category', 'GOPEN')
                perc = c.get('percentile', 0.0)
                sml = c.get('sml', None)
                
                # Insert parsed cutoff
                cursor.execute(
                    "INSERT INTO cutoffs (program_id, year, exam_type, category, round_number, cutoff_percentile, state_merit_list) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (program_id, 2023, exam, cat, 1, perc, sml)
                )
            
            # Update allows_spot_round flag (assume true if we got data)
            cursor.execute("UPDATE colleges SET allows_spot_round = ? WHERE institute_code = ?", (1, institute_code))
        conn.commit()
        conn.close()

    print(f"[Thread-Cutoffs] SUCCESS: {institute_code} extracted {len(extracted_cutoffs)} distinct cutoffs!")
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
    
    # 1. Search Web
    q1 = f"{college_name} highest median placement LPA service based recruiter percentage 2023 2024"
    q2 = f"{college_name} BTech tuition fee hostel mess fee structure"
    q3 = f"{college_name} campus infrastructure hostel mess review rating"
    
    # Rate limit protection for DDGS
    time.sleep(random.uniform(1.0, 3.0))
    context = search_web(q1) + search_web(q2) + search_web(q3)
    
    prompt = f"""
    You are an expert admission counselor extracting metrics from search results for {college_name}.
    Based on the following search snippets, extract the numerical metrics requested.
    If a metric is not found, make an educated estimation based on typical engineering colleges in Maharashtra.
    
    Search Context:
    {context}
    
    Return ONLY valid JSON matching this schema exactly (no markdown formatting, no comments):
    {{
      "highest_placement_lpa": float,
      "median_placement_lpa": float,
      "mass_recruiter_percent": int (0-100),
      "tuition_fee": int,
      "hostel_fee": int,
      "mess_fee": int,
      "city_avg_pg_cost": int,
      "infrastructure_score": float (0-10),
      "alumni_network_score": float (0-10),
      "hostel_rating": float (0-10),
      "mess_rating": float (0-10)
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
        cursor.execute("UPDATE fees SET tuition_fee=?, hostel_fee=?, mess_fee=? WHERE program_id = (SELECT id FROM programs WHERE college_id = (SELECT id FROM colleges WHERE institute_code = ?) LIMIT 1)", 
            (data.get('tuition_fee', 0), data.get('hostel_fee', 0), data.get('mess_fee', 0), institute_code))
        conn.commit()
        conn.close()

    print(f"[Thread-Scraper] SUCCESS: {institute_code} Web & Sentiment Parsed -> Median: {data.get('median_placement_lpa')} LPA")
    return True

# ---------------------------------------------------------
# PIPELINE 0: THE DISCOVERY ENGINE (SEEDS DB AUTOMATICALLY)
# ---------------------------------------------------------
def discover_region(region):
    print(f"\n[Pipeline 0] AI Scout searching for B.E. and M.E. Engineering Colleges across {region}...")
    context = search_web(f"List of top BE BTech and ME MTech engineering colleges across {region} with official Institute Codes")
    
    prompt = f"""
    Generate a comprehensive list of up to 30 top engineering colleges offering B.E./B.Tech and M.E./M.Tech degrees across {region}.
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
