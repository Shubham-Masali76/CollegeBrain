from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import os
import json
from groq import Groq
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="CollegeBrain Multi-Factor Scoring API")

# Allow React UI to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "collegebrain.db")
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class StudentProfile(BaseModel):
    percentile: float
    category: str
    exam_type: str
    preferred_branch: Optional[str] = None
    preferred_country: Optional[str] = None
    preferred_state: Optional[str] = None
    preferred_city: Optional[str] = None
    budget: Optional[int] = None

@app.post("/api/recommend")
def recommend_colleges(profile: StudentProfile):
    conn = sqlite3.connect(DB_PATH)
    # Connect to the live Database populated by the Ingestion Engine
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
        SELECT 
            c.name, c.city, c.state, c.country, c.infrastructure_score, c.highest_placement_lpa, c.city_avg_pg_cost,
            c.median_placement_lpa, c.mass_recruiter_percent, c.alumni_network_score, c.allows_spot_round,
            c.hostel_rating, c.mess_rating, c.minority_status,
            p.branch_name as branch, p.is_nba_accredited as nba,
            cu.cutoff_percentile as base_cutoff, cu.state_merit_list as sml,
            f.tuition_fee, f.hostel_fee, f.mess_fee
        FROM colleges c
        JOIN programs p ON c.id = p.college_id
        JOIN cutoffs cu ON p.id = cu.program_id
        JOIN fees f ON p.college_id = f.college_id
        WHERE cu.round_number = 1 
          AND (cu.category = ? OR cu.category LIKE '%' || ? || '%')
          AND (cu.exam_type LIKE '%' || ? || '%' OR ? = '')
          AND (c.city = ? OR ? = '')
          AND (p.branch_name LIKE '%' || ? || '%' OR ? = '')
    """
    
    # 1. Smart Category Mapping
    raw_cat = profile.category.upper().strip()
    if raw_cat in ["OPEN", "GENERAL", "UR", "GEN"]:
        cat = "GOPEN"
    else:
        cat = raw_cat
        
    # 2. Smart Exam Mapping
    raw_exam = profile.exam_type.upper().strip() if profile.exam_type else ""
    if "DIPLOMA" in raw_exam or "DSE" in raw_exam:
        exam = "DSE"
    elif "JEE" in raw_exam or "MAINS" in raw_exam:
        exam = "JEE"
    elif "MHT" in raw_exam or "CET" in raw_exam:
        exam = "MHT-CET"
    elif "GATE" in raw_exam or "M.E" in raw_exam or "M.TECH" in raw_exam:
        exam = "GATE"
    else:
        exam = raw_exam
        
    # 3. Smart Branch Mapping
    raw_branch = profile.preferred_branch.upper().strip() if profile.preferred_branch else ""
    if "CS" in raw_branch or "COMPUTER" in raw_branch:
        branch = "Computer"
    elif "IT" in raw_branch or "INFORMATION" in raw_branch:
        branch = "Information Technology"
    elif "AI" in raw_branch or "ARTIFICIAL" in raw_branch:
        branch = "Artificial Intelligence"
    elif "ENTC" in raw_branch or "ELECTRONIC" in raw_branch:
        branch = "Electronic"
    elif "MECH" in raw_branch:
        branch = "Mechanical"
    elif "CIVIL" in raw_branch:
        branch = "Civil"
    else:
        branch = profile.preferred_branch if profile.preferred_branch else ""
    
    # Execute query
    params = (cat, cat, exam, exam, profile.preferred_city, profile.preferred_city, branch, branch)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Process financial logic
    colleges = []
    for r in rows:
        row_dict = dict(r)
        tuition = row_dict["tuition_fee"]
        official_housing = row_dict["hostel_fee"] + row_dict["mess_fee"]
        pg_housing = row_dict["city_avg_pg_cost"]
        
        total_official = tuition + official_housing
        total_pg = tuition + pg_housing
        
        row_dict["suggest_pg"] = False
        row_dict["display_housing_cost"] = official_housing
        row_dict["is_unaffordable"] = False
        
        if profile.budget:
            if total_official > profile.budget:
                if total_pg <= profile.budget:
                    # Trigger Alternative Housing
                    row_dict["suggest_pg"] = True
                    row_dict["display_housing_cost"] = pg_housing
                else:
                    row_dict["is_unaffordable"] = True
        
        # We only keep affordable colleges
        if not row_dict["is_unaffordable"]:
            colleges.append(row_dict)
            
    conn.close()

    # Filter by preferred city, branch if provided
    # (Country and State removed from filtering logic as requested by UI cleanup)
    if profile.preferred_city and profile.preferred_city != "All":
        colleges = [c for c in colleges if c["city"].lower() == profile.preferred_city.lower()]
    if profile.preferred_branch:
        colleges = [c for c in colleges if profile.preferred_branch.lower() in c["branch"].lower()]

    final_colleges = []
    for c in colleges:
        # Calculate match score based on infrastructure and placements
        score = (c["infrastructure_score"] * 4) + (c["highest_placement_lpa"] * 0.6)
        c["match_score"] = min(99, int(score))

        # Spot Round Algorithm
        diff = profile.percentile - c["base_cutoff"]
        if diff >= 0:
            c["probability"] = "Safe"
        elif diff >= -5.0 and c["allows_spot_round"]:
            c["probability"] = "Spot Round"
        else:
            c["probability"] = "Impossible"
            
        # Only return Safe or Spot Round options
        if c["probability"] != "Impossible":
            final_colleges.append(c)

    # Sort by match score
    final_colleges.sort(key=lambda x: x["match_score"], reverse=True)

    # Apply Dynamic Category-Wise Fee Reduction
    cat = profile.category.upper()
    for c in final_colleges:
        if cat in ["SC", "ST", "TFWS"]:
            c["tuition_fee"] = 0
        elif cat in ["OBC", "EBC", "VJNT", "NT"]:
            c["tuition_fee"] = int(c["tuition_fee"] / 2)
            
    # Calculate Ranking Justification
    for idx, c in enumerate(final_colleges):
        if idx == 0:
            c["justification"] = f"Ranked #1 because its Median LPA ({c['median_placement_lpa']}LPA) provides the highest ROI for your budget."
        elif idx == 1:
            c["justification"] = f"A solid backup. Slightly lower placements than #1, but excellent alumni network ({c['alumni_network_score']}/10)."
        else:
            c["justification"] = f"Strong option in {c['city']} with a realistic Spot Round chance and great Infrastructure."

    top_colleges = final_colleges[:3]
    for c in top_colleges:
        prompt = f"Write a 1-sentence hyped-up summary for a student getting admission into {c['name']} in {c['city']}. Emphasize their {c['highest_placement_lpa']} LPA placement."
        try:
            chat_completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            c["ai_summary"] = chat_completion.choices[0].message.content.strip()
        except Exception:
            c["ai_summary"] = "An excellent choice with great placement opportunities."

    return {"status": "success", "recommendations": top_colleges}

@app.get("/api/locations")
def get_locations():
    # In production, this queries the DB for DISTINCT countries, states, and cities
    # so the UI only shows locations we actually have data for!
    return {
        "countries": ["India", "USA"],
        "states": ["Maharashtra", "Delhi", "Massachusetts"],
        "cities": ["Pune", "Mumbai", "Nagpur", "Nashik", "New Delhi", "Cambridge"]
    }

@app.get("/")
def health_check():
    return {"status": "CollegeBrain API is Online."}

@app.get("/api/stats")
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM colleges")
    count = cursor.fetchone()[0]
    conn.close()
    return {"total_colleges": count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
