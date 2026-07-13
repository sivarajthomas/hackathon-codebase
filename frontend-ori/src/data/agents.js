// Central definition of the 4 UPS logistics-billing AI agents.

export const agents = [
  {
    id: 'explain',
    slug: 'explain',
    name: 'Explain',
    role: 'Billing Analyst',
    tagline: 'Every charge, clearly explained.',
    description:
      'Explains every invoice charge by breaking down billing components, showing how each cost was calculated, and answering customer questions about invoice details.',
    accent: '#ffb500',
    accentSoft: 'rgba(255,181,0,0.16)',
    gradient: 'from-amber-400/30 via-yellow-600/10 to-transparent',
    icon: 'invoice',
    videoPoster: 'linear-gradient(135deg,#2b1810,#3a2410 45%,#241206)',
    greeting:
      "Explain Agent online. Share an invoice number or a specific charge and I'll break down every billing component and show exactly how it was calculated.",
    placeholder: 'Enter invoice number, date & your query',
    stats: [
      { label: 'Invoices Explained', value: 1284000, format: 'compact' },
      { label: 'Resolution Rate', value: 94.3, suffix: '%' },
      { label: 'Avg. Response', value: 1.2, suffix: 's' },
    ],
    prompts: [
      'Break down every charge on invoice INV0001',
      'Why is the fuel surcharge on INV0004 so high?',
      'How was the 2250 kg billable weight for SHP0001 calculated?',
    ],
  },
  {
    id: 'resolve',
    slug: 'resolve',
    name: 'Resolve',
    role: 'Dispute Specialist',
    tagline: 'Disputes closed, fairly and fast.',
    description:
      'Investigates and resolves invoice disputes by validating shipment data, contracts, and rate cards, then recommending the appropriate resolution.',
    accent: '#3d7bff',
    accentSoft: 'rgba(61,123,255,0.16)',
    gradient: 'from-blue-400/30 via-blue-600/10 to-transparent',
    icon: 'shield',
    videoPoster: 'linear-gradient(135deg,#0a1330,#0d1a45 45%,#050d26)',
    greeting:
      "Resolve Agent ready. Describe the dispute or share a claim reference and I'll validate the shipment data, check the rate card, and recommend the right resolution.",
    placeholder: 'Enter dispute / claim reference, date & your query',
    stats: [
      { label: 'Disputes Resolved', value: 148900, format: 'compact' },
      { label: 'Accuracy', value: 99.1, suffix: '%' },
      { label: 'Avg. Resolution', value: 2.1, suffix: 'd' },
    ],
    prompts: [
      'Investigate the duplicate fuel surcharge dispute DSP-0001 on INV0004',
      'Should the missing contracted discount on INV0011 be credited?',
      'Validate the weight dispute on INV0018 against the shipment record',
    ],
  },
  {
    id: 'simulate',
    slug: 'simulate',
    name: 'Simulate',
    role: 'Pricing Analyst',
    tagline: 'Model every scenario before you ship.',
    description:
      'Performs "what-if" cost analysis by recalculating shipping charges based on changes to shipment details, enabling customers to compare pricing scenarios.',
    accent: '#22c55e',
    accentSoft: 'rgba(34,197,94,0.16)',
    gradient: 'from-emerald-400/30 via-green-600/10 to-transparent',
    icon: 'calculator',
    videoPoster: 'linear-gradient(135deg,#07231a,#0a2f22 45%,#04160f)',
    greeting:
      "Simulate Agent active. Give me a shipment scenario and I'll recalculate the charges and show cost comparisons across service options.",
    placeholder: 'Enter shipment details & the scenario to simulate',
    stats: [
      { label: 'Simulations Run', value: 920000, format: 'compact' },
      { label: 'Pricing Accuracy', value: 99.9, suffix: '%' },
      { label: 'Avg. Quote Time', value: 0.4, suffix: 's' },
    ],
    prompts: [
      'What if SHP0005 shipped by Roadways instead of Airways?',
      'Recalculate INV0001 with insurance at the contracted 1.5% of value',
      'Compare Chennai\u2192Delhi freight cost across Air, Road and Ship',
    ],
  },
  {
    id: 'prevent',
    slug: 'prevent',
    name: 'Prevent',
    role: 'Risk & Compliance',
    tagline: 'Catch errors before they become disputes.',
    description:
      'Proactively identifies potential billing errors and dispute risks before invoices are issued by validating charges, detecting anomalies, and recommending corrective actions.',
    accent: '#ff2fb0',
    accentSoft: 'rgba(255,47,176,0.16)',
    gradient: 'from-pink-400/30 via-fuchsia-600/10 to-transparent',
    icon: 'chip',
    videoPoster: 'linear-gradient(135deg,#2a0620,#3a0830 45%,#1f0418)',
    greeting:
      "Prevent Agent scanning. Share an account or billing batch and I'll validate charges, flag anomalies, and recommend corrective actions before issues escalate.",
    placeholder: 'Enter invoice number, date & your query',
    stats: [
      { label: 'Errors Prevented', value: 64200, format: 'compact' },
      { label: 'Anomaly Detection', value: 97.8, suffix: '%' },
      { label: 'Pre-Issue Catch Rate', value: 91.4, suffix: '%' },
    ],
    prompts: [
      'Show the highest-value leakage findings still open',
      'Why was INV0002 flagged for surcharge not billed?',
      'Which contracts have the most insurance underbilling?',
    ],
    // Invoices flagged with potential billing issues — shown in a right sidebar
    // on the Prevent Agent workspace.
    issues: [
      { id: 'INV-48213', account: '7741', problem: 'Duplicate line item', amount: '$92.00', severity: 'high' },
      { id: 'INV-48090', account: '5530', problem: 'DIM weight mismatch', amount: '$44.00', severity: 'high' },
      { id: 'INV-47765', account: '3320', problem: 'Surcharge on waived account', amount: '$18.40', severity: 'medium' },
      { id: 'INV-47540', account: '9021', problem: 'Zone misclassification', amount: '$26.10', severity: 'medium' },
      { id: 'INV-47201', account: '7741', problem: 'Outdated fuel surcharge index', amount: '$12.75', severity: 'low' },
      { id: 'INV-46988', account: '6650', problem: 'Missing contract discount', amount: '$63.30', severity: 'high' },
      { id: 'INV-46754', account: '4408', problem: 'Residential fee on commercial', amount: '$5.20', severity: 'low' },
    ],
  },
]

export const getAgent = (slug) => agents.find((a) => a.slug === slug)

export const platformStats = [
  { label: 'Invoices Explained', value: 1284000, format: 'compact', accent: '#ffb500' },
  { label: 'Disputes Resolved', value: 148900, format: 'compact', accent: '#3d7bff' },
  { label: 'Billing Accuracy', value: 99.7, suffix: '%', accent: '#22c55e' },
  { label: 'Revenue Processed', value: 4.8, prefix: '$', suffix: 'B', accent: '#ffb500' },
  { label: 'Errors Prevented', value: 64200, format: 'compact', accent: '#ff8a3d' },
  { label: 'Simulations Run', value: 920000, format: 'compact', accent: '#22c55e' },
  { label: 'AI Requests Today', value: 512000, format: 'compact', accent: '#3d7bff' },
  { label: 'Avg. Response Time', value: 0.4, suffix: 's', accent: '#ff8a3d' },
]
