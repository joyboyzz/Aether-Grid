/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html","./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {950:"#050913",900:"#0a0f1e",800:"#0e172a",700:"#15203a",600:"#1e2c4d",500:"#344466"},
        ag: {green:"#00e0a4",blue:"#3fa9ff",orange:"#ff7a18",red:"#ff4c5c",amber:"#ffc845",purple:"#a78bfa"}
      },
      fontFamily: { sans: ["Inter","ui-sans-serif","system-ui","-apple-system","Segoe UI","Roboto"] },
      boxShadow: { glow: "0 0 24px rgba(0,224,164,.35)" },
    },
  },
  safelist: [
    {pattern: /(bg|text|border)-(emerald|sky|amber|rose|indigo|cyan|orange|violet)-(50|100|200|300|400|500|600|700)(\/(10|15|20|30|50|70))?/},
  ],
  plugins: [],
};
