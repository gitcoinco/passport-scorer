/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        purple: {
          softpurple: "#757087",
          gitcoinviolet: "#6F3FF5",
        },
        blue: {
          darkblue: "#0E0333",
        },
        gray: {
          lightgray: "#E2E0E7",
          purplegray: "",
          bluegray: "#F3F4F6",
        },
        green: {
          gitcoingreen: "#02E2AC",
        }
      },
    },
    fontFamily: {
      miriamlibre: ["miriam libre"],
      librefranklin: ["Libre Franklin"],
      body: ['"Libre Franklin"'],
    },
  },
  plugins: [],
}
