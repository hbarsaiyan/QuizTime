/** @type {import('tailwindcss').Config} */
module.exports = {
	content: [
		'./templates/**/*.html',
		'./static/src/**/*.js',
		'./node_modules/flowbite/**/*.js',
	],
	theme: {
		screens: {
			sm: '640px',
			md: '768px',
			lg: '1024px',
			xl: '1280px',
		},
		extend: {
      fontFamily: {
        'belanosima': ['Belanosima', 'sans-serif']
      },
      colors: {
        'regal-purple': '#4f46e5',
        'regal-blue': '#7D7CF9',
      },
    },
	},
	plugins: [require('@tailwindcss/forms'), require('flowbite/plugin')],
};
