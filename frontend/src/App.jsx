import { useState } from 'react'

const API = 'http://localhost:8000'

export default function App() {
  const [imageFile, setImageFile] = useState(null)
  const [image, setImage] = useState(null)
  const [loading, setLoading] = useState(false)
  const [cart, setCart] = useState([])
  const [patientName, setPatientName] = useState('')
  const [patientAge, setPatientAge] = useState('')
  const [saleResult, setSaleResult] = useState(null)

  function handleImageUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setImageFile(file)
    setImage(URL.createObjectURL(file))
    setCart([])
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

      const extracted = data.extracted_data
      setPatientName(extracted.patient_name === 'Unknown' ? '' : extracted.patient_name)
      setPatientAge(extracted.age || '')

      const cartItems = await Promise.all(
        extracted.medicines.map(async (med) => {
          const matches = await searchMedicine(med.name)
          const itemCode = matches.length > 0 ? matches[0].item_code : null
          const billing = itemCode
            ? await getBilling(itemCode, med.suggested_qty || 1)
            : null

          return {
            extracted: med.name,
            rx_qty: med.suggested_qty || 1,
            matches,
            extractedMatches: matches,       // store original for restoring Auto
            extractedBilling: billing,       // store original billing for restoring Auto
            selectedIndex: 0,
            selectedItemCode: itemCode,
            billing,
            isManual: false,
            manualQuery: '',
            selectedName: null,
            showDropdown: false,
            highlightedIndex: 0
          }
        })
      )
      setCart(cartItems)
    } catch (err) {
      console.error('Extraction failed:', err)
    } finally {
      setLoading(false)
    }
  }

  function addManualRow() {
    setCart(prev => [...prev, {
      extracted: 'Manual Entry',
      rx_qty: '',
      matches: [],
      extractedMatches: [],
      extractedBilling: null,
      selectedIndex: 0,
      selectedItemCode: null,
      billing: null,
      isManual: true,
      manualQuery: '',
      selectedName: null,
      showDropdown: false,
      highlightedIndex: 0
    }])
  }

  // Switch to manual mode
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
        rx_qty: ''
      } : it
    ))
  }

  // Restore auto/extracted mode
  function switchToAuto(i) {
    setCart(prev => prev.map((it, idx) =>
      idx === i ? {
        ...it,
        isManual: false,
        manualQuery: '',
        selectedName: null,
        selectedItemCode: it.extractedMatches[0]?.item_code || null,
        matches: it.extractedMatches,
        billing: it.extractedBilling,
        selectedIndex: 0,
        showDropdown: false,
        rx_qty: it.rx_qty || 1
      } : it
    ))
  }

  async function updateManualSearch(i, query) {
    setCart(prev => prev.map((it, idx) =>
      idx === i ? { ...it, manualQuery: query, selectedName: null, billing: null, showDropdown: true, highlightedIndex: 0 } : it
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

    const billing = await getBilling(match.item_code, qty)
    setCart(prev => prev.map((it, idx) =>
      idx === i ? { ...it, billing } : it
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
        rx_qty: ''
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

    const billing = await getBilling(match.item_code, qty)
    setCart(prev => prev.map((it, idx) =>
      idx === i ? { ...it, billing } : it
    ))
  }

  async function updateQty(i, value) {
    const newQty = value === '' ? '' : parseInt(value)

    setCart(prev => prev.map((it, idx) =>
      idx === i ? { ...it, rx_qty: newQty } : it
    ))

    const item = cart[i]
    if (newQty > 0 && item.selectedItemCode) {
      const billing = await getBilling(item.selectedItemCode, newQty)
      setCart(prev => prev.map((it, idx) =>
        idx === i ? { ...it, billing } : it
      ))
    }
  }

  function removeRow(i) {
    setCart(prev => prev.filter((_, idx) => idx !== i))
  }

  const grandTotal = cart.reduce((sum, item) =>
    sum + (item.billing?.billing?.line_total || 0), 0
  )

  const hasStockError = cart.some(item =>
    typeof item.billing?.medicine?.stock === 'number' &&
    item.billing.billing?.packs_needed > item.billing.medicine.stock
  )

  async function handleConfirmSale() {
    const billingItems = cart
      .filter(item => item.billing?.billing)
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

  return (
    <div className="min-h-screen bg-green-50 flex flex-col">

      {/* Header */}
      <div className="bg-green-500 px-8 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">PharmaPOS 💊</h1>
          <p className="text-green-100 text-sm">Prescription Processing System</p>
        </div>
        {grandTotal > 0 && (
          <div className="bg-white rounded-xl px-6 py-2 text-right">
            <p className="text-xs text-green-600 font-semibold uppercase">Grand Total</p>
            <p className="text-2xl font-bold text-green-600">₹{grandTotal.toFixed(2)}</p>
          </div>
        )}
      </div>

      {/* Main layout */}
      <div className="flex flex-1 gap-0">

        {/* LEFT PANEL */}
        <div className="w-1/4 bg-white border-r border-gray-100 p-6 flex flex-col gap-4">
          <h2 className="font-bold text-gray-800">Prescription</h2>

          <input
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            className="block w-full text-xs text-gray-500"
          />

          {image && (
            <img
              src={image}
              alt="Preview"
              className="w-full rounded-lg border border-gray-200 object-contain max-h-48"
            />
          )}

          <button
            onClick={handleExtract}
            disabled={!imageFile || loading}
            className="w-full bg-green-500 text-white font-semibold py-2.5 rounded-xl
                       disabled:opacity-40 hover:bg-green-600 transition-colors text-sm"
          >
            {loading ? 'Extracting...' : '🔍 Extract Prescription'}
          </button>

          <div className="border-t border-gray-100 pt-4">
            <button
              onClick={addManualRow}
              className="w-full border border-gray-300 text-gray-700 font-medium
                         py-2.5 rounded-xl hover:bg-gray-50 transition-colors text-sm"
            >
              🛒 Manual Entry
            </button>
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div className="flex-1 p-6">

          {/* Sale success */}
          {saleResult?.success && (
            <div className="bg-green-50 border border-green-200 rounded-2xl p-8 text-center mb-6">
              <div className="text-4xl mb-2">✅</div>
              <h2 className="text-xl font-bold text-green-800">Sale Complete</h2>
              <p className="text-green-600 mt-1">Receipt #{saleResult.bill_id}</p>
              <p className="text-3xl font-bold text-green-500 mt-2">₹{grandTotal.toFixed(2)}</p>
              <button
                onClick={() => { setCart([]); setSaleResult(null); setImage(null); setImageFile(null) }}
                className="mt-4 bg-green-500 text-white px-6 py-2 rounded-xl font-semibold hover:bg-green-600"
              >
                Start New Sale
              </button>
            </div>
          )}

          {/* Sale failure */}
          {saleResult && !saleResult.success && (
            <div className="bg-red-50 border border-red-200 rounded-2xl p-6 mb-6">
              <div className="text-2xl mb-2">⚠️</div>
              <h2 className="text-lg font-bold text-red-800">Sale Failed — Insufficient Stock</h2>
              <div className="mt-3 space-y-2">
                {saleResult.details?.map((item, i) => (
                  <div key={i} className="bg-white rounded-lg p-3 text-sm">
                    <span className="font-semibold text-red-700">{item.product_name}</span>
                    <span className="text-gray-500 ml-2">
                      Need {item.required} packs — only {item.available} available
                    </span>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setSaleResult(null)}
                className="mt-4 border border-red-300 text-red-700 px-5 py-2 rounded-xl text-sm font-medium hover:bg-red-100"
              >
                Go Back & Edit
              </button>
            </div>
          )}

          {/* Patient info + cart */}
          {cart.length > 0 && !saleResult?.success && (
            <>
              {/* Patient fields with labels */}
              <div className="flex gap-4 mb-6">
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    Patient Name
                  </label>
                  <input
                    value={patientName}
                    onChange={e => setPatientName(e.target.value)}
                    placeholder="Enter patient name"
                    className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-green-400"
                  />
                </div>
                <div className="w-28">
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    Age
                  </label>
                  <input
                    value={patientAge}
                    onChange={e => setPatientAge(e.target.value)}
                    placeholder="Years"
                    type="number"
                    className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-green-400"
                  />
                </div>
              </div>

              {/* Table header — 12 cols: medicine(4) qty(2) pack_size(1) packs(2) total(2) del(1) */}
              <div className="grid grid-cols-12 gap-2 px-3 py-2 text-xs font-bold text-gray-400 uppercase tracking-wide border-b border-gray-100 mb-2">
                <div className="col-span-4">Medicine</div>
                <div className="col-span-2 text-center">Qty</div>
                <div className="col-span-1 text-center">Pack Size</div>
                <div className="col-span-2 text-center">Packs</div>
                <div className="col-span-2 text-right">Total</div>
                <div className="col-span-1"></div>
              </div>

              {/* Cart rows */}
              {cart.map((item, i) => {
                const isOutOfStock = typeof item.billing?.medicine?.stock === 'number' &&
                  item.billing.billing?.packs_needed > item.billing.medicine.stock

                return (
                  <div key={i} className={`grid grid-cols-12 gap-2 items-center bg-white rounded-xl p-3 mb-2 shadow-sm border ${isOutOfStock ? 'border-red-300' : 'border-transparent'}`}>

                    {/* Medicine column */}
                    <div className="col-span-4">
                      {item.isManual ? (
                        <div className="relative">
                          {/* Mode toggle — Manual mode shows "Auto" button only if extracted matches exist */}
                          {item.extractedMatches?.length > 0 && (
                            <div className="flex justify-end mb-1">
                              <button
                                onClick={() => switchToAuto(i)}
                                className="text-xs text-indigo-500 hover:text-indigo-700 font-medium border border-indigo-200 rounded px-2 py-0.5"
                              >
                                ↩ Auto
                              </button>
                            </div>
                          )}

                          <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden focus-within:border-green-400">
                            <input
                              value={item.manualQuery}
                              onChange={e => updateManualSearch(i, e.target.value)}
                              onKeyDown={e => handleKeyDown(e, i)}
                              placeholder="Search medicine..."
                              className="flex-1 px-3 py-1.5 text-sm focus:outline-none"
                            />
                            {item.selectedName && (
                              <button
                                onClick={() => clearManualSelection(i)}
                                className="px-2 text-gray-400 hover:text-red-500 text-lg"
                              >
                                ✕
                              </button>
                            )}
                          </div>

                          {/* Suggestions dropdown */}
                          {item.showDropdown && item.matches.length > 0 && (
                            <div className="absolute z-20 w-full bg-white border border-gray-200 rounded-lg shadow-lg mt-1 overflow-hidden">
                              {item.matches.map((match, j) => (
                                <div
                                  key={j}
                                  onClick={() => selectManualMatch(i, j)}
                                  onMouseEnter={() => setCart(prev => prev.map((it, idx) => idx === i ? { ...it, highlightedIndex: j } : it))}
                                  className={`flex items-center justify-between px-3 py-2.5 text-sm cursor-pointer border-b border-gray-50 last:border-0 ${item.highlightedIndex === j ? 'bg-green-100' : 'hover:bg-green-50'}`}
                                >
                                  <span className="text-gray-800">{match.matched_text}</span>
                                  <span className="text-xs text-green-600 font-semibold ml-2 shrink-0">{match.score}%</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <p className="text-xs text-indigo-500 font-medium">✨ {item.extracted}</p>
                            {/* Auto mode shows "Manual" button */}
                            <button
                              onClick={() => switchToManual(i)}
                              className="text-xs text-gray-400 hover:text-gray-700 font-medium border border-gray-200 rounded px-2 py-0.5"
                            >
                              Manual
                            </button>
                          </div>
                          <select
                            value={item.selectedIndex}
                            onChange={e => updateSelection(i, parseInt(e.target.value))}
                            className={`w-full border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:border-green-400 ${isOutOfStock ? 'border-red-300' : 'border-gray-200'}`}
                          >
                            {item.matches.map((match, j) => (
                              <option key={j} value={j}>
                                {match.matched_text}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {isOutOfStock && (
                        <p className="text-xs text-red-500 mt-1 font-semibold">
                          ⚠️ Only {item.billing.medicine.stock} packs in stock
                        </p>
                      )}
                    </div>

                    {/* Qty */}
                    <div className="col-span-2">
                      <input
                        type="number"
                        min="1"
                        value={item.rx_qty}
                        onChange={e => updateQty(i, e.target.value)}
                        placeholder="Qty"
                        className={`w-full border rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:border-green-400 ${isOutOfStock ? 'border-red-400 bg-red-50' : 'border-gray-200'}`}
                      />
                    </div>

                    {/* Pack Size */}
                    <div className="col-span-1 text-sm text-gray-500 text-center">
                      {item.billing?.medicine?.pack_size ?? '—'}
                    </div>

                    {/* Packs + stock */}
                    <div className="col-span-2 text-sm text-center flex flex-col justify-center">
                      <span className={isOutOfStock ? 'text-red-600 font-bold' : 'text-gray-600'}>
                        {item.billing?.billing?.packs_needed ?? '—'}
                      </span>
                      {typeof item.billing?.medicine?.stock === 'number' && (
                        <span className="text-[10px] text-gray-400">
                          (Stock: {item.billing.medicine.stock})
                        </span>
                      )}
                    </div>

                    {/* Total */}
                    <div className={`col-span-2 text-sm font-bold text-right ${isOutOfStock ? 'text-red-500' : 'text-gray-800'}`}>
                      {item.billing?.billing?.line_total
                        ? `₹${item.billing.billing.line_total.toFixed(2)}`
                        : '—'}
                    </div>

                    {/* Delete */}
                    <div className="col-span-1 text-center">
                      <button
                        onClick={() => removeRow(i)}
                        className="text-gray-300 hover:text-red-400 transition-colors text-lg"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                )
              })}

              {/* Add row + Confirm */}
              <div className="flex justify-between items-center mt-4">
                <button
                  onClick={addManualRow}
                  className="text-sm text-green-600 font-medium hover:underline"
                >
                  + Add medicine
                </button>
                <button
                  onClick={handleConfirmSale}
                  disabled={cart.length === 0 || hasStockError}
                  className={`font-bold px-8 py-3 rounded-xl transition-colors ${hasStockError
                    ? 'bg-red-100 text-red-500 cursor-not-allowed'
                    : 'bg-green-500 text-white hover:bg-green-600 disabled:opacity-40'
                    }`}
                >
                  {hasStockError ? '⚠️ Resolve Stock Errors' : `Confirm Sale · ₹${grandTotal.toFixed(2)}`}
                </button>
              </div>
            </>
          )}

          {/* Empty state */}
          {cart.length === 0 && !loading && !saleResult && (
            <div className="flex flex-col items-center justify-center h-full text-center text-gray-400 pt-20">
              <div className="text-5xl mb-4">📋</div>
              <p className="text-lg font-semibold">Ready for next patient</p>
              <p className="text-sm mt-2">Upload a prescription or start a manual entry</p>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}