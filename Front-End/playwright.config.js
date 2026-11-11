import { defineConfig } from '@playwright/test';
export default defineConfig({
 testDir:'./e2e', fullyParallel:false, workers:1, timeout:240000,
 expect:{timeout:30000},
 use:{baseURL:'http://127.0.0.1:5174',browserName:'chromium',channel:'chrome',headless:true,trace:'off'},
 webServer:[
  {command:'"../Back-End/.venv/Scripts/python.exe" e2e/server.py',url:'http://127.0.0.1:8011/api/v1/status/',reuseExistingServer:false,timeout:120000},
  {command:'npm.cmd run dev -- --port 5174',url:'http://127.0.0.1:5174',env:{WELLIFY_API_TARGET:'http://127.0.0.1:8011'},reuseExistingServer:false,timeout:60000},
 ],
});
