// Standalone existing-report checks, without installation or catalog fixtures.
import base from './playwright.config.js';
export default {
  ...base,
  testMatch: ['report.spec.js', 'score-sort.spec.js', 'playercard.spec.js', 'badges.spec.js', 'compact-targets.spec.js'],
  webServer: base.webServer.slice(0, 1),
};
