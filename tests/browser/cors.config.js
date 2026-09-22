import {defineConfig} from '@playwright/test';
import base from './playwright.config.js';
export default defineConfig({...base,testMatch:'public-player-import.spec.js',webServer:undefined});
