import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState, type ClipboardEvent, type CSSProperties } from "react";
import { cleanAuthFromUrl, isSupabaseConfigured, supabase } from "../lib/supabase";
import { isDesktop } from "../access";
import { api } from "../api";
import LiquidEther from '../effects/LiquidEther.jsx'
import OnboardingWizard from "./OnboardingWizard";

type AuthStep = "choice" | "email" | "otp" | "preview" | "profile" | "companion" | "complete";
type OAuthProvider = "google" | "github" | "azure";
type CompanionId = "navigator" | "creator" | "guardian";

type IconProps = { size?: number; className?: string };

const Icon = {
  Arrow: ({ size = 18, className = "" }: IconProps) => (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5 12h14M14 7l5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  Check: ({ size = 18, className = "" }: IconProps) => (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m5 12 4.2 4.2L19 6.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  Close: ({ size = 20, className = "" }: IconProps) => (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  Spark: ({ size = 20, className = "" }: IconProps) => (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 2.8c.8 5.2 4 8.4 9.2 9.2-5.2.8-8.4 4-9.2 9.2-.8-5.2-4-8.4-9.2-9.2 5.2-.8 8.4-4 9.2-9.2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  ),
  Shield: ({ size = 22, className = "" }: IconProps) => (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3 4.8 6v5.3c0 4.6 2.9 8.1 7.2 9.7 4.3-1.6 7.2-5.1 7.2-9.7V6L12 3Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="m9 12 2 2 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  Brain: ({ size = 22, className = "" }: IconProps) => (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M9.3 4.5a3 3 0 0 0-5 2.2 3.4 3.4 0 0 0 .2 1.1A3.5 3.5 0 0 0 5.3 14a3.5 3.5 0 0 0 4 5.5V4.5ZM14.7 4.5a3 3 0 0 1 5 2.2 3.4 3.4 0 0 1-.2 1.1 3.5 3.5 0 0 1-.8 6.2 3.5 3.5 0 0 1-4 5.5V4.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9.3 9.2H7.8M14.7 9.2h1.5M9.3 14.8H7.6M14.7 14.8h1.7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  Orbit: ({ size = 22, className = "" }: IconProps) => (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="2.2" fill="currentColor" />
      <ellipse cx="12" cy="12" rx="9" ry="4.4" stroke="currentColor" strokeWidth="1.4" />
      <ellipse cx="12" cy="12" rx="9" ry="4.4" transform="rotate(60 12 12)" stroke="currentColor" strokeWidth="1.4" />
      <ellipse cx="12" cy="12" rx="9" ry="4.4" transform="rotate(120 12 12)" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  ),
  Menu: ({ size = 22, className = "" }: IconProps) => (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  ),
  Mail: ({ size = 20, className = "" }: IconProps) => (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="m5 8 7 5 7-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
};

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3Z" />
      <path fill="#34A853" d="M12 22c2.7 0 5-.9 6.6-2.4L15.4 17c-.9.6-2 1-3.4 1a5.8 5.8 0 0 1-5.5-4H3.2v2.6A10 10 0 0 0 12 22Z" />
      <path fill="#FBBC05" d="M6.5 14a6 6 0 0 1 0-3.9V7.5H3.2a10 10 0 0 0 0 9.1L6.5 14Z" />
      <path fill="#EA4335" d="M12 6c1.5 0 2.8.5 3.8 1.5l2.9-2.8A9.7 9.7 0 0 0 12 2a10 10 0 0 0-8.8 5.5l3.3 2.6A5.8 5.8 0 0 1 12 6Z" />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.8c-2.7.6-3.3-1.3-3.3-1.3-.4-1.1-1.1-1.4-1.1-1.4-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.6 2.4 1.1 3 .9.1-.7.4-1.1.6-1.4-2.2-.3-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.7 0 0 .8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.4 4.7-4.6 5 .4.3.7.9.7 1.9v2.8c0 .3.2.6.7.5A10 10 0 0 0 12 2Z" />
    </svg>
  );
}

function WalletIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M3.5 7A2.5 2.5 0 0 1 6 4.5h12A2.5 2.5 0 0 1 20.5 7v1.2M3.5 7v10A2.5 2.5 0 0 0 6 19.5h12a2.5 2.5 0 0 0 2.5-2.5V8.2" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx="16.8" cy="13.5" r="1.4" fill="currentColor" />
    </svg>
  );
}

function MicrosoftIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#F25022" d="M2 2h9.5v9.5H2z" />
      <path fill="#7FBA00" d="M12.5 2H22v9.5h-9.5z" />
      <path fill="#00A4EF" d="M2 12.5h9.5V22H2z" />
      <path fill="#FFB900" d="M12.5 12.5H22V22h-9.5z" />
    </svg>
  );
}

const capabilities = [
  { icon: <Icon.Brain />, title: "Learns your rhythm", text: "Salaar understands your habits, priorities and working style to become more helpful every day." },
  { icon: <Icon.Orbit />, title: "Connects your world", text: "Bring tasks, ideas, schedules and devices into one intelligent personal command center." },
  { icon: <Icon.Shield />, title: "Private by design", text: "Clear permission controls keep you in charge of what Salaar can see, remember and do." },
];

import { GlareHover } from './GlareHover';

