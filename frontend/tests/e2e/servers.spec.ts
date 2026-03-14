import { test, expect } from '@playwright/test'

// Helper: authenticate as admin
async function loginAsAdmin(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.fill('#username', 'admin')
  await page.fill('#password', 'Admin123!')
  await page.click('button[type="submit"]')
  await page.waitForURL('/')
}

test.describe('Servers', () => {
  test.skip(
    process.env.E2E_WITH_BACKEND !== '1',
    'Skipped: requires running backend with seed data'
  )

  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('shows servers page', async ({ page }) => {
    await page.goto('/servers')
    await expect(page.locator('h1')).toContainText('Servers')
  })

  test('add server button visible for superuser', async ({ page }) => {
    await page.goto('/servers')
    await expect(page.locator('button', { hasText: 'Add Server' })).toBeVisible()
  })

  test('navigate to add server form', async ({ page }) => {
    await page.goto('/servers')
    await page.click('button:has-text("Add Server")')
    await expect(page).toHaveURL(/.*servers\/new.*/)
    await expect(page.locator('h1')).toContainText('Add Server')
  })
})
