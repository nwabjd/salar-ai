import { useEffect, useState } from 'react'
import { api } from '../api'

export const PLANS = [
  { plan: 'free', name: 'Free', price: '$0', period: 'forever', blurb: 'Start with the core companion.', cta: 'Stay free', priceId: 'price_free', featured: false, features: ['Full web + mobile companion', 'Local & encrypted memory', '5 devices', 'Community support'] },
  { plan: 'pro', name: 'Pro', price: '$12', period: '/mo', blurb: 'For your everyday chief of staff.', cta: 'Upgrade to Pro', priceId: 'price_pro', featured: true, features: ['Everything in Free', 'Advanced agents & automations', 'Priority models', 'Unlimited devices', 'Priority support'] },
  { plan: 'team', name: 'Team', price: '$24', period: '/mo', blurb: 'For small teams and families.', cta: 'Go Team', priceId: 'price_team', featured: false, features: ['Everything in Pro', 'Shared workspace', 'Team tasks', 'Group calendar sync', 'Dedicated onboarding'] },
]

function Page({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="page">
      <span className="eyebrow">SALAR WORKSPACE</span>
      <h1>{title}</h1>
      <p>{subtitle}</p>
      {children}
    </div>
  )
}

export function PricingPage({ connected, onClose }: { connected: boolean; onClose?: () => void }) {
  const [billing, setBilling] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [note, setNote] = useState('')
  const [choosing, setChoosing] = useState<string | null>(null)

  useEffect(() => {
    if (!connected) { setLoading(false); return }
    api.billingStatus()
      .then(setBilling)
      .catch(() => undefined)
      .finally(() => setLoading(false))
  }, [connected])

  async function checkout(priceId: string, method?: 'wallet' | 'paypal') {
    const rec = PLANS.find(p => p.priceId === priceId)
    if (!rec) return
    if (rec.plan === 'free') {
      setBusy(priceId)
      setNote('')
      try {
        await api.billingSetPlan('free')
        setNote("You're on the Free plan.")
        setBilling(await api.billingStatus())
      } catch (err: any) {
        setNote(err?.message || 'Could not switch plans.')
      } finally {
        setBusy('')
      }
      return
    }
    if (!method) { setChoosing(choosing === priceId ? null : priceId); return }
    setChoosing(null)
    setBusy(`${priceId}:${method}`)
    setNote('')
    try {
      const data = await api.billingCheckout(priceId, undefined, method === 'paypal')
      if (data?.kind === 'paypal' && data?.approval_url) { window.location.assign(data.approval_url); return }
      if (method === 'paypal') { setNote('PayPal is not configured yet. Try the crypto wallet instead.'); return }
      const eth = (window as any).ethereum
      if (!eth) { setNote('No wallet detected. Install MetaMask or another Ethereum wallet, or choose PayPal.'); return }
      const accounts = await eth.request({ method: 'eth_requestAccounts' })
      const from = accounts[0]
      const signature = await eth.request({ method: 'personal_sign', params: [from, data.message] })
      const verified = await api.billingVerify(data.intent_id, from, signature)
      if (verified?.verified) {
        setNote(`You're on the ${rec.name} plan.`)
        setBilling(await api.billingStatus())
      } else {
        setNote('Signature verified but the upgrade could not be applied.')
      }
    } catch (err: any) {
      setNote(err?.message || 'Could not start checkout.')
    } finally {
      setBusy('')
    }
  }

  const exempt = billing?.exempt ?? false
  const limit = billing?.limit ?? null
  const usage = billing?.usage ?? 0
  const pct = limit ? Math.min(100, Math.round((usage / limit) * 100)) : 0
  const plan = billing?.plan ?? 'free'
  const planName = plan === 'free' ? 'Free' : plan === 'pro' ? 'Pro' : 'Team'

  return (
    <Page title="Plan & billing" subtitle="Manage your Salaar plan and monitor usage.">
      {onClose && <button className="billing-back" onClick={onClose}>← Back</button>}
      <div className="billing-card">
        <div className="billing-meta">
          <div>
            <span className="eyebrow">CURRENT PLAN</span>
            <h2 className="plan-name">{exempt ? 'Admin (unlimited)' : planName}</h2>
          </div>
          <div className="usage-meter">
            <div className="usage-label"><span>{usage.toLocaleString()} / {limit === null ? 'unlimited' : limit.toLocaleString()} messages</span><span>{limit === null ? '∞' : `${pct}%`}</span></div>
            <div className="usage-bar"><i style={{ width: `${pct}%` }} /></div>
            {!exempt && plan === 'free' && <small>Free plans are limited to {limit?.toLocaleString()} messages/month. Upgrade for unlimited.</small>}
            {exempt && <small>Admin accounts are exempt from monthly limits.</small>}
          </div>
        </div>
        {loading && <div className="loading-hint">Loading…</div>}
        {!connected && !loading && <div className="loading-hint">Sign in to see your plan.</div>}
        {note && <div className="billing-note">{note}</div>}
      </div>

      <div className="grid grid-billing">
        {PLANS.map(p => {
          const current = plan === p.plan
          const isChoosing = choosing === p.priceId
          return (
            <article className={`card billing-tier${p.featured ? ' featured' : ''}${current ? ' current' : ''}`} key={p.plan}>
              <div><h3>{p.name}</h3>{p.featured && <span className="badge">Popular</span>}</div>
              <div className="price">{p.price}<small> {p.period}</small></div>
              <p>{p.blurb}</p>
              <ul>
                {p.features.map(f => <li key={f}>✓ {f}</li>)}
              </ul>
              {isChoosing ? (
                <div className="method-row">
                  <button className="btn" onClick={() => checkout(p.priceId, 'wallet')} disabled={!!busy}>Pay with crypto wallet</button>
                  <button className="btn" onClick={() => checkout(p.priceId, 'paypal')} disabled={!!busy}>Pay with PayPal</button>
                  <button className="btn method-cancel" onClick={() => setChoosing(null)} disabled={!!busy}>Cancel</button>
                </div>
              ) : (
                <button
                  className={`btn${p.featured ? ' btn-primary' : ' btn-ghost'}`}
                  onClick={() => checkout(p.priceId)}
                  disabled={current || !!busy}
                >
                  {current ? 'Current plan' : busy ? 'Starting…' : p.cta}
                </button>
              )}
            </article>
          )
        })}
      </div>

      <p className="billing-foot">Payments are processed via your crypto wallet or PayPal. Crypto payments are signed on-chain; PayPal uses a card or balance. Cancel anytime from this page.</p>
    </Page>
  )
}