function PriceCard({
  name,
  price,
  period,
  sub,
  features,
  priceId,
  busyId,
  choosing,
  onCheckout,
  onPickMethod,
  featured,
}: {
  name: string;
  price: string;
  period?: string;
  sub: string;
  features: string[];
  priceId: string;
  busyId: string;
  choosing: boolean;
  onCheckout: (priceId: string) => void;
  onPickMethod: (priceId: string, method: "wallet" | "paypal") => void;
  featured?: boolean;
}) {
  const isBusy = busyId === priceId;
  return (
    <div className={`price-card ${featured ? "featured" : ""}`}>
      <div className="price-head">
        <div className="price-name">{name}</div>
        <div className="price-line">
          <span className="price-amount">{price}</span>
          {period && <span className="price-period">{period}</span>}
        </div>
        <p className="price-sub">{sub}</p>
      </div>
      <ul className="price-features">
        {features.map((f) => (
          <li key={f}><Icon.Check size={15} /> {f}</li>
        ))}
      </ul>
      {choosing ? (
        <div className="price-methods">
          <button className="price-cta primary-button" onClick={() => onPickMethod(priceId, "wallet")} disabled={isBusy}>
            {isBusy ? "Connecting wallet…" : "Pay with crypto wallet"}
          </button>
          <button className="price-cta secondary-button" onClick={() => onPickMethod(priceId, "paypal")} disabled={isBusy}>
            {isBusy ? "Opening PayPal…" : "Pay with PayPal"}
          </button>
          <button className="price-cta price-cancel" onClick={() => onCheckout(priceId)} disabled={isBusy}>
            Cancel
          </button>
        </div>
      ) : (
        <button
          className={`price-cta ${featured ? "primary-button" : "secondary-button"}`}
          onClick={() => onCheckout(priceId)}
          disabled={isBusy}
        >
          {isBusy ? "Starting…" : featured ? `Get ${name}` : `Try ${name}`}
        </button>
      )}
    </div>
  );
}

const companions: Array<{ id: CompanionId; name: string; eyebrow: string; copy: string; traits: string[] }> = [
  {
    id: "navigator",
    name: "The Navigator",
    eyebrow: "Focus & execution",
    copy: "A calm chief of staff for planning, daily priorities, reminders and getting important work finished.",
    traits: ["Structured", "Proactive", "Calm"],
  },
  {
    id: "creator",
    name: "The Creator",
    eyebrow: "Ideas & expression",
    copy: "A curious creative partner for writing, visual thinking, brainstorming and turning concepts into reality.",
    traits: ["Imaginative", "Expressive", "Curious"],
  },
  {
    id: "guardian",
    name: "The Guardian",
    eyebrow: "Life & balance",
    copy: "A thoughtful personal guide for routines, reflection, learning and protecting time for what matters.",
    traits: ["Supportive", "Observant", "Grounded"],
  },
];

function attachWalletAddress(user: {
  user_metadata?: Record<string, unknown> | null;
  identities?: Array<{ provider: string; identity_data?: Record<string, unknown> | null }> | null;
}) {
  if (!supabase || !user || user.user_metadata?.wallet_address) return;
  const address = user.identities?.find((identity) => identity.provider === "ethereum")?.identity_data?.sub;
  if (typeof address === "string" && address) {
    supabase.auth.updateUser({ data: { wallet_address: address } }).catch(() => undefined);
  }
}

