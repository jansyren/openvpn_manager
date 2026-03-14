import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('redirects unauthenticated users to login', async ({ page }) => {
    await expect(page).toHaveURL(/.*login.*/)
  })

  test('shows login form', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('text=OpenVPN Manager')).toBeVisible()
    await expect(page.locator('#username')).toBeVisible()
    await expect(page.locator('#password')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()
  })

  test('shows error on invalid credentials', async ({ page }) => {
    await page.goto('/login')
    await page.fill('#username', 'wronguser')
    await page.fill('#password', 'wrongpassword')
    await page.click('button[type="submit"]')
    await expect(page.locator('text=Invalid username or password')).toBeVisible()
  })

  test('requires both fields', async ({ page }) => {
    await page.goto('/login')
    await page.click('button[type="submit"]')
    await expect(page.locator('text=Username and password are required')).toBeVisible()
  })
})
