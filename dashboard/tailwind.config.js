/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0fdf4',
          500: '#22c55e',
          600: '#16a34a',
          900: '#14532d',
        },
        guard: {
          bg: '#0B0F19',
          card: '#111827',
          border: '#1F2937',
          hover: '#1E293B',
        }
      }
    },
  },
  plugins: [],
}
