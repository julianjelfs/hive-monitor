// Draws the icon and renders every size the app needs into public/.
// Run from frontend/: node scripts/icons.mjs
import { mkdir, writeFile } from 'node:fs/promises';
import sharp from 'sharp';

const INK = '#1d1f22';
const HONEY = '#f0a63a';

// A hexagon for Hive, with a heartbeat line through it: the thing being watched, and the watching.
// Drawn on a 512 grid centred on (256, 256).
function hexagon(r) {
	const points = [];
	for (let i = 0; i < 6; i++) {
		const a = (Math.PI / 3) * i - Math.PI / 2;
		points.push(`${(256 + r * Math.cos(a)).toFixed(1)},${(256 + r * Math.sin(a)).toFixed(1)}`);
	}
	return points.join(' ');
}

const drawing = `
  <polygon points="${hexagon(170)}" fill="none" stroke="${HONEY}" stroke-width="30" stroke-linejoin="round"/>
  <polyline points="120,262 196,262 226,196 268,330 300,232 320,262 392,262"
    fill="none" stroke="${HONEY}" stroke-width="28" stroke-linecap="round" stroke-linejoin="round"/>`;

function logo({ corner, scale }) {
	const inset = 256 * (1 - scale);
	return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="${corner}" fill="${INK}"/>
  <g transform="translate(${inset} ${inset}) scale(${scale})">${drawing}</g>
</svg>`;
}

const rounded = logo({ corner: 112, scale: 1 });
// Maskable icons get cropped to any shape, so keep the drawing inside the middle 80%.
const maskable = logo({ corner: 0, scale: 0.78 });
// iOS rounds the corners itself and shows transparency as black.
const square = logo({ corner: 0, scale: 0.9 });

const png = (svg, size) => sharp(Buffer.from(svg)).resize(size, size).png().toBuffer();

await mkdir('public/icons', { recursive: true });
await writeFile('public/favicon.svg', rounded);
await writeFile('public/favicon-32.png', await png(rounded, 32));
await writeFile('public/apple-touch-icon.png', await png(square, 180));
await writeFile('public/icons/icon-192.png', await png(rounded, 192));
await writeFile('public/icons/icon-512.png', await png(rounded, 512));
await writeFile('public/icons/maskable-512.png', await png(maskable, 512));
console.log('icons written to public/');
