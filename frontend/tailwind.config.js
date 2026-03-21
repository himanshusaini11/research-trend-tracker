/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        bg:             '#0a0a0f',
        surface:        '#12121a',
        border:         '#1e1e2e',
        'accent-blue':  '#4a9eff',
        'accent-green': '#00d4aa',
        'accent-red':   '#ff6b6b',
        'accent-gray':  '#8892a4',
        'text-primary': '#e2e8f0',
        'text-muted':   '#64748b',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
