import { useState, useEffect, useRef } from 'react'

const API = 'http://localhost:8000'

const createEmptyRow = () => ({
  extracted: 'Manual Entry',
  rx_qty: '',
  matches: [],
  extractedMatches: [],
  extractedState: null,
  selectedIndex: 0,
  selectedItemCode: null,
  billing: null,
  isManual: true,
  manualQuery: '',
  selectedName: null,
  showDropdown: false,
  highlightedIndex: 0,
  stockWarning: null,
  isUnavailable: false
})

const loadingMessages = [
  "Reading prescription handwriting...",
  "Identifying medicines...",
  "Matching against inventory...",
  "Calculating quantities...",
  "Almost ready..."
]

export default function App() {
  const [imageFile, setImageFile] = useState(null)
  const [image, setImage] = useState(null)
  const [loading, setLoading] = useState(false)
  const [cart, setCart] = useState([createEmptyRow()])
  const [patientName, setPatientName] = useState('')
  const [patientAge, setPatientAge] = useState('')
  const [patientGender, setPatientGender] = useState('')
  const [saleResult, setSaleResult] = useState(null)
  const [sessionTokens, setSessionTokens] = useState(0)
  const [sessionCost, setSessionCost] = useState(0.0)
  const [lastScanMetrics, setLastScanMetrics] = useState(null)
  const [currentTime, setCurrentTime] = useState(new Date())
  const [loadingMsgIndex, setLoadingMsgIndex] = useState(0)

  const fileInputRef = useRef(null)

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // Rotate loading messages every 2 seconds while loading
  useEffect(() => {
    if (!loading) return
    setLoadingMsgIndex(0)
    const interval = setInterval(() => {
      setLoadingMsgIndex(prev => (prev + 1) % loadingMessages.length)
    }, 2000)
    return () => clearInterval(interval)
  }, [loading])

  function handleImageUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setImageFile(file)
    setImage(URL.createObjectURL(file))
    setCart([createEmptyRow()])
    setSaleResult(null)
  }

  async function searchMedicine(name) {
    try {
      const res = await fetch(`${API}/search?query=${encodeURIComponent(name)}`)
      const data = await res.json()
      return data.results || []
    } catch (err) {
      console.error("Search failed", err)
      return []
    }
  }

  async function getBilling(item_code, rx_qty) {
    try {
      const res = await fetch(`${API}/billing?item_code=${item_code}&rx_qty=${rx_qty}`)
      const data = await res.json()
      return data
    } catch (err) {
      console.error("Billing fetch failed", err)
      return null
    }
  }

  async function fetchBillingWithCap(itemCode, qty) {
    const billing = await getBilling(itemCode, qty)

    if (!billing?.medicine || !billing?.billing) {
      return { billing, rx_qty: qty, stockWarning: null, isUnavailable: false }
    }

    const stock = billing.medicine.stock
    const packSize = billing.medicine.pack_size
    const packsNeeded = billing.billing.packs_needed

    if (stock === 0) {
      return {
        billing,
        rx_qty: qty,
        stockWarning: 'Out of stock — not included in bill',
        isUnavailable: true
      }
    }

    if (packsNeeded > stock) {
      const maxQty = stock * packSize
      const cappedBilling = await getBilling(itemCode, maxQty)
      return {
        billing: cappedBilling,
        rx_qty: maxQty,
        stockWarning: `Only ${stock} pack${stock !== 1 ? 's' : ''} in stock — qty adjusted to ${maxQty}`,
        isUnavailable: false
      }
    }

    return { billing, rx_qty: qty, stockWarning: null, isUnavailable: false }
  }

  async function handleExtract() {
    if (!imageFile) return
    setLoading(true)
    setCart([])
    setSaleResult(null)

    try {
      const formData = new FormData()
      formData.append('file', imageFile)
      const res = await fetch(`${API}/extract`, { method: 'POST', body: formData })
      const data = await res.json()

      if (data.metrics) {
        setLastScanMetrics(data.metrics)
        setSessionTokens(prev => prev + (data.metrics.total_tokens || 0))
        setSessionCost(prev => prev + (data.metrics.cost_inr || 0))
      }

      const extracted = data.extracted_data
      setPatientName(extracted.patient_name === 'Unknown' ? '' : extracted.patient_name)
      setPatientAge(extracted.age || '')

      const validGenders = ['Male', 'Female', 'Other']
      setPatientGender(validGenders.includes(extracted.gender) ? extracted.gender : '')

      const cartItems = await Promise.all(
        extracted.medicines.map(async (med) => {
          const matches = await searchMedicine(med.name)
          const itemCode = matches.length > 0 ? matches[0].item_code : null

          let stockState = { billing: null, rx_qty: med.suggested_qty || 1, stockWarning: null, isUnavailable: false }
          if (itemCode) {
            stockState = await fetchBillingWithCap(itemCode, med.suggested_qty || 1)
          }

          return {
            extracted: med.name,
            rx_qty: stockState.rx_qty,
            matches,
            extractedMatches: matches,
            extractedState: { ...stockState, selectedItemCode: itemCode },
            selectedIndex: 0,
            selectedItemCode: itemCode,
            billing: stockState.billing,
            isManual: false,
            manualQuery: '',
            selectedName: null,
            showDropdown: false,
            highlightedIndex: 0,
            stockWarning: stockState.stockWarning,
            isUnavailable: stockState.isUnavailable
          }
        })
      )

      setCart(cartItems.length > 0 ? cartItems : [createEmptyRow()])
    } catch (err) {
      console.error('Extraction failed:', err)
      setCart([createEmptyRow()])
    } finally {
      setLoading(false)
    }
  }

  function addManualRow() {
    setCart(prev => [...prev, createEmptyRow()])
  }

  function switchToManual(i) {
    setCart(prev => prev.map((it, idx) =>
      idx === i ? {
        ...it,
        isManual: true,
        manualQuery: '',
        selectedName: null,
        selectedItemCode: null,
        matches: [],
        billing: null,
        showDropdown: false,
        rx_qty: '',
        stockWarning: null,
        isUnavailable: false
      } : it
    ))
  }

  function switchToAuto(i) {
    setCart(prev => prev.map((it, idx) => {
      if (idx !== i) return it
      const state = it.extractedState
      if (!state) return it
      return {
        ...it,
        isManual: false,
        manualQuery: '',
        selectedName: null,
        selectedItemCode: state.selectedItemCode,
        matches: it.extractedMatches,
        billing: state.billing,
        selectedIndex: 0,
        showDropdown: false,
        rx_qty: state.rx_qty,
        stockWarning: state.stockWarning,
        isUnavailable: state.isUnavailable
      }
    }))
  }

  async function updateManualSearch(i, query) {
    setCart(prev => prev.map((it, idx) =>
      idx === i ? {
        ...it,
        manualQuery: query,
        selectedName: null,
        billing: null,
        showDropdown: true,
        highlightedIndex: 0,
        stockWarning: null,
        isUnavailable: false
      } : it
    ))

    if (query.length < 2) {
      setCart(prev => prev.map((it, idx) =>
        idx === i ? { ...it, matches: [], showDropdown: false } : it
      ))
      return
    }

    const matches = await searchMedicine(query)
    setCart(prev => prev.map((it, idx) =>
      idx === i ? { ...it, matches, showDropdown: true } : it
    ))
  }

  function handleKeyDown(e, i) {
    const item = cart[i]
    if (!item.showDropdown || item.matches.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setCart(prev => prev.map((it, idx) =>
        idx === i ? { ...it, highlightedIndex: Math.min(it.highlightedIndex + 1, it.matches.length - 1) } : it
      ))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCart(prev => prev.map((it, idx) =>
        idx === i ? { ...it, highlightedIndex: Math.max(it.highlightedIndex - 1, 0) } : it
      ))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      selectManualMatch(i, item.highlightedIndex)
    } else if (e.key === 'Escape') {
      setCart(prev => prev.map((it, idx) =>
        idx === i ? { ...it, showDropdown: false } : it
      ))
    }
  }

  async function selectManualMatch(i, matchIndex) {
    const item = cart[i]
    const match = item.matches[matchIndex]
    if (!match) return

    const qty = item.rx_qty || 1
    const displayText = match.matched_text

    setCart(prev => prev.map((it, idx) =>
      idx === i ? {
        ...it,
        selectedIndex: matchIndex,
        selectedItemCode: match.item_code,
        selectedName: displayText,
        manualQuery: displayText,
        matches: [],
        showDropdown: false,
        rx_qty: qty
      } : it
    ))

    const stockState = await fetchBillingWithCap(match.item_code, qty)
    setCart(prev => prev.map((it, idx) =>
      idx === i ? {
        ...it,
        billing: stockState.billing,
        rx_qty: stockState.rx_qty,
        stockWarning: stockState.stockWarning,
        isUnavailable: stockState.isUnavailable
      } : it
    ))
  }

  function clearManualSelection(i) {
    setCart(prev => prev.map((it, idx) =>
      idx === i ? {
        ...it,
        manualQuery: '',
        selectedName: null,
        selectedItemCode: null,
        billing: null,
        matches: [],
        showDropdown: false,
        rx_qty: '',
        stockWarning: null,
        isUnavailable: false
      } : it
    ))
  }

  async function updateSelection(i, newIndex) {
    const item = cart[i]
    const match = item.matches[newIndex]
    const qty = item.rx_qty || 1

    setCart(prev => prev.map((it, idx) =>
      idx === i ? { ...it, selectedIndex: newIndex, selectedItemCode: match.item_code } : it
    ))

    const stockState = await fetchBillingWithCap(match.item_code, qty)
    setCart(prev => prev.map((it, idx) =>
      idx === i ? {
        ...it,
        billing: stockState.billing,
        rx_qty: stockState.rx_qty,
        stockWarning: stockState.stockWarning,
        isUnavailable: stockState.isUnavailable
      } : it
    ))
  }

  async function updateQty(i, value) {
    const newQty = value === '' ? '' : parseInt(value)

    setCart(prev => prev.map((it, idx) =>
      idx === i ? { ...it, rx_qty: newQty } : it
    ))

    const item = cart[i]
    if (newQty > 0 && item.selectedItemCode) {
      const stockState = await fetchBillingWithCap(item.selectedItemCode, newQty)
      setCart(prev => prev.map((it, idx) =>
        idx === i ? {
          ...it,
          billing: stockState.billing,
          rx_qty: stockState.rx_qty,
          stockWarning: stockState.stockWarning,
          isUnavailable: stockState.isUnavailable
        } : it
      ))
    }
  }

  function removeRow(i) {
    setCart(prev => {
      const newCart = prev.filter((_, idx) => idx !== i)
      return newCart.length === 0 ? [createEmptyRow()] : newCart
    })
  }

  function resetTerminal() {
    setCart([createEmptyRow()])
    setSaleResult(null)
    setImage(null)
    setImageFile(null)
    setPatientName('')
    setPatientAge('')
    setPatientGender('')
    setLastScanMetrics(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const grandTotal = cart.reduce((sum, item) =>
    item.isUnavailable ? sum : sum + (item.billing?.billing?.line_total || 0), 0
  )

  const validItemCount = cart.filter(item => !item.isUnavailable && item.billing?.billing).length
  const hasBillableItems = validItemCount > 0

  async function handleConfirmSale() {
    const billingItems = cart
      .filter(item => item.billing?.billing && !item.isUnavailable)
      .map(item => ({
        item_code: item.selectedItemCode,
        packs_needed: item.billing.billing.packs_needed,
        billed_qty: item.billing.billing.billed_qty,
        line_total: item.billing.billing.line_total
      }))

    try {
      const res = await fetch(`${API}/confirm-sale`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_name: patientName || 'Unknown',
          age: parseInt(patientAge) || 0,
          gender: patientGender || 'Unknown',
          grand_total: grandTotal,
          billing_items: billingItems
        })
      })
      const data = await res.json()
      setSaleResult(data)
    } catch (err) {
      console.error("Sale failed", err)
    }
  }

  const timeString = currentTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const dateString = currentTime.toLocaleDateString('en-US', { weekday: 'short', month: 'long', day: 'numeric', year: 'numeric' })

  return (
    <div className="h-screen bg-[#F4F5F7] flex flex-col overflow-hidden font-sans text-slate-800">

      {/* Header */}
      <div className="bg-white px-8 py-4 flex items-center justify-between border-b border-slate-200 shadow-sm relative z-20">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600 text-white p-2.5 rounded-xl shadow-md shadow-indigo-200">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight leading-none mb-1">PharmaPOS</h1>
            <p className="text-indigo-600 text-[10px] font-bold uppercase tracking-widest">Prescription Intelligence</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-lg font-bold text-slate-800 tracking-wide">{timeString}</p>
          <p className="text-sm font-medium text-slate-500">{dateString}</p>
        </div>
      </div>

      {/* Main layout */}
      <div className="flex flex-1 gap-0 overflow-hidden">

        {/* LEFT PANEL */}
        <div className="w-[20%] bg-[#151722] border-r border-[#242736] p-7 flex flex-col gap-6 overflow-y-auto relative z-10 shadow-[4px_0_24px_rgba(0,0,0,0.05)]">
          <h2 className="font-bold text-slate-300 uppercase tracking-widest text-xs flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.8)]"></span>
            Upload Prescription
          </h2>

          <input
            type="file"
            accept="image/*"
            ref={fileInputRef}
            onChange={handleImageUpload}
            className="block w-full text-xs text-slate-400 file:mr-4 file:py-3 file:px-5 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-indigo-500/20 file:text-indigo-400 hover:file:bg-indigo-500/30 file:transition-colors file:cursor-pointer cursor-pointer bg-[#1C1F2E] border border-[#2D3142] rounded-xl transition-all focus:outline-none focus:border-indigo-500"
          />

          {image && (
            <div className="border border-[#2D3142] p-1.5 rounded-2xl bg-[#1C1F2E] shadow-inner">
              <img src={image} alt="Preview" className="w-full rounded-xl object-contain max-h-56 bg-slate-50" />
            </div>
          )}

          <button
            onClick={handleExtract}
            disabled={!imageFile || loading}
            className="w-full bg-indigo-600 text-white font-bold py-3.5 rounded-xl disabled:opacity-40 disabled:hover:bg-indigo-600 hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-900/30 text-sm tracking-wide flex justify-center items-center gap-2"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing AI...
              </span>
            ) : '🔍 Extract Data'}
          </button>

          {lastScanMetrics && (
            <div className="bg-[#1C1F2E] border border-[#2D3142] rounded-xl p-5 mt-auto">
              <h3 className="font-bold text-[10px] text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Token Metrics
              </h3>
              <div className="flex justify-between items-center mb-2.5 text-xs">
                <span className="text-slate-400 font-medium">This Scan</span>
                <span className="font-bold text-slate-200">
                  {lastScanMetrics.total_tokens?.toLocaleString()} tok
                  <span className="text-slate-600 mx-1">|</span>
                  <span className="text-indigo-400 font-mono">₹{lastScanMetrics.cost_inr?.toFixed(4)}</span>
                </span>
              </div>
              <div className="flex justify-between items-center border-t border-[#2D3142] pt-2.5 text-xs">
                <span className="text-slate-400 font-medium">Session Total</span>
                <span className="font-black text-white">
                  {sessionTokens.toLocaleString()} tok
                  <span className="text-slate-600 mx-1">|</span>
                  <span className="text-emerald-400 font-mono text-sm">₹{sessionCost.toFixed(4)}</span>
                </span>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT PANEL */}
        <div className="flex-1 p-8 relative flex flex-col overflow-hidden">

          {/* ── AI LOADING PANEL ── */}
          {loading && (
            <div className="flex-1 flex flex-col items-center justify-center gap-10">

              {/* Orbiting spinner — like a radar dish scanning for data */}
              <div className="relative w-28 h-28 flex items-center justify-center">
                {/* Center icon */}
                <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center shadow-xl shadow-indigo-900/40 z-10">
                  <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                {/* Inner ring */}
                <div className="absolute inset-0 rounded-full border-4 border-indigo-500/20 border-t-indigo-500 animate-spin" />
                {/* Outer ring — spins the other way, like two gears */}
                <div
                  className="absolute -inset-4 rounded-full border-2 border-indigo-400/10 border-t-indigo-400/50 animate-spin"
                  style={{ animationDuration: '3s', animationDirection: 'reverse' }}
                />
              </div>

              {/* Status message — rotates every 2s */}
              <div className="text-center">
                <p className="text-xl font-bold text-slate-700 transition-all duration-500 min-h-[28px]">
                  {loadingMessages[loadingMsgIndex]}
                </p>
                <p className="text-sm text-slate-400 mt-2 font-medium">Powered by Gemini AI</p>
              </div>

              {/* Skeleton rows — like scaffolding showing where results will appear */}
              <div className="w-full max-w-3xl space-y-3">
                {[1, 2, 3].map(n => (
                  <div
                    key={n}
                    className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm grid grid-cols-12 gap-3 items-center"
                    style={{ opacity: 1 - (n - 1) * 0.2 }}
                  >
                    <div className="col-span-4 space-y-2">
                      <div className="h-2.5 bg-slate-200 rounded animate-pulse w-1/3" />
                      <div className="h-8 bg-slate-100 rounded-lg animate-pulse" />
                    </div>
                    <div className="col-span-2">
                      <div className="h-8 bg-slate-100 rounded-lg animate-pulse" />
                    </div>
                    <div className="col-span-1">
                      <div className="h-8 bg-slate-100 rounded-lg animate-pulse" />
                    </div>
                    <div className="col-span-2 flex flex-col items-center gap-1">
                      <div className="h-4 bg-slate-200 rounded animate-pulse w-8" />
                      <div className="h-2.5 bg-slate-100 rounded animate-pulse w-12" />
                    </div>
                    <div className="col-span-2">
                      <div className="h-4 bg-slate-200 rounded animate-pulse w-16 ml-auto" />
                    </div>
                    <div className="col-span-1">
                      <div className="h-8 w-8 bg-slate-100 rounded-lg animate-pulse mx-auto" />
                    </div>
                  </div>
                ))}
              </div>

            </div>
          )}

          {/* Sale success */}
          {!loading && saleResult?.success && (
            <div className="bg-white border border-emerald-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-3xl p-12 text-center mb-6 max-w-lg mx-auto mt-12">
              <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-10 h-10 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-3xl font-black text-slate-800 mb-2">Sale Complete</h2>
              <p className="text-slate-500 font-medium mb-6">Receipt #{saleResult.bill_id}</p>
              <div className="bg-slate-50 rounded-2xl py-6 px-4 mb-8">
                <p className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Amount Paid</p>
                <p className="text-5xl font-black text-emerald-600">₹{grandTotal.toFixed(2)}</p>
              </div>
              <button
                onClick={resetTerminal}
                className="w-full bg-emerald-600 text-white px-8 py-4 rounded-xl font-bold hover:bg-emerald-500 shadow-lg shadow-emerald-600/30 transition-all text-lg"
              >
                Start New Sale
              </button>
            </div>
          )}

          {/* Sale failure */}
          {!loading && saleResult && !saleResult.success && (
            <div className="bg-white border-l-4 border-l-rose-500 shadow-md rounded-2xl p-6 mb-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="bg-rose-100 p-2 rounded-lg">
                  <svg className="w-6 h-6 text-rose-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <h2 className="text-lg font-bold text-slate-800">Transaction Failed: Insufficient Stock</h2>
              </div>
              <div className="space-y-2 mb-5 pl-12">
                {saleResult.details?.map((item, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span className="font-bold text-slate-700">{item.product_name}</span>
                    <span className="text-slate-400">—</span>
                    <span className="text-rose-600 font-medium">
                      Need {item.required} <span className="text-rose-400">/</span> Have {item.available}
                    </span>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setSaleResult(null)}
                className="ml-12 bg-white border border-slate-200 text-slate-600 px-6 py-2.5 rounded-xl text-sm font-bold hover:bg-slate-50 hover:text-slate-900 shadow-sm transition-colors"
              >
                Go Back & Edit Cart
              </button>
            </div>
          )}

          {/* Patient info + cart */}
          {!loading && cart.length > 0 && !saleResult?.success && (
            <div className="flex-1 flex flex-col overflow-hidden">

              {/* Patient Info + Summary */}
              <div className="bg-white px-5 py-3 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between mb-4">

                {/* Left Section */}
                <div className="flex items-center gap-5 flex-1 pr-6 border-r border-slate-100">

                  {/* Name */}
                  <div className="flex items-center gap-2 flex-1">
                    <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                      Name
                    </label>

                    <input
                      value={patientName}
                      onChange={e => setPatientName(e.target.value)}
                      placeholder="Walk-in Patient"
                      className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm font-semibold text-slate-800 focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none transition-all"
                    />
                  </div>

                  {/* Age */}
                  <div className="flex items-center gap-2">
                    <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                      Age
                    </label>

                    <input
                      value={patientAge}
                      onChange={e => {
                        const val = e.target.value
                        if (val === '' || Number(val) >= 0) setPatientAge(val)
                      }}
                      type="number"
                      min="0"
                      className="w-20 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm font-semibold text-slate-800 focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none transition-all"
                    />
                  </div>

                  {/* Gender */}
                  <div className="flex items-center gap-2">
                    <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                      Gender
                    </label>

                    <select
                      value={patientGender}
                      onChange={e => setPatientGender(e.target.value)}
                      className="w-32 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm font-semibold text-slate-800 focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none appearance-none transition-all"
                    >
                      <option value="">Select</option>
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>

                </div>

                {/* Right Section - Summary */}
                <div className="pl-6 min-w-[190px] bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-xl px-4 py-3">

                  <div className="flex justify-between items-center">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      Grand Total:
                    </span>

                    <span className="text-1xl font-black text-emerald-600">
                      ₹{grandTotal.toFixed(2)}
                    </span>
                  </div>

                  <div className="flex justify-between items-center mt-1">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      Items:
                    </span>

                    <span className="text-lg font-black text-slate-800">
                      {validItemCount}
                    </span>
                  </div>

                </div>

              </div>

              {/* Table header */}
              <div className="grid grid-cols-12 gap-3 px-5 py-3 text-[10px] font-extrabold text-slate-400 uppercase tracking-widest border-b border-slate-200 mb-3 bg-white rounded-xl shadow-sm flex-shrink-0">
                <div className="col-span-4">Medicine</div>
                <div className="col-span-2 text-center">Qty</div>
                <div className="col-span-1 text-center">Pack</div>
                <div className="col-span-2 text-center">Billable Packs</div>
                <div className="col-span-2 text-right">Line Total</div>
                <div className="col-span-1"></div>
              </div>

              {/* Cart rows */}
              <div className="overflow-y-auto flex-1 pr-2 pb-28 space-y-3">
                {cart.map((item, i) => (
                  <div
                    key={i}
                    className={`grid grid-cols-12 gap-3 items-center rounded-xl p-3.5 shadow-sm border transition-all duration-200 ${
                      item.isUnavailable
                        ? 'bg-slate-50/50 border-slate-200 opacity-60'
                        : 'bg-white border-slate-200 hover:border-indigo-300 hover:shadow-md'
                    }`}
                  >
                    <div className="col-span-4">
                      {item.isManual ? (
                        <div className="relative">
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 border border-amber-200/50 text-[9px] font-black px-2 py-0.5 rounded uppercase tracking-wider">
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                              {item.extracted === 'Manual Entry' ? 'Manual Add' : 'Override'}
                            </span>
                            {item.extractedMatches?.length > 0 && (
                              <button
                                onClick={() => switchToAuto(i)}
                                className="text-[10px] text-indigo-600 hover:bg-indigo-50 font-bold border border-transparent hover:border-indigo-200 rounded px-2 py-1 transition-colors uppercase tracking-wide"
                              >
                                ↩ Restore AI
                              </button>
                            )}
                          </div>
                          <div className="flex items-center border border-slate-200 rounded-lg overflow-hidden focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-100 bg-slate-50 transition-all">
                            <input
                              value={item.manualQuery}
                              onChange={e => updateManualSearch(i, e.target.value)}
                              onKeyDown={e => handleKeyDown(e, i)}
                              placeholder="Search inventory..."
                              className="flex-1 px-3 py-2 text-sm font-semibold text-slate-800 bg-transparent focus:outline-none placeholder:font-medium placeholder:text-slate-400"
                            />
                            {item.selectedName && (
                              <button onClick={() => clearManualSelection(i)} className="px-3 text-slate-400 hover:text-rose-500 transition-colors">
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                              </button>
                            )}
                          </div>
                          {item.showDropdown && item.matches.length > 0 && (
                            <div className="absolute z-20 w-full bg-white border border-slate-200 rounded-xl shadow-xl mt-1.5 overflow-hidden py-1.5">
                              {item.matches.map((match, j) => (
                                <div
                                  key={j}
                                  onClick={() => selectManualMatch(i, j)}
                                  onMouseEnter={() => setCart(prev => prev.map((it, idx) => idx === i ? { ...it, highlightedIndex: j } : it))}
                                  className={`px-4 py-2.5 text-sm cursor-pointer border-b border-slate-50 last:border-0 ${
                                    item.highlightedIndex === j ? 'bg-indigo-50 text-indigo-800 font-bold' : 'hover:bg-slate-50 text-slate-700 font-medium'
                                  }`}
                                >
                                  {match.matched_text}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-700 border border-indigo-100/50 text-[9px] font-black px-2 py-0.5 rounded uppercase tracking-wider">
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                              {item.extracted}
                            </span>
                            <button
                              onClick={() => switchToManual(i)}
                              className="text-[10px] text-slate-500 hover:bg-slate-100 font-bold border border-transparent hover:border-slate-200 rounded px-2 py-1 transition-colors uppercase tracking-wide"
                            >
                              Edit
                            </button>
                          </div>
                          <select
                            value={item.selectedIndex}
                            onChange={e => updateSelection(i, parseInt(e.target.value))}
                            disabled={item.isUnavailable}
                            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-semibold focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 bg-slate-50 text-slate-800 disabled:bg-slate-100 disabled:text-slate-400 transition-all cursor-pointer"
                          >
                            {item.matches.map((match, j) => (
                              <option key={j} value={j}>{match.matched_text}</option>
                            ))}
                          </select>
                        </div>
                      )}

                      {item.stockWarning && !item.isUnavailable && (
                        <div className="mt-2 flex items-start gap-1.5 bg-amber-50 border border-amber-100 px-2.5 py-1.5 rounded-lg">
                          <svg className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                          <p className="text-[11px] text-amber-700 font-semibold leading-tight">{item.stockWarning}</p>
                        </div>
                      )}

                      {item.isUnavailable && (
                        <div className="mt-2 flex items-center gap-2">
                          <span className="text-[10px] text-rose-600 font-black bg-rose-50 border border-rose-100 px-2 py-0.5 rounded uppercase tracking-wider">Out of Stock</span>
                          <span className="text-[11px] text-slate-400 font-medium italic">Removed from bill</span>
                        </div>
                      )}
                    </div>

                    <div className="col-span-2">
                      <input
                        type="number"
                        min="1"
                        value={item.rx_qty}
                        onChange={e => updateQty(i, e.target.value)}
                        placeholder="Qty"
                        disabled={item.isUnavailable}
                        className="w-full border border-slate-200 rounded-lg px-2 py-2 text-sm font-bold text-center focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 bg-slate-50 text-slate-800 disabled:bg-slate-100 disabled:text-slate-400 transition-all"
                      />
                    </div>

                    <div className="col-span-1 text-sm font-semibold text-slate-500 text-center bg-slate-50 border border-slate-100 py-1.5 rounded-lg">
                      {item.billing?.medicine?.pack_size ?? '—'}
                    </div>

                    <div className="col-span-2 text-center flex flex-col justify-center items-center">
                      <span className={`text-base font-black ${item.isUnavailable ? 'text-slate-300' : 'text-slate-800'}`}>
                        {item.isUnavailable ? '—' : (item.billing?.billing?.packs_needed ?? '—')}
                      </span>
                      {typeof item.billing?.medicine?.stock === 'number' && (
                        <span className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mt-0.5">
                          In Stock: {item.billing.medicine.stock}
                        </span>
                      )}
                    </div>

                    <div className={`col-span-2 text-lg font-black text-right tracking-tight ${item.isUnavailable ? 'text-slate-300' : 'text-slate-800'}`}>
                      {item.isUnavailable ? '—' : item.billing?.billing?.line_total ? `₹${item.billing.billing.line_total.toFixed(2)}` : '—'}
                    </div>

                    <div className="col-span-1 text-center">
                      <button
                        onClick={() => removeRow(i)}
                        className="w-8 h-8 rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600 flex items-center justify-center mx-auto transition-colors"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Fixed bottom action bar */}
              <div className="absolute bottom-0 left-8 right-8 pb-8 pt-6 bg-gradient-to-t from-slate-50 via-slate-50 to-transparent z-10 pointer-events-none">
                <div className="bg-white p-4 rounded-2xl shadow-[0_-8px_30px_rgb(0,0,0,0.04)] border border-slate-200 flex justify-between items-center pointer-events-auto">
                  <button
                    onClick={addManualRow}
                    className="text-sm text-indigo-600 font-bold hover:bg-indigo-50 px-5 py-2.5 rounded-xl transition-colors flex items-center gap-2 border border-transparent hover:border-indigo-100"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M12 4v16m8-8H4" /></svg>
                    Add Row
                  </button>
                  <button
                    onClick={handleConfirmSale}
                    disabled={!hasBillableItems}
                    className="font-black text-base px-10 py-4 rounded-xl transition-all shadow-md bg-emerald-600 text-white hover:bg-emerald-500 hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none flex items-center gap-3 tracking-wide"
                  >
                    Confirm Sale
                    <span className="w-1.5 h-1.5 bg-white/40 rounded-full"></span>
                    ₹{grandTotal.toFixed(2)}
                  </button>
                </div>
              </div>

            </div>
          )}

        </div>
      </div>
    </div>
  )
}