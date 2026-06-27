import { useState } from 'react'
import axios from 'axios'
import { Reorder } from 'framer-motion'
import { GraduationCap, MapPin, GripVertical, Download, Shield, ChevronDown } from 'lucide-react'

export default function App() {
  const [percentile, setPercentile] = useState('')
  const [category, setCategory] = useState('')
  const [branch, setBranch] = useState('')
  const [city, setCity] = useState('')
  const [examType, setExamType] = useState('')
  const [budget, setBudget] = useState('')
  const [isBudgetOpen, setIsBudgetOpen] = useState(false)
  const [colleges, setColleges] = useState([])
  const [loading, setLoading] = useState(false)

  const handleGenerate = async () => {
    setLoading(true)
    try {
      const res = await axios.post('http://localhost:8000/api/recommend', {
        percentile: parseFloat(percentile) || 0,
        category,
        exam_type: examType,
        preferred_branch: branch,
        preferred_city: city,
        budget: budget ? parseInt(budget) : null
      })
      setColleges(res.data.recommendations)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white print:bg-white print:text-black p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex items-center space-x-4">
          <div className="p-3 bg-blue-600 rounded-xl">
            <GraduationCap className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">CollegeBrain</h1>
            <p className="text-gray-400">The Ultimate 100% Accurate Admission Analyzer</p>
          </div>
        </div>

        {/* Input Card */}
        <div className="print:hidden bg-gray-900 border border-gray-800 p-6 rounded-2xl shadow-xl flex flex-col gap-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-gray-400 mb-2">Percentile Score</label>
              <input 
                type="number" 
                placeholder="e.g. 95.42"
                value={percentile}
                onChange={(e) => setPercentile(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-gray-400 mb-2">Category</label>
              <input 
                type="text"
                placeholder="e.g. GOPEN or OBC"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
          </div>
          
          <div className="flex flex-col md:flex-row gap-4 items-end">
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-gray-400 mb-2">Exam Type</label>
              <input 
                type="text"
                placeholder="e.g. MHT-CET, JEE, GATE"
                value={examType}
                onChange={(e) => setExamType(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-gray-400 mb-2">Branch / Course</label>
              <input 
                type="text"
                placeholder="e.g. Computer Science"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
          </div>

          <div className="flex flex-col md:flex-row gap-4 items-end">
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-gray-400 mb-2">Target City</label>
              <input 
                type="text"
                placeholder="e.g. Pune, Mumbai"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <div className="flex-1 w-full relative">
              <label className="block text-sm font-medium text-gray-400 mb-2">Max Budget (Per Year)</label>
              <button 
                type="button"
                onClick={() => setIsBudgetOpen(!isBudgetOpen)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 text-left focus:outline-none focus:border-blue-500 transition-colors flex justify-between items-center"
              >
                <span>{budget === "100000" ? "Under ₹1 Lakh/yr" : budget === "150000" ? "Under ₹1.5 Lakh/yr" : budget === "200000" ? "Under ₹2 Lakh/yr" : "No Limit"}</span>
                <ChevronDown className="w-4 h-4 text-gray-500" />
              </button>
              
              {isBudgetOpen && (
                <div className="absolute z-10 w-full mt-2 bg-gray-900 border border-gray-700 rounded-lg shadow-2xl overflow-hidden">
                  {[
                    { value: "", label: "No Limit" },
                    { value: "100000", label: "Under ₹1 Lakh/yr" },
                    { value: "150000", label: "Under ₹1.5 Lakh/yr" },
                    { value: "200000", label: "Under ₹2 Lakh/yr" }
                  ].map((opt) => (
                    <div 
                      key={opt.value}
                      onClick={() => { setBudget(opt.value); setIsBudgetOpen(false); }}
                      className="px-4 py-3 hover:bg-gray-800 cursor-pointer transition-colors text-sm text-gray-300 hover:text-white"
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
              className="w-full md:w-auto bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-8 py-3 rounded-lg font-semibold transition-all shadow-[0_0_20px_rgba(37,99,235,0.3)]"
            >
              {loading ? "Analyzing..." : "Generate"}
            </button>
          </div>
        </div>

        {/* Drag and Drop List */}
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
            
            <Reorder.Group axis="y" values={colleges} onReorder={setColleges} className="space-y-4">
              {colleges.map((college, index) => (
                <Reorder.Item 
                  key={college.id} 
                  value={college}
                  className="bg-gray-900/50 print:bg-white print:border-gray-400 print:shadow-none backdrop-blur-sm border border-gray-800 p-6 rounded-2xl flex items-start gap-4 cursor-grab active:cursor-grabbing hover:border-gray-700 transition-colors relative group"
                >
                  <div className="print:hidden mt-8 text-gray-600 group-hover:text-gray-400 transition-colors">
                    <GripVertical className="w-5 h-5" />
                  </div>
                  
                  <div className="flex-1 space-y-3">
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="text-xs font-bold text-blue-500 mb-1 flex items-center space-x-2">
                          <span>PREFERENCE #{index + 1}</span>
                          {college.nba && <span className="bg-blue-900 text-blue-300 px-2 py-0.5 rounded text-[10px]">🏅 NBA ACCREDITED</span>}
                          {college.probability === 'Spot Round' && <span className="bg-purple-900 text-purple-300 px-2 py-0.5 rounded text-[10px]">🎯 SPOT ROUND CHANCE</span>}
                        </div>
                        <h3 className="text-xl font-bold">{college.name}</h3>
                        <p className="text-gray-400 text-sm mt-1">{college.branch}</p>
                        
                        <p className="text-sm text-gray-300 mt-2 p-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
                          💡 <strong>AI Justification:</strong> {college.justification}
                        </p>
                        
                        {college.suggest_pg && (
                          <div className="mt-3 bg-red-950/40 border border-red-900/50 rounded-md p-2 text-xs text-red-200">
                            ⚠️ <strong>Hostel Unaffordable:</strong> We suggest renting a local PG/Flat (est. ₹{college.display_housing_cost.toLocaleString()}/yr) to keep total costs under your budget.
                          </div>
                        )}
                      </div>
                      <div className="flex flex-col items-end space-y-2">
                        <div className={`px-3 py-1 rounded-full text-sm font-semibold border flex items-center space-x-1 ${
                          college.probability === 'Safe' 
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                            : 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                        }`}>
                          <Shield className="w-4 h-4" />
                          <span>{college.probability}</span>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-2 text-right mt-2 bg-gray-950 p-2 rounded-lg border border-gray-800 w-56">
                          <div className="text-[10px] text-gray-500 uppercase">Median LPA</div>
                          <div className="text-xs font-bold text-gray-300">{college.median_placement_lpa} LPA</div>
                          
                          <div className="text-[10px] text-gray-500 uppercase">Hostel Rating</div>
                          <div className="text-xs font-bold text-gray-300">{college.hostel_rating}/10</div>

                          <div className="text-[10px] text-gray-500 uppercase">Mess Rating</div>
                          <div className="text-xs font-bold text-gray-300">{college.mess_rating}/10</div>

                          <div className="text-[10px] text-gray-500 uppercase">Minority Quota</div>
                          <div className="text-[9px] font-bold text-blue-400">{college.minority_status}</div>
                          
                          <div className="text-[10px] text-gray-500 uppercase">State Merit List</div>
                          <div className="text-xs font-bold text-gray-400">#{college.sml}</div>
                        </div>

                        <div className="mt-2 text-xs text-gray-500 font-mono text-right">
                          Tuition: ₹{college.tuition_fee.toLocaleString()} (Cat Adjusted)<br/>
                          Housing: ₹{college.display_housing_cost.toLocaleString()}
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2 text-gray-400 text-sm">
                      <MapPin className="w-4 h-4" />
                      <span>{college.city}</span>
                      <span className="text-gray-700">•</span>
                      <span>Infrastructure Score: {college.infrastructure_score}/10</span>
                    </div>

                    <div className="p-4 bg-gray-950/50 rounded-lg border border-gray-800/50">
                      <p className="text-sm text-gray-300 italic">"{college.ai_summary}"</p>
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
