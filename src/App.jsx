import { useState, useEffect } from 'react'
import axios from 'axios'
import { Reorder } from 'framer-motion'
import { GraduationCap, MapPin, GripVertical, Download, Shield, ChevronDown } from 'lucide-react'

export default function App() {
  const [percentile, setPercentile] = useState('')
  const [category, setCategory] = useState('')
  const [branch, setBranch] = useState('')
  const [city, setCity] = useState('')
  const [budget, setBudget] = useState('')
  const [isBudgetOpen, setIsBudgetOpen] = useState(false)
  const [colleges, setColleges] = useState([])
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [totalColleges, setTotalColleges] = useState(0)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await axios.get('http://localhost:8000/api/stats')
        setTotalColleges(res.data.total_colleges)
      } catch (e) {
        console.error("Could not fetch stats:", e)
      }
    }
    fetchStats()
  }, [])

  const handleGenerate = async () => {
    setLoading(true)
    try {
      const res = await axios.post('http://localhost:8000/api/recommend', {
        percentile: parseFloat(percentile) || 0,
        category,
        exam_type: "Diploma",
        preferred_branch: branch,
        preferred_city: city,
        budget: budget ? parseInt(budget) : null
      })
      setColleges(res.data.recommendations)
      setHasSearched(true)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen text-white print:bg-white print:text-black p-4 md:p-8 font-sans relative overflow-hidden">
      {/* Ambient Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-cyan-600/20 blur-[120px] rounded-full pointer-events-none animate-float" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[30rem] h-[30rem] bg-blue-600/20 blur-[120px] rounded-full pointer-events-none animate-float" style={{ animationDelay: '2s' }} />
      
      <div className="max-w-4xl mx-auto space-y-10 relative z-10">
        
        {/* Header */}
        <div className="flex items-center space-x-5">
          <div className="p-4 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-2xl shadow-[0_0_30px_rgba(34,211,238,0.3)]">
            <GraduationCap className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-4xl font-extrabold tracking-tight neon-text">CollegeBrain</h1>
            <p className="text-gray-400 font-medium mt-1">The Ultimate 100% Accurate Admission Analyzer</p>
            {totalColleges > 0 && (
              <p className="text-sm font-semibold text-cyan-400/80 mt-1">
                Currently scanning data from {totalColleges.toLocaleString()} top engineering colleges in India!
              </p>
            )}
          </div>
        </div>

        {/* Input Card */}
        <div className="print:hidden glass p-8 rounded-3xl flex flex-col gap-6">
          <div className="flex flex-col md:flex-row gap-6">
            <div className="flex-1 w-full">
              <label className="block text-sm font-semibold text-gray-300 mb-2">Percentile Score</label>
              <input 
                type="number" 
                placeholder="e.g. 95.42"
                value={percentile}
                onChange={(e) => setPercentile(e.target.value)}
                className="w-full glass-input rounded-xl px-4 py-3 text-white placeholder-gray-500"
              />
            </div>
            <div className="flex-1 w-full">
              <label className="block text-sm font-semibold text-gray-300 mb-2">Category</label>
              <input 
                type="text"
                placeholder="e.g. GOPEN or OBC"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full glass-input rounded-xl px-4 py-3 text-white placeholder-gray-500"
              />
            </div>
          </div>
          
          <div className="flex flex-col md:flex-row gap-6 items-end">
            <div className="flex-1 w-full">
              <label className="block text-sm font-semibold text-gray-300 mb-2">Branch / Course</label>
              <input 
                type="text"
                placeholder="e.g. Computer Science"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                className="w-full glass-input rounded-xl px-4 py-3 text-white placeholder-gray-500"
              />
            </div>
            <div className="flex-1 w-full">
              <label className="block text-sm font-semibold text-gray-300 mb-2">Target City</label>
              <input 
                type="text"
                placeholder="e.g. Pune, Mumbai"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full glass-input rounded-xl px-4 py-3 text-white placeholder-gray-500"
              />
            </div>
          </div>

          <div className="flex flex-col md:flex-row gap-6 items-end">
            <div className="flex-1 w-full relative">
              <label className="block text-sm font-semibold text-gray-300 mb-2">Max Budget (Per Year)</label>
              <button 
                type="button"
                onClick={() => setIsBudgetOpen(!isBudgetOpen)}
                className="w-full glass-input rounded-xl px-4 py-3 text-left text-white flex justify-between items-center"
              >
                <span>{budget === "100000" ? "Under ₹1 Lakh/yr" : budget === "150000" ? "Under ₹1.5 Lakh/yr" : budget === "200000" ? "Under ₹2 Lakh/yr" : "No Limit"}</span>
                <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isBudgetOpen ? 'rotate-180' : ''}`} />
              </button>
              
              {isBudgetOpen && (
                <div className="absolute z-20 w-full mt-2 glass border border-cyan-900/30 rounded-xl shadow-2xl overflow-hidden">
                  {[
                    { value: "", label: "No Limit" },
                    { value: "100000", label: "Under ₹1 Lakh/yr" },
                    { value: "150000", label: "Under ₹1.5 Lakh/yr" },
                    { value: "200000", label: "Under ₹2 Lakh/yr" }
                  ].map((opt) => (
                    <div 
                      key={opt.value}
                      onClick={() => { setBudget(opt.value); setIsBudgetOpen(false); }}
                      className="px-4 py-3 hover:bg-cyan-900/40 cursor-pointer transition-colors text-sm text-gray-300 hover:text-white border-b border-white/5 last:border-0"
                    >
                      {opt.label}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <button 
              onClick={handleGenerate}
              disabled={loading || !percentile}
              className="w-full md:w-auto neon-button px-10 py-3 rounded-xl font-bold text-white"
            >
              {loading ? "Analyzing Models..." : "Generate College List"}
            </button>
          </div>
        </div>

        {/* Drag and Drop List */}
        {hasSearched && colleges.length === 0 && (
          <div className="glass p-10 rounded-3xl text-center border-red-500/20">
            <h2 className="text-2xl font-bold text-gray-200">No Colleges Found</h2>
            <p className="text-gray-400 mt-2">We couldn't find any colleges matching your criteria. Try adjusting your budget, percentile, or branch.</p>
          </div>
        )}
        
        {colleges.length > 0 && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold">Your Optimized Preference List</h2>
              <button onClick={() => window.print()} className="print:hidden flex items-center space-x-2 text-sm text-blue-400 hover:text-blue-300 transition-colors">
                <Download className="w-4 h-4" />
                <span>Export PDF for CAP Form</span>
              </button>
            </div>
            <p className="text-sm text-gray-400">Drag and drop to realign your preferences before exporting.</p>
            
            <Reorder.Group axis="y" values={colleges} onReorder={setColleges} className="space-y-6">
              {colleges.map((college, index) => (
                <Reorder.Item 
                  key={college.id} 
                  value={college}
                  className="glass-card print:bg-white print:border-gray-400 print:shadow-none p-6 rounded-2xl flex items-start gap-4 cursor-grab active:cursor-grabbing relative group"
                >
                  <div className="print:hidden mt-8 text-gray-500 group-hover:text-cyan-400 transition-colors">
                    <GripVertical className="w-5 h-5" />
                  </div>
                  
                  <div className="flex-1 space-y-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="text-xs font-bold text-blue-500 mb-1 flex items-center space-x-2">
                          <span>PREFERENCE #{index + 1}</span>
                          {college.nba && <span className="bg-blue-900 text-blue-300 px-2 py-0.5 rounded text-[10px]">🏅 NBA ACCREDITED</span>}
                          {college.probability === 'Spot Round' && <span className="bg-purple-900 text-purple-300 px-2 py-0.5 rounded text-[10px]">🎯 SPOT ROUND CHANCE</span>}
                        </div>
                        <h3 className="text-xl font-bold">{college.name}</h3>
                        <p className="text-gray-400 text-sm mt-1">{college.branch}</p>
                        
                        <p className="text-sm text-gray-300 mt-3 p-4 glass-input rounded-xl border border-white/5">
                          💡 <strong className="text-cyan-400">AI Justification:</strong> {college.justification}
                        </p>
                        
                        {college.suggest_pg && (
                          <div className="mt-3 bg-red-950/40 border border-red-500/30 rounded-xl p-3 text-sm text-red-200">
                            ⚠️ <strong>Hostel Unaffordable:</strong> We suggest renting a local PG/Flat (est. ₹{college.display_housing_cost.toLocaleString()}/yr) to keep total costs under your budget.
                          </div>
                        )}
                      </div>
                      <div className="flex flex-col items-end space-y-3">
                        <div className={`px-4 py-1.5 rounded-full text-sm font-bold border flex items-center space-x-1.5 ${
                          college.probability === 'Safe' 
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-[0_0_15px_rgba(16,185,129,0.3)]' 
                            : 'bg-purple-500/20 text-purple-300 border-purple-500/50 shadow-[0_0_15px_rgba(168,85,247,0.3)]'
                        }`}>
                          <Shield className="w-4 h-4" />
                          <span>{college.probability}</span>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-3 text-right mt-2 glass-input p-4 rounded-xl border border-white/5 w-64">
                          <div className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">Median LPA</div>
                          <div className="text-sm font-bold text-white">{college.median_placement_lpa} LPA</div>
                          
                          <div className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">Hostel Rating</div>
                          <div className="text-sm font-bold text-white">{college.hostel_rating}/10</div>

                          <div className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">Mess Rating</div>
                          <div className="text-sm font-bold text-white">{college.mess_rating}/10</div>

                          <div className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">Minority Quota</div>
                          <div className="text-xs font-bold text-cyan-400">{college.minority_status}</div>
                          
                          <div className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">State Merit List</div>
                          <div className="text-sm font-bold text-gray-300">#{college.sml}</div>
                        </div>

                        <div className="mt-2 text-xs text-cyan-200/60 font-mono text-right">
                          Tuition: ₹{college.tuition_fee.toLocaleString()} (Cat Adjusted)<br/>
                          Housing: ₹{college.display_housing_cost.toLocaleString()}
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2 text-gray-400 text-sm">
                      <MapPin className="w-4 h-4 text-cyan-500" />
                      <span>{college.city}</span>
                      <span className="text-gray-600">•</span>
                      <span>Infrastructure Score: <span className="text-white font-bold">{college.infrastructure_score}/10</span></span>
                    </div>

                    <div className="p-5 glass-input rounded-xl border-l-4 border-l-cyan-500">
                      <p className="text-sm text-gray-200 italic font-medium">"{college.ai_summary}"</p>
                    </div>
                  </div>
                </Reorder.Item>
              ))}
            </Reorder.Group>
          </div>
        )}
      </div>
    </div>
  )
}
