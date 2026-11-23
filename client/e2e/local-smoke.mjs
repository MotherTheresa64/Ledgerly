// Local end-to-end smoke test against the Firebase Auth emulator. See README "Local mode".
// Env: APP_URL (default http://127.0.0.1:5173), EMULATOR (default 127.0.0.1:9099),
//      PLAYWRIGHT_DIR (path to a playwright install), CHROME_PATH (optional chromium executable).
import { createRequire } from 'node:module'

const APP = process.env.APP_URL || 'http://127.0.0.1:5173'
const EMU = process.env.EMULATOR || '127.0.0.1:9099'
const PROJECT = 'demo-ledgerly'
const email = process.env.TEST_EMAIL || `smoke-${Date.now()}@example.com`
const password = process.env.TEST_PASSWORD || 'LocalSmoke!234'
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT_DIR || 'playwright')

const assert = (ok, msg) => { if (!ok) throw new Error(`FAIL: ${msg}`); console.log(`ok - ${msg}`) }
const emu = (path, init) => fetch(`http://${EMU}/${path}`, init).then((r) => r.json())

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true })
const page = await browser.newPage()
page.on('pageerror', (e) => console.error('pageerror:', e.message))
try {
  await page.goto(APP)
  await page.getByRole('button', { name: 'Need an account? Register' }).click()
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await page.getByRole('button', { name: /I verified my email/ }).waitFor()
  assert(true, 'registered, waiting for email verification')

  // Verify through the emulator: apply the verifyEmail oobCode it recorded.
  const { oobCodes } = await emu(`emulator/v1/projects/${PROJECT}/oobCodes`)
  const code = oobCodes.filter((c) => c.email === email && c.requestType === 'VERIFY_EMAIL').pop()
  assert(code, 'emulator recorded a verification code')
  await emu('identitytoolkit.googleapis.com/v1/accounts:update?key=x', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ oobCode: code.oobCode }),
  })

  await page.getByRole('button', { name: /I verified my email/ }).click()
  await page.getByRole('button', { name: 'Load fictional demo data' }).click()
  await page.getByText('Fictional demo data loaded').waitFor()
  assert(true, 'signed in and loaded demo data')

  await page.getByRole('button', { name: 'Transactions', exact: true }).click()
  const description = `Smoke test ${Date.now()}`
  await page.getByPlaceholder('e.g. Grocery run').fill(description)
  await page.getByPlaceholder('0.00').first().fill('12.34')
  await page.getByPlaceholder('Groceries').fill('Groceries')
  await page.getByRole('button', { name: 'Save transaction' }).click()
  await page.getByText(description).first().waitFor()
  assert(true, 'added a transaction')
  console.log(`PASS (user ${email})`)
} catch (error) {
  await page.screenshot({ path: 'e2e/local-smoke-failure.png' }).catch(() => {})
  console.error(error.message)
  process.exitCode = 1
} finally {
  await browser.close()
}
