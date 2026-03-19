/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        soc: {
          bg:     '#030712',
          surface:'#0b1120',
          card:   '#111827',
          border: '#1f2937',
          text:   '#f3f4f6',
          muted:  '#8ca0bf',
          accent: '#6be8ff',
          safe:   '#53e2a1',
          warn:   '#f6c667',
          danger: '#ff5f8f',
        },
      },
      boxShadow: {
        'glow-blue': '0 0 12px rgba(107,232,255,0.3)',
      },
    },
  },
  plugins: [],
};
