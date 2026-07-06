import { useEffect, useRef, useState } from 'react'

// SelectField.jsx — themed, searchable dropdown (combobox).
//
// A drop-in replacement for a native <select>: shows a chevron so it reads as
// a dropdown, opens on focus/click, filters options as you type, and supports
// arrow-key/Enter/Escape navigation. Styled to match the app's inputs.
//
// Props:
//   value       — current value (string, '' for none)
//   onChange    — called with the chosen option string
//   options     — array of option strings
//   placeholder — shown when nothing is selected (default 'Select')
//   className   — extra classes for the wrapper (e.g. width)
export default function SelectField({ value, onChange, options, placeholder = 'Select', className = '' }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState(null) // null = not typing; input shows `value`
  const [highlighted, setHighlighted] = useState(0)
  const rootRef = useRef(null)

  // Close (and discard any half-typed filter) when clicking outside.
  useEffect(() => {
    function onDocMouseDown(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) {
        setOpen(false)
        setQuery(null)
      }
    }
    document.addEventListener('mousedown', onDocMouseDown)
    return () => document.removeEventListener('mousedown', onDocMouseDown)
  }, [])

  const filtered = query
    ? options.filter(opt => opt.toLowerCase().includes(query.toLowerCase()))
    : options

  function selectOption(opt) {
    onChange(opt)
    setOpen(false)
    setQuery(null)
  }

  function handleKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (!open) { setOpen(true); return }
      setHighlighted(h => Math.min(h + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted(h => Math.max(h - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (open && filtered[highlighted]) selectOption(filtered[highlighted])
    } else if (e.key === 'Escape') {
      setOpen(false)
      setQuery(null)
    }
  }

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <div className="flex items-center bg-slate-50 border border-slate-200 rounded-lg focus-within:bg-white focus-within:border-green-500 focus-within:ring-2 focus-within:ring-green-100 transition-all">
        <input
          value={query !== null ? query : (value || '')}
          placeholder={placeholder}
          onChange={e => { setQuery(e.target.value); setOpen(true); setHighlighted(0) }}
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          onBlur={() => { setOpen(false); setQuery(null) }}
          onKeyDown={handleKeyDown}
          className="w-full bg-transparent px-3 py-2 text-sm font-semibold text-slate-800 outline-none placeholder:text-slate-400 placeholder:font-medium"
        />
        <button
          type="button"
          tabIndex={-1}
          aria-label="Toggle options"
          onMouseDown={e => e.preventDefault()}
          onClick={() => { setOpen(o => !o); setQuery(null) }}
          className="px-2 text-slate-400 hover:text-slate-600 transition-colors"
        >
          <svg
            className={`w-4 h-4 transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {open && filtered.length > 0 && (
        // preventDefault on mousedown so interacting with the list (options,
        // scrollbar) never blurs the input and closes the dropdown early.
        <div
          onMouseDown={e => e.preventDefault()}
          className="absolute z-30 mt-2 w-full rounded-xl border border-slate-200 bg-white shadow-xl max-h-56 overflow-y-auto"
        >
          {filtered.map((opt, j) => (
            <button
              key={opt}
              type="button"
              onMouseDown={e => e.preventDefault()}
              onClick={() => selectOption(opt)}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                highlighted === j ? 'bg-green-100 text-green-900' : 'text-slate-700 hover:bg-slate-50'
              } ${opt === value ? 'font-bold' : ''}`}
            >
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
