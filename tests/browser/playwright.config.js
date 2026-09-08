import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir: '.', testMatch: '*.spec.js', fullyParallel: true,
  forbidOnly: !!process.env.CI, retries: 0, workers: process.env.CI ? 2 : undefined,
  timeout: 30000, expect: {timeout: 6000},
  reporter: [['list'], ['html', {outputFolder: 'synthetic-results', open: 'never'}]],
  outputDir: 'test-results',
  use: {baseURL: 'http://127.0.0.1:4180', screenshot: 'only-on-failure', trace: 'retain-on-failure'},
  webServer: [
    {command: 'python server.py', url: 'http://127.0.0.1:4180/complete.html', reuseExistingServer: false},
    {command: 'node history-server.mjs', url: 'http://127.0.0.1:4181/maimai/history', reuseExistingServer: false,timeout:60000},
    {command: 'node installation-server.mjs', url: 'http://127.0.0.1:4182/alpha/', reuseExistingServer: false,timeout:60000},
  ],
  projects: [
    {name: 'desktop', use: {browserName: 'chromium', viewport: {width:1280,height:900}}},
    {name: 'tablet', use: {browserName: 'chromium', viewport: {width:768,height:1024}}},
    {name: 'phone', use: {browserName: 'chromium', viewport: {width:390,height:844}}},
    {name: 'narrow', use: {browserName: 'chromium', viewport: {width:320,height:800}}},
    {name: 'webkit-phone', use: {browserName: 'webkit', viewport: {width:390,height:844}}},
  ],
});
