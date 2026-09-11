import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'.',testMatch:'browser-cards.spec.js',workers:2,
  use:{baseURL:'http://127.0.0.1:4180',trace:'retain-on-failure'},
  projects:[
    {name:'desktop',use:{browserName:'chromium',viewport:{width:1280,height:900}}},
    {name:'phone',use:{browserName:'chromium',viewport:{width:390,height:844}}},
    {name:'narrow',use:{browserName:'chromium',viewport:{width:320,height:800}}},
    {name:'webkit',use:{browserName:'webkit',viewport:{width:390,height:844}}},
  ],
});
