import { useState } from "react";

const steps = [
  {
    id: "welcome",
    title: "Welcome to Salaar",
    subtitle: "Your personal intelligence, built around you.",
    illustration: "✨",
  },
  {
    id: "context",
    title: "Connect your world",
    subtitle: "Bring tasks, schedules, and devices into one private space.",
    illustration: "🌍",
  },
  {
    id: "privacy",
    title: "Designed around privacy",
    subtitle: "Everything you share stays yours. Clear permissions, always in your control.",
    illustration: "🔒",
  },
  {
    id: "sample",
    title: "Try your first prompt",
    subtitle: "Ask Salaar to plan your day or organize your priorities.",
    illustration: "💡",
  },
  {
    id: "done",
    title: "You're ready",
    subtitle: "Your companion is activated. Let's get started.",
    illustration: "🚀",
  },
] as const;

const samplePrompts = [
  "Plan my ideal Tuesday morning routine",
  "What are the 3 most important things I should focus on today?",
  "Summarize the key points from my recent conversations",
];

export default function OnboardingWizard({
  onComplete,
}: {
  onComplete: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [email, setEmail] = useState("");

  const step = steps[index];
  const isLast = index === steps.length - 1;
  const progress = ((index) / (steps.length - 1)) * 100;

  function next() {
    if (isLast) onComplete();
    else setIndex(index + 1);
  }

  function back() {
    if (step.id === "sample") {
      if (!/^\S+@\S+\.\S+$/.test(email)) return;
      setIndex(index + 1);
      return;
    }
    setIndex((i) => Math.max(0, i - 1));
  }

  function renderBody() {
    switch (step.id) {
      case "welcome":
        return (
          <div className="onboard-body">
            <div className="onboard-illustration">{step.illustration}</div>
            <p className="onboard-text">
              SALAR is your private personal AI companion that understands your
              world, helps you decide, and turns intention into action.
            </p>
          </div>
        );
      case "context":
        return (
          <div className="onboard-body">
            <ul className="onboard-bullets">
              <li>Learns your habits, priorities, and working style</li>
              <li>Remembers what matters across devices</li>
              <li>Acts with clear permissions you control</li>
            </ul>
          </div>
        );
      case "privacy":
        return (
          <div className="onboard-body">
            <div className="onboard-illustration">{step.illustration}</div>
            <p className="onboard-text">
              End-to-end encryption. Editable memory. Transparent controls.
              Everything stays yours — nothing is sold.
            </p>
          </div>
        );
      case "sample":
        return (
          <div className="onboard-body">
            <p className="onboard-text">Here are some ways to start:</p>
            <ul className="onboard-prompts">
              {samplePrompts.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        );
      case "done":
        return (
          <div className="onboard-body">
            <div className="onboard-illustration">{step.illustration}</div>
            <p className="onboard-text">
              You can change your companion's style, connect integrations, or
              rename them anytime from Settings.
            </p>
          </div>
        );
      default:
        return null;
    }
  }

  return (
    <div className="onboarding-wizard">
      <div className="onboard-progress">
        <span style={{ width: `${progress}%` }} />
      </div>
      <div className="onboard-header">
        <div className="onboard-step">
          Step {index + 1} of {steps.length}
        </div>
        <h2 className="onboard-title">{step.title}</h2>
        {step.subtitle && <p className="onboard-subtitle">{step.subtitle}</p>}
      </div>

      {renderBody()}

      <div className="onboard-nav">
        {index > 0 && (
          <button
            className="onboard-back"
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
          >
            ← Back
          </button>
        )}
        <button className="onboard-next primary-button" onClick={next}>
          {isLast ? "Enter Salaar →" : "Continue"}
        </button>
      </div>

      <style>{`
        .onboarding-wizard { padding: 8px 0 18px; }
        .onboard-progress { height:3px; border-radius:2px; background:#ebe7f2; overflow:hidden; margin-bottom:22px; }
        .onboard-progress span { display:block; height:100%; width:0; border-radius:2px;
          transition:width .55s ease; background:linear-gradient(90deg,#6546df,#ac8df8,#57dbe8); }
        .onboard-step { font-size:11px; font-weight:700; letter-spacing:.12em; color:#777181; text-transform:uppercase; }
        .onboard-title { margin:10px 0 6px; font-size:34px; line-height:1.05; }
        .onboard-subtitle { margin:0 0 18px; color:#777181; font-size:14px; line-height:1.55; }
        .onboard-body { text-align:center; padding:10px 0 8px; }
        .onboard-illustration { font-size:46px; margin:14px 0; }
        .onboard-text { margin:0 auto; max-width:420px; color:#4a4656; font-size:14px; line-height:1.55; }
        .onboard-bullets, .onboard-prompts { text-align:left; max-width:380px; margin:12px auto; padding-left:20px; }
        .onboard-bullets li, .onboard-prompts li { margin:9px 0; font-size:14px; color:#4a4656; line-height:1.5; }
        .onboard-nav { display:flex; justify-content:space-between; margin-top:18px; }
        .onboard-back { height:42px; padding:0 18px; border:1px solid #e0d9f0; border-radius:12px; background:#f7f5ff; font-weight:600; color:#5b45b3; }
        .onboard-next { flex:1; margin-left:12px; }
        .onboard-back:hover { background:#ebe7f2; }
      `}</style>
    </div>
  );
}
