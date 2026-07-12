// Lightweight enterprise logistics SVG glyphs. Stroke uses currentColor so the
// parent can tint via the agent accent color. Used by agent cards, pages and
// the operations dashboard.

export default function AgentIcon({ name, className = '', strokeWidth = 1.4 }) {
  const common = {
    className,
    viewBox: '0 0 48 48',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  }

  switch (name) {
    // Invoice / billing document
    case 'invoice':
      return (
        <svg {...common}>
          <path d="M12 5h18l6 6v32H12V5Z" />
          <path d="M30 5v6h6" />
          <path d="M17 20h14M17 26h14M17 32h9" />
        </svg>
      )
    // Rate engine — calculator / pricing
    case 'calculator':
      return (
        <svg {...common}>
          <rect x="10" y="5" width="28" height="38" rx="3" />
          <rect x="15" y="10" width="18" height="7" rx="1" />
          <path d="M16 24h.02M24 24h.02M32 24h.02M16 31h.02M24 31h.02M32 31h.02M16 38h.02M24 38h.02M32 38h.02" />
        </svg>
      )
    // Shipment — delivery truck
    case 'truck':
      return (
        <svg {...common}>
          <path d="M4 12h20v18H4z" />
          <path d="M24 18h9l7 7v5H24z" />
          <circle cx="13" cy="34" r="4" />
          <circle cx="33" cy="34" r="4" />
          <path d="M17 34h10" />
        </svg>
      )
    // Dispute — shield / protection
    case 'shield':
      return (
        <svg {...common}>
          <path d="M24 5 40 11v11c0 10-7 17-16 21-9-4-16-11-16-21V11l16-6Z" />
          <path d="M17 23l5 5 9-10" />
        </svg>
      )
    // Extra logistics glyphs for the dashboard / decorative use
    case 'package':
      return (
        <svg {...common}>
          <path d="M24 5 42 14v20L24 43 6 34V14L24 5Z" />
          <path d="M6 14l18 9 18-9M24 23v20M15 9.5l18 9" />
        </svg>
      )
    case 'globe':
      return (
        <svg {...common}>
          <circle cx="24" cy="24" r="19" />
          <path d="M5 24h38M24 5c6 5 6 33 0 38M24 5c-6 5-6 33 0 38M9 13c9 5 21 5 30 0M9 35c9-5 21-5 30 0" />
        </svg>
      )
    case 'barcode':
      return (
        <svg {...common}>
          <path d="M8 12v24M13 12v24M18 12v18M23 12v24M28 12v18M33 12v24M38 12v24" />
        </svg>
      )
    case 'chip':
      return (
        <svg {...common}>
          <rect x="14" y="14" width="20" height="20" rx="2" />
          <rect x="20" y="20" width="8" height="8" rx="1" />
          <path d="M20 8v6M28 8v6M20 34v6M28 34v6M8 20h6M8 28h6M34 20h6M34 28h6" />
        </svg>
      )
    default:
      return (
        <svg {...common}>
          <circle cx="24" cy="24" r="16" />
        </svg>
      )
  }
}
