import { mount } from 'svelte';
import App from './App.svelte';
import './app.css';

export default mount(App, { target: document.getElementById('app')! });

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
