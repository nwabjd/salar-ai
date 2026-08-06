import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const landing = readFileSync(new URL('./components/SalaarLanding.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')
const css = readFileSync(new URL('./landing.css', import.meta.url), 'utf8')

describe('pricing + wallet/paypal checkout surface', () => {
  it('renders three plans with Pro featured', () => {
    expect(landing).toContain('priceId="price_pro"')
    expect(landing).toContain('priceId="price_team"')
    expect(landing).toContain('priceId="price_free"')
  })

  it('offers a Pricing nav link and section anchor', () => {
    expect(landing).toMatch(/href="#pricing"/)
    expect(landing).toContain('id="pricing"')
  })

  it('wires handleCheckout through the SalarApi client', () => {
    expect(landing).toContain('async function handleCheckout')
    expect(landing).toContain('api.billingCheckout')
  })

  it('supports the wallet-native signing flow in the client API', () => {
    expect(api).toContain('billingCheckout(')
    expect(api).toContain('/api/billing/checkout')
    expect(api).toContain('billingVerify(')
    expect(api).toContain('/api/billing/verify')
  })

  it('requests a wallet signature and verifies it in handleCheckout', () => {
    expect(landing).toContain('eth_requestAccounts')
    expect(landing).toContain('personal_sign')
    expect(landing).toContain('api.billingVerify')
  })

  it('styles the pricing grid and cards in landing.css', () => {
    expect(css).toContain('.pricing-grid')
    expect(css).toContain('.price-card')
    expect(css).toContain('.price-cta')
  })
})
