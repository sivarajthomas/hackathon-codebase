/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Space Grotesk"', 'Inter', 'sans-serif'],
      },
      colors: {
        // Warm charcoal / near-black base — logistics command center.
        base: {
          900: '#0c0a09',
          800: '#141110',
          700: '#1d1815',
          600: '#271f19',
        },
        // UPS-inspired brand: deep brown + gold.
        brand: {
          brown: '#4a2c1a',
          brownDeep: '#2b1810',
          gold: '#ffb500',
          goldSoft: '#f5c65a',
        },
        // Operational accents.
        ops: {
          ai: '#3d7bff', // AI interactions
          active: '#ff8a3d', // active shipments
          done: '#22c55e', // completed processes
        },
        // Back-compat aliases (existing classes) mapped to the new palette.
        neon: {
          cyan: '#ffb500',
          violet: '#f5a623',
          pink: '#ff8a3d',
          blue: '#3d7bff',
        },
      },
      backgroundImage: {
        'radial-glow': 'radial-gradient(circle at 50% 40%, rgba(255,181,0,0.10), transparent 60%)',
        'grid-lines': 'linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)',
      },
      boxShadow: {
        glow: '0 0 40px -8px rgba(255,181,0,0.45)',
        'glow-violet': '0 0 50px -10px rgba(255,138,61,0.5)',
        panel: '0 20px 60px -15px rgba(0,0,0,0.75)',
      },
      backdropBlur: {
        xs: '2px',
      },
      keyframes: {
        float: {
          '0%,100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulseGlow: {
          '0%,100%': { opacity: '0.6' },
          '50%': { opacity: '1' },
        },
        sweep: {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(120%)' },
        },
      },
      animation: {
        float: 'float 6s ease-in-out infinite',
        shimmer: 'shimmer 3s linear infinite',
        pulseGlow: 'pulseGlow 3s ease-in-out infinite',
        sweep: 'sweep 3.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
