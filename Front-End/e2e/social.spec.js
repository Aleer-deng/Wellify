import { test, expect } from '@playwright/test';

// Isolate provider UI checks from external OAuth services and saved sessions.
test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/profile/', route => route.fulfill({ status: 403, json: { detail: 'Authentication credentials were not provided.' } }));
  await page.route('**/api/v1/auth/providers/', route => route.fulfill({ json: { providers: [] } }));
  await page.route('**/api/v1/auth/csrf/', route => route.fulfill({ json: { csrfToken: 'test-csrf-token' } }));
});

test('login offers provider options and unconfigured options preserve email sign-in', async ({ page }) => {
  await page.route('**/api/v1/auth/providers/', route => route.fulfill({ json: { providers: [
    { id: 'google', enabled: false }, { id: 'apple', enabled: false }, { id: 'microsoft', enabled: false },
  ] } }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Log in to Wellify', exact: true }).click();
  for (const provider of ['Google', 'Apple', 'Microsoft']) {
    await page.getByRole('button', { name: `Continue with ${provider}` }).click();
    await expect(page.getByRole('alert')).toContainText(`${provider} sign-in is not available yet`);
  }
  await expect(page.getByLabel('Email or username')).toBeVisible();
  await expect(page.getByLabel('Password', { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('provider errors return to login and are explained', async ({ page }) => {
  await page.goto('/?auth_error=existing_account');
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Please sign in with your original method');
  await expect(page).not.toHaveURL(/auth_error/);
});

test('configured provider starts with a CSRF-protected browser POST', async ({ page }) => {
  await page.route('**/api/v1/auth/providers/', route => route.fulfill({ json: { providers: [{ id: 'google', enabled: true }] } }));
  let submitted;
  await page.route('**/api/v1/auth/social/google/login/', route => {
    submitted = route.request();
    return route.fulfill({ contentType: 'text/html', body: '<p>Provider navigation started</p>' });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Log in to Wellify', exact: true }).click();
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  await expect(page.getByText('Provider navigation started')).toBeVisible();
  expect(submitted.method()).toBe('POST');
  expect(new URLSearchParams(submitted.postData()).get('csrfmiddlewaretoken')).toBeTruthy();
});
