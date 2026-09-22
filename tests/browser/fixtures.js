import {test as base, expect} from '@playwright/test';
import {isolatedTest} from './isolation.mjs';
export const test = isolatedTest(base, {origins: ['http://127.0.0.1:4180', 'http://127.0.0.1:4181', 'http://127.0.0.1:4182']});
export {expect};
