import { useEffect, useRef, useState } from "react";

type StepState = "idle" | "active" | "done" | "error";

const STEP_COMMANDS = [
  { id: "install_copy_files", label: "Extracting SALAR engine" },
  { id: "install_register_protocol", label: "Registering browser hand-off" },
  { id: "install_create_shortcuts", label: "Creating your shortcuts" },
  { id: "install_finish", label: "Igniting your companion" },
];

function tauriInvoke(cmd: string) {
  const invoke = (window as any).__TAURI_INTERNALS__?.invoke
    || (window as any).__TAURI__?.core?.invoke
    || (window as any).__TAURI__?.invoke;
  if (!invoke) throw new Error("Tauri runtime unavailable");
  return invoke(cmd);
}

export function SetupScreen({ variant = "install" }: { variant?: "install" | "update" }) {
  const isUpdate = variant === "update";
  const [states, setStates] = useState<StepState[]>(() => STEP_COMMANDS.map(() => "idle"));
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    (async () => {
      for (let i = 0; i < STEP_COMMANDS.length; i++) {
        setStates(prev => prev.map((s, idx) => (idx === i ? "active" : s)));
        try {
          await tauriInvoke(STEP_COMMANDS[i].id);
          setStates(prev => prev.map((s, idx) => (idx === i ? "done" : s)));
          await new Promise(resolve => setTimeout(resolve, 420));
        } catch (err) {
          startedRef.current = false;
          setStates(prev => prev.map((s, idx) => (idx === i ? "error" : s)));
          setError(String(err));
          return;
        }
      }
      // install_finish launches the installed copy and exits this process.
    })();

    return () => { startedRef.current = false; };
  }, [attempt]);

  function retry() {
    setError("");
    setStates(STEP_COMMANDS.map(() => "idle"));
    setAttempt(a => a + 1);
  }

  return (
    <div className="setup-screen">
      <div className="setup-orb" aria-hidden="true">
        <span className="ring r1" />
        <span className="ring r2" />
        <span className="core" />
      </div>
      <h1 className="setup-wordmark">SALAAR</h1>
      <p className="setup-sub">{isUpdate ? "Updating your personal intelligence" : "Preparing your personal intelligence"}</p>

      <ol className="setup-steps">
        {STEP_COMMANDS.map((step, i) => (
          <li key={step.id} className={`setup-step ${states[i]}`}>
            <span className="dot">{states[i] === "done" ? "✓" : ""}</span>
            <span>{step.label}</span>
          </li>
        ))}
      </ol>

      {error && (
        <div className="setup-error" role="alert">
          <strong>Setup hit a snag.</strong> {error}
          <br />
          <button className="setup-retry" onClick={retry}>Try again</button>
        </div>
      )}
    </div>
  );
}