export default function SalaarLanding({ onEnterApp }: { onEnterApp?: (supabaseToken?: string | null) => Promise<boolean> }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [step, setStep] = useState<AuthStep>("choice");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [useCase, setUseCase] = useState("Everyday productivity");
  const [selectedCompanion, setSelectedCompanion] = useState<CompanionId>("navigator");
  const [busy, setBusy] = useState(false);
  const [entryBusy, setEntryBusy] = useState(false);
  const [pricingBusyId, setPricingBusyId] = useState<string>("");
  const [choosingPriceId, setChoosingPriceId] = useState<string>("");
  const [pricingError, setPricingError] = useState<string>("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [onboardingStarted, setOnboardingStarted] = useState(false);
  const otpRefs = useRef<Array<HTMLInputElement | null>>([]);
  const shellRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const shell = shellRef.current;
    if (!shell) return;
    const onPointerMove = (event: PointerEvent) => {
      shell.style.setProperty("--mouse-x", `${event.clientX}px`);
      shell.style.setProperty("--mouse-y", `${event.clientY}px`);
    };
    window.addEventListener("pointermove", onPointerMove);
    return () => window.removeEventListener("pointermove", onPointerMove);
  }, []);

  useEffect(() => {
    const observed = document.querySelectorAll<HTMLElement>("[data-reveal]");
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => entry.isIntersecting && entry.target.classList.add("is-visible")),
      { threshold: 0.14 }
    );
    observed.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!supabase) return;
    let mounted = true;

    async function handleSession(session: { user?: any; access_token?: string | null } | null) {
      const user = session?.user;
      if (!user || !session?.access_token) return;
      cleanAuthFromUrl();
      attachWalletAddress(user);
      setEmail(user.email ?? "");
      setFirstName((user.user_metadata?.first_name as string) ?? "");
      setLastName((user.user_metadata?.last_name as string) ?? "");
      if (user.user_metadata?.onboarding_complete) {
        const bridged = await onEnterApp?.(session.access_token);
        if (!mounted) return;
        if (!bridged) {
          setError("Signed in, but the Salaar backend could not be reached. Please try again in a moment.");
        }
        return;
      }
      setStep("profile");
      setModalOpen(true);
    }

    supabase.auth.getSession().then(({ data }) => { cleanAuthFromUrl(); void handleSession(data.session) });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => { void handleSession(session) });

    return () => { mounted = false; data.subscription.unsubscribe(); };
  }, []);

  useEffect(() => {
    const shell = shellRef.current;
    if (shell) shell.style.overflowY = modalOpen ? "hidden" : "auto";
  }, [modalOpen]);

  const progress = useMemo(() => {
    const map: Record<AuthStep, number> = { choice: 12, email: 28, otp: 48, preview: 54, profile: 68, companion: 86, complete: 100 };
    return map[step];
  }, [step]);

  function launchSignup() {
    setMessage("");
    setError("");
    setStep("choice");
    setModalOpen(true);
    setMenuOpen(false);
  }

  async function handleEnterApp() {
    if (entryBusy) return;
    setEntryBusy(true);
    const entered = await onEnterApp?.();
    if (!entered) launchSignup();
    setEntryBusy(false);
  }

  const PLAN_NAMES: Record<string, string> = { price_free: "Free", price_pro: "Pro", price_team: "Team" };

  async function handleCheckout(priceId: string, method?: "wallet" | "paypal") {
    setPricingError("");
    // Free plan has no payment — go straight to signup.
    if (priceId === "price_free") {
      launchSignup();
      return;
    }
    // First click asks which payment method to use.
    if (!method) {
      setChoosingPriceId(choosingPriceId === priceId ? "" : priceId);
      return;
    }
    setChoosingPriceId("");
    setPricingBusyId(priceId);
    try {
      const data = await api.billingCheckout(priceId, undefined, method === "paypal");
      // PayPal flow — redirect to the approval URL.
      if (data?.kind === "paypal" && data?.approval_url) {
        window.location.assign(data.approval_url);
        return;
      }
      if (method === "paypal") {
        setPricingError("PayPal checkout is not configured yet. Try the crypto wallet instead.");
        return;
      }
      // Wallet-native flow.
      const eth = (window as unknown as { ethereum?: any }).ethereum;
      if (!eth) {
        setPricingError("No wallet detected. Install MetaMask, Rabby, or another Ethereum wallet.");
        return;
      }
      const accounts = await eth.request({ method: "eth_requestAccounts" });
      const from = accounts[0];
      const signature = await eth.request({
        method: "personal_sign",
        params: [from, data.message],
      });
      const verified = await api.billingVerify(data.intent_id, from, signature);
      if (verified?.verified) {
        const planName = PLAN_NAMES[priceId] || "Pro";
        setMessage(`Your ${planName} plan is active — refresh to see your new limits.`);
        setModalOpen(false);
      } else {
        setPricingError("Signature verified but the upgrade could not be applied.");
      }
    } catch (err: any) {
      if (err?.message?.includes("not configured") || err?.message?.includes("501")) {
        // PayPal not configured — no crash, just surface via pricingError.
        setPricingError("PayPal checkout is not configured yet. Try wallet payment instead.");
      } else {
        setPricingError(err?.message || "Could not start checkout.");
      }
    } finally {
      setPricingBusyId("");
    }
  }

  function resetFeedback() {
    setError("");
    setMessage("");
  }

  async function handleOAuth(provider: OAuthProvider) {
    resetFeedback();
    if (!supabase) {
      setMessage("Preview mode: add Supabase keys to activate social sign-in. Opening the profile step for design testing.");
      window.setTimeout(() => setStep("profile"), 650);
      return;
    }

    setBusy(true);
    // Tauri desktop webviews cannot relay OAuth popup sessions back to the
    // opener window. Redirect the main window instead and let Supabase pick
    // the session out of the callback URL.
    if (isDesktop()) {
      const { data, error: authError } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: window.location.origin, skipBrowserRedirect: true },
      });
      if (authError) setError(authError.message);
      if (data?.url) {
        window.location.href = data.url;
        return;
      }
      setBusy(false);
      return;
    }
    const { error: authError } = await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo: window.location.origin },
    });
    if (authError) setError(authError.message);
    setBusy(false);
  }

  async function handleWalletSignIn() {
    resetFeedback();
    if (!supabase) {
      setMessage("Preview mode: add Supabase keys to activate wallet sign-in.");
      return;
    }
    if (typeof window === "undefined" || !(window as unknown as { ethereum?: unknown }).ethereum) {
      setError("No wallet detected. Install MetaMask or another Ethereum wallet to continue.");
      return;
    }

    setBusy(true);
    try {
      const { error: authError } = await supabase.auth.signInWithWeb3({
        chain: "ethereum",
        statement: "Sign in to Salaar",
      });
      if (authError) setError(authError.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
    setBusy(false);
  }

  async function handleSendCode(event: FormEvent) {
    event.preventDefault();
    resetFeedback();
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      setError("Enter a valid email address.");
      return;
    }

    setBusy(true);
    if (!supabase) {
      setMessage("Preview mode: use code 123456. Configure Supabase to send real email codes.");
      setStep("otp");
      setBusy(false);
      return;
    }

    const { error: authError } = await supabase.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: true },
    });
    if (authError) setError(authError.message);
    else {
      setMessage(`A six-digit code was sent to ${email}.`);
      setStep("otp");
    }
    setBusy(false);
  }

  async function handleVerifyCode(event: FormEvent) {
    event.preventDefault();
    resetFeedback();
    if (otp.length !== 6) {
      setError("Enter the complete six-digit code.");
      return;
    }

    setBusy(true);
    if (!supabase) {
      if (otp !== "123456") {
        setError("In preview mode, enter 123456.");
        setBusy(false);
        return;
      }
      setStep("profile");
      setBusy(false);
      return;
    }

    const { error: verifyError } = await supabase.auth.verifyOtp({ email, token: otp, type: "email" });
    if (verifyError) {
      setError(verifyError.message);
      setBusy(false);
      return;
    }
    const { data } = await supabase.auth.getSession();
    cleanAuthFromUrl();
    if (data.session?.user?.user_metadata?.onboarding_complete) {
      await onEnterApp?.(data.session.access_token);
      setBusy(false);
      return;
    }
    setStep("profile");
    setBusy(false);
  }

  function updateOtp(index: number, value: string) {
    const digit = value.replace(/\D/g, "").slice(-1);
    const chars = otp.padEnd(6, " ").split("");
    chars[index] = digit || " ";
    const next = chars.join("").replace(/\s/g, "").slice(0, 6);
    setOtp(next);
    if (digit && index < 5) otpRefs.current[index + 1]?.focus();
  }

  function handleOtpKey(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && !event.currentTarget.value && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  }

  function handleOtpPaste(event: ClipboardEvent<HTMLDivElement>) {
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;
    event.preventDefault();
    setOtp(pasted);
    otpRefs.current[Math.min(pasted.length, 5)]?.focus();
  }

  async function handleProfile(event: FormEvent) {
    event.preventDefault();
    resetFeedback();
    if (!firstName.trim() || !lastName.trim()) {
      setError("Tell Salaar your first and last name.");
      return;
    }

    setBusy(true);
    if (supabase) {
      const { error: updateError } = await supabase.auth.updateUser({
        data: {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          primary_use_case: useCase,
        },
      });
      if (updateError) {
        setError(updateError.message);
        setBusy(false);
        return;
      }
    }
    setStep("companion");
    setBusy(false);
  }

  async function handleActivate() {
    resetFeedback();
    setBusy(true);
    if (supabase) {
      const { error: updateError } = await supabase.auth.updateUser({
        data: {
          companion_profile: selectedCompanion,
          onboarding_complete: true,
        },
      });
      if (updateError) {
        setError(updateError.message);
        setBusy(false);
        return;
      }
    }
    setStep("complete");
    setBusy(false);
  }

  async function signOut() {
    if (supabase) await supabase.auth.signOut();
    setModalOpen(false);
    setStep("choice");
    setOtp("");
    setMessage("");
    setError("");
  }

  return (
    <div id="salar-landing" ref={shellRef}>
      <main className="site-shell cosmic-site">
        <div className="landing-liquid-stage" aria-hidden="true">
          <LiquidEther
            colors={['#5227FF', '#FF4FD8', '#54D9FF']}
            mouseForce={8}
            cursorSize={72}
            isViscous={false}
            iterationsViscous={8}
            iterationsPoisson={12}
            resolution={0.28}
            BFECC={false}
            autoDemo
            autoSpeed={0.22}
            autoIntensity={1.15}
            autoResumeDelay={4000}
          />
        </div>
        <div className="cosmic-vignette" aria-hidden="true" />
        <div className="cursor-aura" aria-hidden="true" />
        <div className="noise" aria-hidden="true" />
        {error && <div className="landing-notice" role="alert">{error}</div>}

        <header className="topbar cosmic-topbar">
          <a href="#top" className="brand" aria-label="Salaar home">
            <span className="cosmic-brand-mark"><i /><i /><i /></span>
            <span>SALAR</span>
          </a>
          <nav className={menuOpen ? "nav-links open" : "nav-links"} aria-label="Main navigation">
            <a href="#experience" onClick={() => setMenuOpen(false)}>Voice</a>
            <a href="#capabilities" onClick={() => setMenuOpen(false)}>Intelligence</a>
            <a href="#download" onClick={() => setMenuOpen(false)}>Get SALAR</a>
            <a href="#pricing" onClick={() => setMenuOpen(false)}>Pricing</a>
            <a href="#privacy" onClick={() => setMenuOpen(false)}>Privacy</a>
            {onEnterApp && <button className="enter-app-button" onClick={() => void handleEnterApp()} disabled={entryBusy}>{entryBusy ? "Checking…" : "Open SALAR"}</button>}
            <button className="nav-cta" onClick={launchSignup}>Meet SALAR <Icon.Arrow size={16} /></button>
          </nav>
          <button className="menu-button" onClick={() => setMenuOpen((value) => !value)} aria-label="Toggle navigation">
            {menuOpen ? <Icon.Close /> : <Icon.Menu />}
          </button>
        </header>

        <section className="cosmic-hero" id="top">
          <div className="cosmic-hero-copy">
            <div className="cosmic-kicker reveal-up"><span /> Private intelligence / continuously yours</div>
            <h1 className="reveal-up delay-1" aria-label="One intelligence that remembers">One intelligence<br />that <em>remembers.</em></h1>
            <div className="cosmic-verb-row reveal-up delay-2"><span>Reasons.</span><i /><span>Acts.</span></div>
            <p className="cosmic-lede reveal-up delay-2">SALAR turns your conversations, context, and connected world into forward motion&mdash;one private intelligence that grows with you.</p>
            <div className="cosmic-actions reveal-up delay-3">
              <button className="primary-button" onClick={launchSignup}>Meet your SALAR <Icon.Arrow /></button>
              <a className="cosmic-text-link" href="#experience">Enter the intelligence <span>&darr;</span></a>
            </div>
          </div>
          <div className="cosmic-hero-index" aria-hidden="true"><span>00</span><i /><span>03</span></div>
          <div className="cosmic-scroll-cue" aria-hidden="true"><span>Scroll to evolve</span><i /></div>
        </section>

        <section className="cosmic-chapter voice-chapter" id="experience" data-reveal>
          <div className="chapter-copy">
            <span className="chapter-index">01 / Live presence</span>
            <h2>Voice-first companion.</h2>
            <p>Speak naturally. SALAR listens, understands the context behind your words, and stays with the thread from thought to action.</p>
            <div className="voice-status"><i /><span>Listening across your context</span><b>LIVE</b></div>
          </div>
          <div className="chapter-rail" aria-hidden="true"><span>Natural voice</span><span>Continuous context</span><span>Instant action</span></div>
        </section>

        <section className="cosmic-chapter command-chapter" id="capabilities" data-reveal>
          <div className="chapter-copy">
            <span className="chapter-index">02 / Connected intelligence</span>
            <h2>Your private command center.</h2>
            <p>Memory, knowledge, calendar, tasks, automations, and connected devices move as one system&mdash;with you in control.</p>
            <div className="command-nodes" aria-label="Connected SALAR capabilities">
              <span>Memory</span><span>Knowledge</span><span>Calendar</span><span>Tasks</span><span>Devices</span><span>Automations</span>
            </div>
          </div>
        </section>

        <section className="cosmic-trust" id="privacy" data-reveal>
          <span className="chapter-index">03 / Private by architecture</span>
          <h2>Your world stays yours.</h2>
          <p>Explicit permissions. Editable memory. Connections you can inspect and revoke. SALAR is designed around your control.</p>
          <div className="trust-spectrum"><span><Icon.Shield /> Permission-based</span><span><Icon.Check /> Memory controls</span><span><Icon.Orbit /> Cross-device</span></div>
        </section>

        {false && <div className="legacy-marketing" aria-hidden="true">
        <section className="hero" id="legacy-top">
          <div className="hero-copy">
            <div className="eyebrow reveal-up"><span className="eyebrow-dot" /> A personal intelligence, built around you</div>
            <h1 className="reveal-up delay-1">Meet the AI that<br /><span>moves life forward.</span></h1>
            <p className="hero-lede reveal-up delay-2">
              Salaar is your private personal AI companion—one intelligent presence that understands your world, helps you decide and turns intention into action.
            </p>
            <div className="hero-actions reveal-up delay-3">
              <button className="primary-button" onClick={launchSignup}>Get your companion <Icon.Arrow /></button>
              <a className="text-button" href="#experience">See how it works <span>↓</span></a>
            </div>
            <div className="trust-row reveal-up delay-4">
              <span><Icon.Shield size={17} /> Privacy-first</span>
              <span><Icon.Spark size={17} /> Personal from day one</span>
              <span><Icon.Orbit size={17} /> Available across devices</span>
            </div>
          </div>

          <div className="hero-visual" aria-label="Animated Salaar intelligence core">
            <div className="hero-glow" />
            <div className="orbit orbit-one"><i /><i /><i /></div>
            <div className="orbit orbit-two"><i /><i /></div>
            <div className="orbit orbit-three"><i /><i /><i /></div>
            <div className="core-wrap">
              <div className="core-halo" />
              <div className="core">
                <div className="core-liquid" />
                <span>S</span>
              </div>
            </div>
            <div className="floating-card card-one">
              <span className="mini-icon"><Icon.Check size={15} /></span>
              <div><small>Today</small><strong>Morning plan ready</strong></div>
            </div>
            <div className="floating-card card-two">
              <span className="pulse-dot" />
              <div><small>Salaar is thinking</small><strong>3 priorities found</strong></div>
            </div>
            <div className="floating-card card-three">
              <span className="mini-icon cyan"><Icon.Spark size={15} /></span>
              <div><small>Creative mode</small><strong>New concept drafted</strong></div>
            </div>
          </div>
        </section>

        <section className="marquee" aria-label="Salaar capabilities">
          <div className="marquee-track">
            {["THINK WITH YOU", "PLAN WITH YOU", "CREATE WITH YOU", "REMEMBER FOR YOU", "ACT FOR YOU", "THINK WITH YOU", "PLAN WITH YOU", "CREATE WITH YOU"].map((item, index) => (
              <span key={`${item}-${index}`}>{item}<i>✦</i></span>
            ))}
          </div>
        </section>

        <section className="experience section" id="legacy-experience">
          <div className="section-heading" data-reveal>
            <span className="section-kicker">A new kind of relationship</span>
            <h2>Not another app.<br /><em>Your other mind.</em></h2>
            <p>Salaar develops context, recognizes patterns and stays close to the things you care about—without making your digital life feel more complicated.</p>
          </div>

          <div className="experience-stage" data-reveal>
            <div className="conversation-panel glass-panel">
              <div className="panel-top"><span>Live conversation</span><span className="online"><i /> Salaar online</span></div>
              <div className="chat-flow">
                <div className="message user-message">I have too much on my plate today.</div>
                <div className="message ai-message">
                  <span className="ai-avatar">S</span>
                  <div>
                    <strong>Let’s make it lighter.</strong>
                    <p>I found three things that truly need your attention. I can organize the rest around them.</p>
                    <div className="suggestion-chips"><span>Build my plan</span><span>Move low priorities</span></div>
                  </div>
                </div>
              </div>
              <div className="composer"><span>Ask Salaar anything...</span><button aria-label="Send"><Icon.Arrow /></button></div>
            </div>

            <div className="context-stack">
              <div className="context-card glass-panel context-primary">
                <div className="context-icon"><Icon.Brain /></div>
                <span className="context-label">Personal context</span>
                <h3>It remembers what matters.</h3>
                <p>Your preferences, projects and patterns become a useful private context—not a trail of disconnected chats.</p>
                <div className="memory-visual"><i /><i /><i /><i /><i /><i /></div>
              </div>
              <div className="context-card glass-panel context-mini">
                <div><span className="status-orb" /><small>Companion state</small><strong>Focused with you</strong></div>
                <div className="wave"><i /><i /><i /><i /><i /><i /><i /><i /></div>
              </div>
            </div>
          </div>
        </section>

        <section className="capabilities section" id="legacy-capabilities">
          <div className="section-heading centered" data-reveal>
            <span className="section-kicker">One companion. Many roles.</span>
            <h2>Intelligence that fits<br /><em>the moment.</em></h2>
          </div>
          <div className="capability-grid">
            {capabilities.map((item, index) => (
              <article className="capability-card" data-reveal key={item.title} style={{ "--delay": `${index * 100}ms` } as CSSProperties}>
                <div className="capability-number">0{index + 1}</div>
                <div className="capability-icon">{item.icon}</div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <span className="capability-line" />
              </article>
            ))}
          </div>
        </section>

        <section className="privacy section" id="legacy-privacy">
          <div className="privacy-visual" data-reveal>
            <div className="shield-rings"><i /><i /><i /></div>
            <div className="shield-core"><Icon.Shield size={52} /></div>
            <div className="privacy-pill p-one">Encrypted</div>
            <div className="privacy-pill p-two">Permission-based</div>
            <div className="privacy-pill p-three">You control memory</div>
          </div>
          <div className="privacy-copy" data-reveal>
            <span className="section-kicker">Trust is the foundation</span>
            <h2>Your life is personal.<br /><em>Salaar keeps it that way.</em></h2>
            <p>Privacy is not a switch hidden in settings. It is designed into how Salaar remembers, connects and takes action.</p>
            <div className="privacy-points">
              <span><Icon.Check /> Clear permissions for every connection</span>
              <span><Icon.Check /> Transparent, editable personal memory</span>
              <span><Icon.Check /> Delete or disconnect whenever you choose</span>
            </div>
          </div>
        </section>

        </div>}

        <section className="download-section section" id="download" data-reveal>
          <div className="download-heading">
            <span className="chapter-index">04 / Available everywhere</span>
            <h2>SALAR, closer<br />to your world.</h2>
            <p>Install the complete SALAR experience on Windows. Your conversations, memory, Live voice, and connected tools stay in sync with salaar.cloud.</p>
          </div>
          <div className="platform-grid" aria-label="SALAR app availability">
            <article className="platform-card platform-ready">
              <div className="platform-top"><span className="platform-icon">WIN</span><span className="platform-status available">Available now</span></div>
              <h3>Windows</h3>
              <p>Native desktop app for Windows 10 and 11. Installs for your account without administrator access.</p>
              <a className="platform-download" href="/downloads/SALAR-Setup.exe" download>Download for Windows <Icon.Arrow size={16} /></a>
              <small>64-bit · SALAR Desktop 1.0</small>
            </article>
            {[
              ["macOS", "MAC"],
              ["iOS", "IOS"],
              ["Android", "AND"],
            ].map(([platform, mark]) => (
              <article className="platform-card platform-future" key={platform}>
                <div className="platform-top"><span className="platform-icon">{mark}</span><span className="platform-status">Coming soon</span></div>
                <h3>{platform}</h3>
                <p>The same private SALAR intelligence, designed for {platform}.</p>
              </article>
            ))}
          </div>
        </section>

        <section className="pricing section cosmic-pricing" id="pricing" data-reveal>
          <span className="section-kicker reveal-up">Simple, transparent pricing</span>
          <h2 className="reveal-up delay-1">One companion. <br /><span>Plan that fits your life.</span></h2>
          <p className="pricing-lede reveal-up delay-2">
            Start free. Unlock Pro when Salaar becomes your everyday chief of staff.
          </p>

          <div className="pricing-grid">
            <GlareHover className="glare-price-wrap">
              <PriceCard
                name="Free"
                price="$0"
                sub="Forever free while we build in the open."
                features={["Full web + mobile companion", "Local & encrypted memory", "5 devices", "Standard models", "Community support"]}
                priceId="price_free"
                busyId={pricingBusyId}
                choosing={choosingPriceId === "price_free"}
                onCheckout={handleCheckout}
                onPickMethod={handleCheckout}
                featured={false}
              />
            </GlareHover>
            <GlareHover className="glare-price-wrap">
              <PriceCard
                name="Pro"
                price="$12"
                period="/mo"
                sub="Billed monthly at $12. Cancel anytime."
                features={["Everything in Free", "Advanced agents & automations", "Priority models", "Unlimited devices", "Priority support"]}
                priceId="price_pro"
                busyId={pricingBusyId}
                choosing={choosingPriceId === "price_pro"}
                onCheckout={handleCheckout}
                onPickMethod={handleCheckout}
                featured={true}
              />
            </GlareHover>
            <GlareHover className="glare-price-wrap">
              <PriceCard
                name="Team"
                price="$24"
                period="/mo"
                sub="For small teams and families (up to 5 seats)."
                features={["Everything in Pro", "Shared workspace", "Team tasks", "Group calendar sync", "Dedicated onboarding"]}
                priceId="price_team"
                busyId={pricingBusyId}
                choosing={choosingPriceId === "price_team"}
                onCheckout={handleCheckout}
                onPickMethod={handleCheckout}
                featured={false}
              />
            </GlareHover>
          </div>

          {pricingError && <p className="pricing-error">{pricingError}</p>}

          <p className="pricing-note">Salaar is free during early access. You'll only be charged when Pro features ship. Pay with crypto (wallet) or card (PayPal).</p>
        </section>

        <section className="final-cta section" data-reveal>
          <div className="cta-orb orb-left" /><div className="cta-orb orb-right" />
          <span className="section-kicker light">Your companion is ready</span>
          <h2>Make space for a more<br /><em>intentional life.</em></h2>
          <p>Start with Salaar today. Set up your personal companion in a few thoughtful steps.</p>
          <button className="primary-button light-button" onClick={launchSignup}>Get Salaar Personal AI Companion <Icon.Arrow /></button>
          <small>No password required. Start free.</small>
        </section>

        <footer>
          <a href="#top" className="brand footer-brand"><span className="brand-mark">S</span><span>SALAAR</span></a>
          <p>Personal intelligence for a life in motion.</p>
          <div className="footer-links">
            <a href="#privacy">Privacy</a><a href="#capabilities">Capabilities</a><a href="#download">Get SALAR</a>
            {onEnterApp && <button onClick={() => void handleEnterApp()} disabled={entryBusy}>Enter SALAR app</button>}
            <button onClick={launchSignup}>Create account</button>
          </div>
          <span className="copyright">© {new Date().getFullYear()} Salaar AI</span>
        </footer>

        {modalOpen && (
          <div className="modal-backdrop modal-fade-in" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setModalOpen(false)}>
            <section className="auth-modal modal-scale-in" role="dialog" aria-modal="true" aria-labelledby="auth-title">
              <div className="modal-progress"><span style={{ width: `${progress}%` }} /></div>
              <button className="modal-close" onClick={() => setModalOpen(false)} aria-label="Close registration"><Icon.Close /></button>
              <div className="modal-brand"><span className="brand-mark">S</span><span>SALAAR</span></div>

               {step === "choice" && (
                 <div className="auth-view auth-choice view-transition">
                   <span className="auth-kicker">Begin your journey</span>
                   <h2 id="auth-title">Meet your personal<br />AI companion.</h2>
                   <p>Create your Salaar account to begin a private, personalized experience.</p>
                   <div className="social-grid">
                     <button onClick={() => handleOAuth("google")} disabled={busy}><GoogleIcon /><span>Continue with Google</span></button>
                     <button onClick={() => handleOAuth("github")} disabled={busy}><GitHubIcon /><span>Continue with GitHub</span></button>
                     <button onClick={() => handleOAuth("azure")} disabled={busy}><MicrosoftIcon /><span>Continue with Microsoft</span></button>
                     <button onClick={handleWalletSignIn} disabled={busy}><WalletIcon /><span>Continue with wallet</span></button>
                   </div>
                   <div className="divider"><span>or</span></div>
                   <button className="email-auth-button" onClick={() => { resetFeedback(); setStep("email"); }}><Icon.Mail /><span>Continue with email</span><Icon.Arrow /></button>
                   {error && <div className="form-error">{error}</div>}
                   {!isSupabaseConfigured && <div className="demo-badge">Preview mode active</div>}
                   <p className="legal-copy">By continuing, you agree to the Terms and acknowledge the Privacy Policy.</p>
                 </div>
               )}

               {step === "email" && (
                 <form className="auth-view view-transition" onSubmit={handleSendCode}>
                   <button type="button" className="back-button" onClick={() => setStep("choice")}>← Back</button>
                   <span className="auth-kicker">Email registration</span>
                   <h2 id="auth-title">Where should we<br />send your code?</h2>
                   <p>No password to remember. We’ll email you a secure six-digit sign-in code.</p>
                   <label className="field-label" htmlFor="email">Email address</label>
                   <div className="input-shell"><Icon.Mail size={19} /><input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" autoFocus /></div>
                   {error && <div className="form-error">{error}</div>}
                   <button className="modal-primary" type="submit" disabled={busy}>{busy ? "Sending…" : "Send my code"}<Icon.Arrow /></button>
                 </form>
               )}

               {step === "otp" && (
                 <form className="auth-view view-transition" onSubmit={handleVerifyCode}>
                   <button type="button" className="back-button" onClick={() => setStep("email")}>← Change email</button>
                  <span className="auth-kicker">Verify your email</span>
                  <h2 id="auth-title">Enter your<br />six-digit code.</h2>
                  <p>We sent it to <strong>{email}</strong>. The code may take a moment to arrive.</p>
                  {message && <div className="form-message">{message}</div>}
                  <div className="otp-row" onPaste={handleOtpPaste}>
                    {Array.from({ length: 6 }).map((_, index) => (
                      <input
                        key={index}
                        ref={(element) => { otpRefs.current[index] = element; }}
                        inputMode="numeric"
                        autoComplete={index === 0 ? "one-time-code" : "off"}
                        maxLength={1}
                        value={otp[index] ?? ""}
                        onChange={(event) => updateOtp(index, event.target.value)}
                        onKeyDown={(event) => handleOtpKey(index, event)}
                        aria-label={`Code digit ${index + 1}`}
                      />
                    ))}
                  </div>
                  {error && <div className="form-error">{error}</div>}
                  <button className="modal-primary" type="submit" disabled={busy}>{busy ? "Verifying…" : "Verify and continue"}<Icon.Arrow /></button>
                  <button className="resend-button" type="button" onClick={(event) => handleSendCode(event as unknown as FormEvent)}>Send a new code</button>
                </form>
              )}

               {step === "profile" && (
                 <form className="auth-view view-transition" onSubmit={handleProfile}>
                  <span className="auth-kicker">Make it personal</span>
                  <h2 id="auth-title">What should Salaar<br />call you?</h2>
                  <p>A few details help your companion greet you and shape its first recommendations.</p>
                  <div className="two-fields">
                    <label><span>First name</span><input value={firstName} onChange={(event) => setFirstName(event.target.value)} placeholder="First name" autoFocus /></label>
                    <label><span>Last name</span><input value={lastName} onChange={(event) => setLastName(event.target.value)} placeholder="Last name" /></label>
                  </div>
                  <label className="select-label"><span>What would you like help with first?</span>
                    <select value={useCase} onChange={(event) => setUseCase(event.target.value)}>
                      <option>Everyday productivity</option>
                      <option>Work and business</option>
                      <option>Creative projects</option>
                      <option>Learning and research</option>
                      <option>Personal organization</option>
                    </select>
                  </label>
                  {error && <div className="form-error">{error}</div>}
                  {message && <div className="form-message">{message}</div>}
                  <button className="modal-primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Create my profile"}<Icon.Arrow /></button>
                </form>
              )}

               {step === "companion" && (
                 <div className="auth-view companion-view view-transition">
                  <span className="auth-kicker">Choose a starting style</span>
                  <h2 id="auth-title">How should Salaar<br />show up for you?</h2>
                  <p>You can change this later. Every style still has access to Salaar’s full intelligence.</p>
                  <div className="companion-options">
                    {companions.map((companion) => (
                      <button key={companion.id} className={selectedCompanion === companion.id ? "companion-option selected" : "companion-option"} onClick={() => setSelectedCompanion(companion.id)}>
                        <span className="selection-dot"><i /></span>
                        <span className="companion-copy"><small>{companion.eyebrow}</small><strong>{companion.name}</strong><p>{companion.copy}</p><span className="trait-row">{companion.traits.map((trait) => <i key={trait}>{trait}</i>)}</span></span>
                      </button>
                    ))}
                  </div>
                  {error && <div className="form-error">{error}</div>}
                  <button className="modal-primary" onClick={handleActivate} disabled={busy}>{busy ? "Activating…" : "Get Salaar Personal AI Companion"}<Icon.Arrow /></button>
                </div>
              )}

                {step === "complete" && (
                  <div className="auth-view complete-view view-transition">
                   <div className="success-core"><span>S</span><i /><i /></div>
                   <span className="auth-kicker">Companion activated</span>
                   <h2 id="auth-title">Welcome to Salaar{firstName ? `, ${firstName}` : ""}.</h2>
                   <p>Your personal AI companion is ready. The next screen can be connected to your Salaar chat, desktop app or onboarding dashboard.</p>
                   <div className="ready-card"><span className="status-orb" /><div><small>Selected companion</small><strong>{companions.find((item) => item.id === selectedCompanion)?.name}</strong></div><Icon.Check /></div>
                   <button className="modal-primary" onClick={() => setOnboardingStarted(true)}>Enter Salaar <Icon.Arrow /></button>
                   <button className="resend-button" onClick={signOut}>Sign out</button>
                  </div>
                )}
             </section>

             {onboardingStarted && (
                <OnboardingWizard onComplete={() => { setModalOpen(false); void onEnterApp?.(); }} />
             )}
           </div>
         )}
      </main>
    </div>
  );
}
