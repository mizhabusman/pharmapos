import { useState, useEffect, useRef } from 'react'
import Login from './Login'
import { LogoLockup } from './Logo'
import SelectField from './SelectField'
import { authFetch, getToken, logout } from './auth'

// API base URL — set VITE_API_URL in a .env file for production hosting.
// Falls back to the local dev server. Trailing slashes are trimmed.
const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

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

// A row is "empty" when the user hasn't put anything in it yet — no medicine
// selected, nothing typed, no qty. (AI-extracted rows are never empty.)
const isRowEmpty = (item) =>
  item.isManual && !item.selectedItemCode && !item.manualQuery && !item.rx_qty

// A manual row with no committed medicine is still open for input — it IS the
// entry point, however much has been typed in it. A new phantom is only owed
// once this row commits (medicine selected), which is what stops "type one
// letter per row" from spawning endless rows.
const isEntryRow = (item) => item.isManual && !item.selectedItemCode

// Phantom-row invariant: the cart always ends with exactly ONE uncommitted
// manual row that acts as the entry point for the next item (standard
// billing-grid pattern). Appends one when the last row is committed;
// collapses a redundant trailing empty when the row before it can already
// serve as the entry point (only ever pops the final row, so focus is safe).
const withPhantomRow = (rows) => {
  const next = [...rows]
  while (next.length >= 2 && isRowEmpty(next[next.length - 1]) && isEntryRow(next[next.length - 2])) {
    next.pop()
  }
  if (next.length === 0 || !isEntryRow(next[next.length - 1])) {
    next.push(createEmptyRow())
  }
  return next
}

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
  const [errorMsg, setErrorMsg] = useState(null)
  const [token, setTokenState] = useState(getToken())

  const fileInputRef = useRef(null)
  const rowsScrollRef = useRef(null)
  const prevRowCount = useRef(1) // matches the initial single-phantom cart

  // When committing a medicine spawns the next phantom row below the fold,
  // scroll it into view. Only fires when exactly ONE row was appended — a
  // full cart rebuild (AI extraction) must not yank the view to the bottom.
  useEffect(() => {
    const prev = prevRowCount.current
    prevRowCount.current = cart.length
    if (cart.length !== prev + 1) return
    const el = rowsScrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    // The billing response re-renders the committed row a moment later, which
    // aborts an in-flight smooth scroll (Chrome). Snap the remaining distance
    // if that happened.
    const settle = setTimeout(() => {
      if (el.scrollTop + el.clientHeight < el.scrollHeight - 4) {
        el.scrollTo({ top: el.scrollHeight })
      }
    }, 450)
    return () => clearTimeout(settle)
  }, [cart.length])

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // If any request comes back 401, auth.js clears the token and fires this
  // event — drop back to the login screen.
  useEffect(() => {
    const onUnauthorized = () => setTokenState(null)
    window.addEventListener('pharmapos:unauthorized', onUnauthorized)
    return () => window.removeEventListener('pharmapos:unauthorized', onUnauthorized)
  }, [])

  function handleLogout() {
    logout()
    setTokenState(null)
  }

  // Rotate loading messages every 2 seconds while loading.
  // (The index is reset to 0 in handleExtract when loading begins, so we
  // don't call setState directly in the effect body.)
  useEffect(() => {
    if (!loading) return
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
    // Deliberately leave the cart alone — anything entered manually before
    // scanning must survive (extraction merges rather than replaces).
    setSaleResult(null)
    setErrorMsg(null)
  }

  async function searchMedicine(name) {
    try {
      const res = await authFetch(`${API}/search?query=${encodeURIComponent(name)}`)
      const data = await res.json()
      return data.results || []
    } catch (err) {
      console.error("Search failed", err)
      return []
    }
  }

  async function getBilling(item_code, rx_qty) {
    try {
      const res = await authFetch(`${API}/billing?item_code=${item_code}&rx_qty=${rx_qty}`)
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

  // mode controls how a scan merges with what's already in the cart. Each
  // extracted (AI) row carries a `scanBatch` number so scans stay separable:
  //   'replace' — re-scan of the LAST prescription: drop only the most recent
  //               scan's AI rows (earlier scans + manual rows are kept), then
  //               add the fresh rows in that batch's place.
  //   'append'  — a DIFFERENT prescription for the same bill: keep everything
  //               already there (manual + all earlier AI rows) and add the new
  //               AI rows after it as a new batch.
  // Patient name/age/gender are fill-if-empty in both modes (earliest wins).
  async function handleExtract(mode = 'replace') {
    if (!imageFile) return
    setLoading(true)
    setLoadingMsgIndex(0)
    setSaleResult(null)
    setErrorMsg(null)

    try {
      const formData = new FormData()
      formData.append('file', imageFile)
      const res = await authFetch(`${API}/extract`, { method: 'POST', body: formData })
      const data = await res.json()

      if (!res.ok) {
        throw new Error(data?.detail?.message || 'Prescription extraction failed')
      }

      if (data.metrics) {
        setLastScanMetrics(data.metrics)
        setSessionTokens(prev => prev + (data.metrics.total_tokens || 0))
        setSessionCost(prev => prev + (data.metrics.cost_inr || 0))
      }

      const extracted = data.extracted_data
      // Manually entered patient details always win — AI only fills the gaps.
      setPatientName(prev => prev || (extracted.patient_name === 'Unknown' ? '' : extracted.patient_name))
      setPatientAge(prev => prev || (extracted.age || ''))

      const validGenders = ['Male', 'Female', 'Other']
      setPatientGender(prev => prev || (validGenders.includes(extracted.gender) ? extracted.gender : ''))

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

      // Merge, never wipe. Manual rows (incl. AI rows the user overrode) always
      // survive. For AI rows we look at their scanBatch:
      //   - append  → keep every batch; the new rows form the next batch.
      //   - replace → drop only the most recent batch (redo the last scan);
      //               the new rows take that same batch number.
      // Kept rows stay first; the fresh rows follow. The empty phantom row is
      // dropped here and re-added by withPhantomRow.
      setCart(prev => {
        const aiBatches = prev
          .filter(row => !row.isManual && !isRowEmpty(row))
          .map(row => row.scanBatch || 1)
        const maxBatch = aiBatches.length ? Math.max(...aiBatches) : 0
        const targetBatch = mode === 'append' ? maxBatch + 1 : Math.max(maxBatch, 1)

        const kept = prev.filter(row => {
          if (isRowEmpty(row)) return false                        // drop the empty phantom row
          if (row.isManual) return true                            // manual input is never lost
          if (mode === 'append') return true                       // keep every earlier scan
          return (row.scanBatch || 1) !== maxBatch                 // replace: drop only the last batch
        })
        const newRows = cartItems.map(row => ({ ...row, scanBatch: targetBatch }))
        return withPhantomRow([...kept, ...newRows])
      })
    } catch (err) {
      console.error('Extraction failed:', err)
      setErrorMsg(err.message || 'Could not process the prescription. Please try another image.')
      // Leave the cart exactly as it was — a failed scan must not cost the
      // user their manually entered rows.
    } finally {
      setLoading(false)
    }
  }

  function switchToManual(i) {
    setCart(prev => withPhantomRow(prev.map((it, idx) =>
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
    )))
  }

  function switchToAuto(i) {
    setCart(prev => withPhantomRow(prev.map((it, idx) => {
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
    })))
  }

  async function updateManualSearch(i, query) {
    // Typing never spawns a new row — the row stays the single entry point
    // until a medicine is committed (see withPhantomRow / isEntryRow).
    setCart(prev => withPhantomRow(prev.map((it, idx) =>
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
    )))

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

    setCart(prev => withPhantomRow(prev.map((it, idx) =>
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
    )))

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
    setCart(prev => withPhantomRow(prev.map((it, idx) =>
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
    )))
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

    setCart(prev => withPhantomRow(prev.map((it, idx) =>
      idx === i ? { ...it, rx_qty: newQty } : it
    )))

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
    setCart(prev => withPhantomRow(prev.filter((_, idx) => idx !== i)))
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
    setErrorMsg(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const grandTotal = cart.reduce((sum, item) =>
    item.isUnavailable ? sum : sum + (item.billing?.billing?.line_total || 0), 0
  )

  const validItemCount = cart.filter(item => !item.isUnavailable && item.billing?.billing).length
  const hasBillableItems = validItemCount > 0

  // Is there anything worth keeping on screen while a scan runs? (Any row the
  // user already worked on, vs. just the empty phantom entry row.)
  const hasCartContent = cart.some(row => !isRowEmpty(row))
  // Full-screen extraction animation only when there's nothing to protect.
  // Otherwise we keep the cart visible and show a non-blocking strip instead,
  // so manually entered rows never disappear mid-scan.
  const showFullLoader = loading && !hasCartContent

  // A prescription has already been scanned once there's at least one AI row
  // (un-overridden extracted row). When true, a further scan asks whether it's
  // a re-scan (replace) or a different Rx for the same bill (append).
  const hasExtractedRows = cart.some(row => !row.isManual)

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
      const res = await authFetch(`${API}/confirm-sale`, {
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
      setErrorMsg('Network error — the sale could not be completed. Please try again.')
    }
  }

  const timeString = currentTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const dateString = currentTime.toLocaleDateString('en-US', { weekday: 'short', month: 'long', day: 'numeric', year: 'numeric' })

  // Gate the whole app behind login — no token, no POS.
  if (!token) {
    return <Login apiBase={API} onSuccess={() => setTokenState(getToken())} />
  }

  return (
    <div className="h-screen bg-app-canvas flex flex-col overflow-hidden font-sans text-slate-800">

      {/* Header */}
      <div className="bg-white px-8 py-4 flex items-center justify-between border-b border-slate-200 shadow-sm relative z-20">
        <LogoLockup tone="dark" />
        <div className="flex items-center gap-5">
          <div className="text-right">
            <p className="text-lg font-bold text-slate-800 tracking-wide">{timeString}</p>
            <p className="text-sm font-medium text-slate-500">{dateString}</p>
          </div>
          <button
            onClick={handleLogout}
            title="Log out"
            className="flex items-center gap-2 text-slate-500 hover:text-slate-900 bg-white hover:bg-slate-100 border border-slate-200 rounded-xl px-4 py-2.5 text-xs font-bold uppercase tracking-widest transition-colors shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Logout
          </button>
        </div>
      </div>

      {/* Main layout */}
      <div className="flex flex-1 gap-0 overflow-hidden">

        {/* LEFT PANEL */}
        <div className="w-[20%] bg-gradient-to-b from-white to-slate-50 border-r border-slate-200 p-7 flex flex-col gap-6 overflow-y-auto relative z-10 shadow-[4px_0_24px_rgba(15,23,42,0.04)]">
          <h2 className="font-bold text-slate-500 uppercase tracking-widest text-xs flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#0D9488] shadow-[0_0_10px_rgba(13,148,136,0.35)]"></span>
            Upload Prescription
          </h2>

          <div>
            <label className="group flex flex-col items-center justify-center gap-2 w-full py-6 px-4 rounded-xl border border-dashed border-slate-300 bg-slate-50 hover:border-[#0D9488] hover:bg-green-50/60 cursor-pointer transition-all">
              <svg className="w-7 h-7 text-slate-400 group-hover:text-[#0D9488] transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <span className="text-xs font-bold text-slate-600 group-hover:text-slate-900 transition-colors">
                {imageFile ? 'Change image' : 'Choose prescription image'}
              </span>
              <span className="text-[10px] text-slate-400">JPG, PNG · tap to upload</span>
              <input
                type="file"
                accept="image/*"
                ref={fileInputRef}
                onChange={handleImageUpload}
                className="hidden"
              />
            </label>
            {imageFile && (
              <p className="mt-2 text-[11px] text-slate-500 font-medium truncate" title={imageFile.name}>
                {imageFile.name}
              </p>
            )}
          </div>

          {image && (
            <div className="border border-slate-200 p-1.5 rounded-2xl bg-white shadow-inner">
              <img src={image} alt="Preview" className="w-full rounded-xl object-contain max-h-56 bg-slate-100" />
            </div>
          )}

          {/* Extract action:
              - while a scan runs → a single disabled "Processing AI…" button
              - after a first scan (hasExtractedRows) → two labelled modes:
                  re-scan the same Rx (replace) vs. a different Rx (append)
              - otherwise → the normal single "Extract Data" button */}
          {loading ? (
            <button
              disabled
              className="w-full btn-green text-white font-bold py-3.5 rounded-xl text-sm tracking-wide flex justify-center items-center gap-2"
            >
              <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Processing AI...
            </button>
          ) : hasExtractedRows ? (
            <div className="flex flex-col gap-2.5">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                Already scanned — scan again as:
              </p>
              <button
                onClick={() => handleExtract('replace')}
                disabled={!imageFile}
                title="Re-scan the last prescription — replaces only the most recent scan's items (earlier scans stay)"
                className="w-full flex items-center justify-center gap-2 border border-slate-200 bg-white text-slate-700 hover:border-green-400 hover:text-green-700 font-bold py-2.5 rounded-xl text-xs tracking-wide transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                Re-scan (replace last scan)
              </button>
              <button
                onClick={() => handleExtract('append')}
                disabled={!imageFile}
                title="A different prescription for the same bill — keeps current items and adds the new ones below"
                className="w-full flex items-center justify-center gap-2 btn-green text-white font-bold py-2.5 rounded-xl text-xs tracking-wide disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M12 4v16m8-8H4" /></svg>
                Different Rx (add to bill)
              </button>
            </div>
          ) : (
            <button
              onClick={() => handleExtract('replace')}
              disabled={!imageFile}
              className="w-full btn-green text-white font-bold py-3.5 rounded-xl text-sm tracking-wide flex justify-center items-center gap-2"
            >
              🔍 Extract Data
            </button>
          )}

          {lastScanMetrics && (
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 mt-auto">
              <h3 className="font-bold text-[10px] text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                <svg className="w-3.5 h-3.5 text-[#0D9488]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Token Metrics
              </h3>
              <div className="flex justify-between items-center mb-2.5 text-xs">
                <span className="text-slate-500 font-medium">This Scan</span>
                <span className="font-bold text-slate-800">
                  {lastScanMetrics.total_tokens?.toLocaleString()} tok
                  <span className="text-slate-300 mx-1">|</span>
                  <span className="text-[#0D9488] font-mono">₹{lastScanMetrics.cost_inr?.toFixed(4)}</span>
                </span>
              </div>
              <div className="flex justify-between items-center border-t border-slate-200 pt-2.5 text-xs">
                <span className="text-slate-500 font-medium">Session Total</span>
                <span className="font-black text-slate-800">
                  {sessionTokens.toLocaleString()} tok
                  <span className="text-slate-300 mx-1">|</span>
                  <span className="text-[#0D9488] font-mono text-sm">₹{sessionCost.toFixed(4)}</span>
                </span>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT PANEL */}
        <div className="flex-1 p-8 relative flex flex-col overflow-hidden bg-transparent">

          {/* ── ERROR BANNER ── */}
          {errorMsg && (
            <div className="mb-4 flex items-start gap-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl px-4 py-3 shadow-sm">
              <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-sm font-semibold flex-1">{errorMsg}</p>
              <button
                onClick={() => setErrorMsg(null)}
                className="text-rose-400 hover:text-rose-600 transition-colors"
                aria-label="Dismiss"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
          )}

          {/* ── AI LOADING PANEL (only when the cart is empty) ── */}
          {showFullLoader && (
            <div className="flex-1 flex flex-col items-center justify-center gap-10">

              {/* Orbiting spinner — like a radar dish scanning for data */}
              <div className="relative w-28 h-28 flex items-center justify-center">
                {/* Center icon */}
                <div className="w-16 h-16 bg-green-600 rounded-2xl flex items-center justify-center shadow-xl shadow-green-900/40 z-10">
                  <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                {/* Inner ring */}
                <div className="absolute inset-0 rounded-full border-4 border-green-500/20 border-t-green-500 animate-spin" />
                {/* Outer ring — spins the other way, like two gears */}
                <div
                  className="absolute -inset-4 rounded-full border-2 border-green-400/10 border-t-green-400/50 animate-spin"
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
            <div className="bg-white border border-slate-200/70 shadow-card-lg rounded-3xl p-12 text-center mb-6 max-w-lg mx-auto mt-12 animate-rise">
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <svg className="w-10 h-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-3xl font-black text-slate-800 mb-2">Sale Complete</h2>
              <p className="text-slate-500 font-medium mb-6">Receipt #{saleResult.bill_id}</p>
              <div className="bg-slate-50 rounded-2xl py-6 px-4 mb-8">
                <p className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Amount Paid</p>
                <p className="text-5xl font-black text-green-600">₹{(saleResult.grand_total ?? grandTotal).toFixed(2)}</p>
              </div>
              <button
                onClick={resetTerminal}
                className="w-full btn-green text-white px-8 py-4 rounded-xl font-bold text-lg"
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

          {/* Patient info + cart — stays visible during a scan when the user
              already has rows, so their manual entries never vanish. */}
          {!showFullLoader && cart.length > 0 && !saleResult?.success && (
            <div className="flex-1 flex flex-col overflow-hidden">

              {/* Non-blocking "scanning" strip shown above the cart while the
                  AI reads a new prescription (only in the has-content case). */}
              {loading && (
                <div className="mb-4 flex items-center gap-3 bg-white border border-green-200/70 rounded-2xl px-4 py-3 shadow-card overflow-hidden relative">
                  <div className="absolute top-0 left-0 right-0 h-0.5 bg-green-100 overflow-hidden">
                    <div className="h-full w-1/3 bg-green-500 rounded-full animate-indeterminate" />
                  </div>
                  <svg className="animate-spin h-4 w-4 text-green-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <p className="text-sm font-bold text-slate-700 flex-1">
                    {loadingMessages[loadingMsgIndex]}
                    <span className="ml-2 font-medium text-slate-400">— your existing items are kept; new ones appear below.</span>
                  </p>
                </div>
              )}

              {/* Patient Info + Summary */}
              <div className="bg-white px-5 py-3 rounded-2xl border border-slate-200/70 shadow-card flex items-center justify-between mb-4">

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
                      className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm font-semibold text-slate-800 focus:bg-white focus:border-green-500 focus:ring-2 focus:ring-green-100 outline-none transition-all"
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
                      className="w-20 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm font-semibold text-slate-800 focus:bg-white focus:border-green-500 focus:ring-2 focus:ring-green-100 outline-none transition-all"
                    />
                  </div>

                  {/* Gender */}
                  <div className="flex items-center gap-2">
                    <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                      Gender
                    </label>

                    <SelectField
                      value={patientGender}
                      onChange={setPatientGender}
                      options={['Male', 'Female', 'Other']}
                      placeholder="Select"
                      className="w-32"
                    />
                  </div>

                </div>

                {/* Right Section - Summary */}
                <div className="pl-6 min-w-[190px] bg-gradient-to-br from-green-50 to-green-100/70 border border-green-200/80 rounded-xl px-4 py-3">

                  <div className="flex justify-between items-center">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      Grand Total:
                    </span>

                    <span className="text-1xl font-black text-green-600">
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

              {/* Cart rows. The header lives INSIDE the same scroll box (sticky)
                  so its columns line up exactly with the rows — same width,
                  same scrollbar inset. A fixed 2.75rem serial-number column sits
                  before the 12 proportional columns (identical in both). "S.No"
                  matches the label pharmacists already see on printed bills and
                  billing software (Tally/Marg/GST formats), not a generic "#". */}
              <div ref={rowsScrollRef} className="overflow-y-auto flex-1 pr-2 pb-28">
                <div className="grid grid-cols-[2.75rem_repeat(12,minmax(0,1fr))] gap-2 px-4 py-2.5 text-[10px] font-extrabold text-slate-400 uppercase tracking-widest border-b border-slate-200/70 mb-2.5 bg-white rounded-xl shadow-card sticky top-0 z-10">
                  <div className="text-center tracking-normal">S.No</div>
                  <div className="col-span-4">Medicine</div>
                  <div className="col-span-2 text-center">Qty</div>
                  <div className="col-span-1 text-center">Pack</div>
                  <div className="col-span-2 text-center">Billable Packs</div>
                  <div className="col-span-2 text-right">Line Total</div>
                  <div className="col-span-1"></div>
                </div>

                <div className="bg-white rounded-2xl border border-slate-200/70 shadow-card divide-y divide-slate-200/70">
                {cart.map((item, i) => (
                  <div
                    key={i}
                    className={`grid grid-cols-[2.75rem_repeat(12,minmax(0,1fr))] gap-2 items-center px-4 py-2 transition-colors duration-200 min-h-[80px] first:rounded-t-2xl last:rounded-b-2xl ${
                      item.isUnavailable
                        ? 'bg-slate-50/50 opacity-60'
                        : 'hover:bg-slate-50/70'
                    }`}
                  >
                    {/* Serial number — blank for the trailing empty entry row. */}
                    <div className="text-center text-sm font-bold text-slate-400 self-center">
                      {isRowEmpty(item) ? '' : i + 1}
                    </div>

                    <div className="col-span-4 min-h-[80px] flex flex-col justify-between gap-1 py-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className={`inline-flex items-center gap-1 border px-2 py-0.5 rounded uppercase tracking-wider text-[9px] font-black ${item.isManual ? 'bg-amber-50 text-amber-700 border-amber-200/50' : 'bg-green-50 text-green-700 border-green-100/50'}`}>
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            {item.isManual ? (
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            ) : (
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                            )}
                          </svg>
                          {item.isManual ? (item.extracted === 'Manual Entry' ? 'Manual Add' : 'Override') : item.extracted}
                        </span>
                        {item.isManual ? (
                          item.extractedMatches?.length > 0 && (
                            <button
                              onClick={() => switchToAuto(i)}
                              className="text-[10px] text-green-600 hover:bg-green-50 font-bold border border-transparent hover:border-green-200 rounded px-2 py-1 transition-colors uppercase tracking-wide"
                            >
                              ↩ Restore AI
                            </button>
                          )
                        ) : (
                          <button
                            onClick={() => switchToManual(i)}
                            className="text-[10px] text-slate-500 hover:bg-slate-100 font-bold border border-transparent hover:border-slate-200 rounded px-2 py-1 transition-colors uppercase tracking-wide"
                          >
                            Edit
                          </button>
                        )}
                      </div>

                      <div className="flex items-center justify-center">
                        <div className="relative w-full">
                          {item.isManual ? (
                            <>
                              <div className="flex items-center border border-slate-200 rounded-lg overflow-hidden focus-within:border-green-500 focus-within:ring-2 focus-within:ring-green-100 bg-slate-50 transition-all">
                                <input
                                  value={item.manualQuery}
                                  onChange={e => updateManualSearch(i, e.target.value)}
                                  onKeyDown={e => handleKeyDown(e, i)}
                                  placeholder="Search inventory..."
                                  className="flex-1 px-3 py-1 text-sm font-semibold text-slate-800 bg-transparent focus:outline-none placeholder:font-medium placeholder:text-slate-400"
                                />
                                {item.selectedName && (
                                  <button onClick={() => clearManualSelection(i)} className="px-3 text-slate-400 hover:text-rose-500 transition-colors">
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                                  </button>
                                )}
                              </div>

                              {item.showDropdown && item.matches.length > 0 && (
                                <div className="absolute z-30 mt-2 w-full rounded-xl border border-slate-200 bg-white shadow-xl max-h-60 overflow-y-auto">
                                  {item.matches.map((match, j) => (
                                    <button
                                      key={j}
                                      type="button"
                                      onMouseDown={e => e.preventDefault()}
                                      onMouseEnter={() => setCart(prev => prev.map((it, idx) =>
                                        idx === i ? { ...it, highlightedIndex: j } : it
                                      ))}
                                      onClick={() => selectManualMatch(i, j)}
                                      className={`w-full text-left px-3 py-2 text-sm transition-colors ${item.highlightedIndex === j ? 'bg-green-600 text-white' : 'text-slate-700'}`}
                                    >
                                      {match.matched_text}
                                    </button>
                                  ))}
                                </div>
                              )}
                            </>
                          ) : (
                            /* AI-matched row — same themed dropdown as gender/manual */
                            <SelectField
                              value={item.matches[item.selectedIndex]?.matched_text || ''}
                              options={item.matches.map(m => m.matched_text)}
                              onChange={(text) => {
                                const idx = item.matches.findIndex(m => m.matched_text === text)
                                if (idx >= 0) updateSelection(i, idx)
                              }}
                              placeholder={item.extracted}
                              disabled={item.isUnavailable}
                              className="w-full"
                            />
                          )}
                        </div>
                      </div>

                      <div className="min-h-[1.2rem]">
                        {item.stockWarning && !item.isUnavailable ? (
                          <div className="flex items-center gap-2 bg-amber-50 border border-amber-100 px-2 py-1 rounded-lg text-[10px] text-amber-700 font-semibold">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                            <span>{item.stockWarning}</span>
                          </div>
                        ) : item.isUnavailable ? (
                          <div className="flex items-center gap-2 text-[10px] text-rose-600 font-semibold">
                            <span className="bg-rose-50 border border-rose-100 px-2 py-0.5 rounded uppercase tracking-wide">Out of Stock</span>
                            <span className="text-slate-400 italic">Removed from bill</span>
                          </div>
                        ) : (
                          <div className="h-4" />
                        )}
                      </div>
                    </div>

                    <div className="col-span-2 flex items-center justify-center">
                      <input
                        type="number"
                        min="1"
                        value={item.rx_qty}
                        onChange={e => updateQty(i, e.target.value)}
                        placeholder="Qty"
                        disabled={item.isUnavailable}
                        className="w-full max-w-[92px] border border-slate-200 rounded-lg px-2 py-1.5 text-sm font-bold text-center focus:outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100 bg-slate-50 text-slate-800 disabled:bg-slate-100 disabled:text-slate-400 transition-all"
                      />
                    </div>

                    <div className="col-span-1 flex items-center justify-center text-sm font-semibold text-slate-500 bg-slate-50 border border-slate-100 py-1 rounded-lg">
                      {item.billing?.medicine?.pack_size ?? '—'}
                    </div>

                    <div className="col-span-2 flex flex-col items-center justify-center">
                      <span className={`text-base font-black ${item.isUnavailable ? 'text-slate-300' : 'text-slate-800'}`}>
                        {item.isUnavailable ? '—' : (item.billing?.billing?.packs_needed ?? '—')}
                      </span>
                      {typeof item.billing?.medicine?.stock === 'number' && (
                        <span className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mt-0.5">
                          In Stock: {item.billing.medicine.stock}
                        </span>
                      )}
                    </div>

                    <div className={`col-span-2 flex items-center justify-end text-lg font-black tracking-tight ${item.isUnavailable ? 'text-slate-300' : 'text-slate-800'}`}>
                      {item.isUnavailable ? '—' : item.billing?.billing?.line_total ? `₹${item.billing.billing.line_total.toFixed(2)}` : '—'}
                    </div>

                    <div className="col-span-1 text-center">
                      {/* The trailing phantom row is the entry point for the
                          next item — it can't be deleted. */}
                      {!(i === cart.length - 1 && isRowEmpty(item)) && (
                        <button
                          onClick={() => removeRow(i)}
                          className="w-7 h-7 rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600 flex items-center justify-center mx-auto transition-colors"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                </div>
              </div>

              {/* Fixed bottom action bar */}
              <div className="absolute bottom-0 left-8 right-8 pb-8 pt-6 bg-gradient-to-t from-slate-50 via-slate-50 to-transparent z-10 pointer-events-none">
                <div className="bg-white p-4 rounded-2xl shadow-card-lg border border-slate-200/70 flex justify-end items-center pointer-events-auto">
                  <button
                    onClick={handleConfirmSale}
                    disabled={!hasBillableItems}
                    className="font-black text-base px-10 py-4 rounded-xl btn-green text-white hover:-translate-y-0.5 disabled:cursor-not-allowed flex items-center gap-3 tracking-wide"
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