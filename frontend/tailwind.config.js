/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      zIndex: {
        header: '10',
        sub: '20',
        overlay: '50',
        modal: '100',
        toast: '150',
      },
      fontFamily: {
        crayon: ['HakgyoansimDoldam', 'sans-serif'],
        pretendard: ['Pretendard', 'sans-serif'],
      },
      colors: {
        brand: {
          light: '#f3f4f6',
          DEFAULT: '#9ca3af',
          dark: '#4b5563',
        },
        crayon: {
          bg: '#fdfaf0',
          line: '#1f2937', // gray-800
        }
      }
    },
  },
  plugins: [],
}
