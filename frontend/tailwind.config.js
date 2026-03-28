/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      // Colors use CSS channel variables so opacity modifiers (bg-bg/50) work
      colors: {
        bg:             'rgb(var(--color-bg) / <alpha-value>)',
        surface:        'rgb(var(--color-surface) / <alpha-value>)',
        border:         'rgb(var(--color-border) / <alpha-value>)',
        'accent-blue':  'rgb(var(--color-accent-blue) / <alpha-value>)',
        'accent-green': 'rgb(var(--color-accent-green) / <alpha-value>)',
        'accent-red':   'rgb(var(--color-accent-red) / <alpha-value>)',
        'accent-gray':  'rgb(var(--color-accent-gray) / <alpha-value>)',
        'text-primary': 'rgb(var(--color-text-primary) / <alpha-value>)',
        'text-muted':   'rgb(var(--color-text-muted) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
