const plugin = require('tailwindcss/plugin');

// Mesa palette from Plane mesa.css, with controls from Studio and OS tokens.
// Scope it to staff pages; customer widgets keep their inbox branding.
const light = {
  '--slate-1': '253 250 244',
  '--slate-2': '247 245 240',
  '--slate-3': '239 234 225',
  '--slate-4': '231 225 214',
  '--slate-5': '220 211 198',
  '--slate-6': '203 192 175',
  '--slate-7': '184 170 147',
  '--slate-8': '163 146 120',
  '--slate-9': '139 128 109',
  '--slate-10': '119 108 91',
  '--slate-11': '106 100 88',
  '--slate-12': '48 61 71',
  '--background-color': '253 250 244',
  '--surface-1': '247 245 240',
  '--surface-2': '255 255 255',
  '--surface-active': '239 234 225',
  '--solid-1': '255 255 255',
  '--solid-2': '255 255 255',
  '--solid-3': '247 245 240',
  '--solid-active': '239 234 225',
  '--card-color': '255 255 255',
  '--border-container': '235 222 222',
  '--border-weak': '235 222 222',
  '--border-strong': '163 146 120',
  '--button-color': '255 255 255',
  '--label-background': '247 245 240',
  '--alpha-1': '106, 100, 88, 0.06',
  '--alpha-2': '106, 100, 88, 0.09',
  '--alpha-3': '255, 255, 255, 0.98',
  '--black-alpha-1': '112, 18, 47, 0.14',
  '--black-alpha-2': '106, 100, 88, 0.04',
  '--mesa-rail-start': '#70122f',
  '--mesa-rail-end': '#590c26',
};

const dark = {
  '--slate-1': '27 23 20',
  '--slate-2': '34 29 24',
  '--slate-3': '41 35 29',
  '--slate-4': '50 42 34',
  '--slate-5': '58 49 40',
  '--slate-6': '74 63 52',
  '--slate-7': '99 89 77',
  '--slate-8': '124 119 109',
  '--slate-9': '146 137 124',
  '--slate-10': '164 155 142',
  '--slate-11': '168 162 152',
  '--slate-12': '247 245 240',
  '--background-color': '27 23 20',
  '--surface-1': '34 29 24',
  '--surface-2': '34 29 24',
  '--surface-active': '50 42 34',
  '--solid-1': '34 29 24',
  '--solid-2': '34 29 24',
  '--solid-3': '41 35 29',
  '--solid-active': '50 42 34',
  '--card-color': '34 29 24',
  '--border-container': '59 54 48',
  '--border-weak': '59 54 48',
  '--border-strong': '124 119 109',
  '--button-color': '41 35 29',
  '--label-background': '41 35 29',
  '--alpha-1': '247, 245, 240, 0.06',
  '--alpha-2': '247, 245, 240, 0.10',
  '--alpha-3': '34, 29, 24, 0.98',
  '--black-alpha-1': '0, 0, 0, 0.30',
  '--black-alpha-2': '0, 0, 0, 0.18',
  '--mesa-rail-start': '#2b0014',
  '--mesa-rail-end': '#230b14',
};

const accent = {
  '--mesa-brand': '190 53 47',
  '--mesa-brand-text': '143 39 37',
  '--blue-1': '253 250 244',
  '--blue-2': '255 246 242',
  '--blue-3': '255 238 238',
  '--blue-4': '252 222 220',
  '--blue-5': '246 204 200',
  '--blue-6': '234 175 171',
  '--blue-7': '215 136 129',
  '--blue-8': '192 95 85',
  '--blue-9': '190 53 47',
  '--blue-10': '143 39 37',
  '--blue-11': '143 39 37',
  '--blue-12': '112 18 47',
  '--solid-blue': '255 238 238',
  '--solid-blue-2': '255 246 242',
  '--text-blue': '112 18 47',
  '--border-blue': '190, 53, 47, 0.5',
  '--border-blue-strong': '143 39 37',
};

const darkAccent = {
  '--mesa-brand-text': '243 123 118',
  '--blue-1': '27 23 20',
  '--blue-2': '43 29 27',
  '--blue-3': '57 33 36',
  '--blue-4': '74 39 42',
  '--blue-5': '94 47 48',
  '--blue-6': '119 55 54',
  '--blue-7': '155 65 60',
  '--blue-8': '190 76 70',
  '--blue-11': '243 123 118',
  '--blue-12': '249 181 178',
  '--solid-blue': '57 33 36',
  '--solid-blue-2': '43 29 27',
  '--text-blue': '249 181 178',
  '--border-blue-strong': '243 123 118',
};

const rail = {
  '--slate-1': '112 18 47',
  '--slate-2': '112 18 47',
  '--slate-3': '124 38 65',
  '--slate-4': '135 49 72',
  '--slate-5': '161 81 101',
  '--slate-9': '255 255 255',
  '--slate-10': '232 198 211',
  '--slate-11': '245 225 231',
  '--slate-12': '255 255 255',
  '--background-color': '112 18 47',
  '--button-color': '124 38 65',
  '--border-weak': '135 49 72',
  '--border-strong': '135 49 72',
  '--alpha-1': '255, 255, 255, 0.08',
  '--alpha-2': '255, 255, 255, 0.12',
  '--mesa-brand': '249 181 178',
  '--mesa-brand-text': '255 255 255',
};

module.exports = plugin(({ addBase, addUtilities, addVariant }) => {
  addVariant('mesa', '.mesa-dashboard &');
  addBase({
    '@font-face': {
      fontFamily: 'Mesa Fraunces',
      src: "url('/mesa/fonts/fraunces-latin-standard-normal.woff2') format('woff2')",
      fontWeight: '100 900',
      fontStyle: 'normal',
      fontDisplay: 'swap',
    },
    '.mesa-dashboard': {
      ...light,
      ...accent,
      fontFamily: 'Inter, system-ui, sans-serif',
      letterSpacing: '-0.011em',
    },
    '.mesa-dashboard.dark, .dark .mesa-dashboard, .mesa-dashboard .dark': {
      ...dark,
      ...accent,
      ...darkAccent,
    },
    '.mesa-dashboard .text-n-brand, .mesa-dashboard .dark\\:text-n-brand': {
      color: 'rgb(var(--mesa-brand-text))',
    },
    '.mesa-dashboard h1, .mesa-dashboard h2': {
      fontFamily: "'Mesa Fraunces', Georgia, serif",
      letterSpacing: '-0.02em',
    },
  });
  addUtilities({
    '.bg-mesa-cta': {
      backgroundImage:
        'linear-gradient(96deg, rgba(0,0,0,0.2) 0%, transparent 46%, rgba(255,212,81,0.06) 100%)',
    },
    '.mesa-sidebar': {
      ...rail,
      backgroundImage:
        'linear-gradient(180deg, var(--mesa-rail-start), var(--mesa-rail-end))',
    },
    '.dark .mesa-sidebar': {
      '--background-color': '35 11 20',
      '--button-color': '64 28 41',
      '--slate-3': '64 28 41',
      '--slate-4': '68 35 49',
      '--slate-5': '85 47 65',
      '--border-weak': '68 35 49',
      '--border-strong': '68 35 49',
    },
    // Floating menus inside the rail must use content-surface colors.
    '.mesa-surface': { ...light, ...accent },
    '.dark .mesa-surface': { ...dark, ...accent, ...darkAccent },
  });
});
