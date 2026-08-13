export type CosmicScene = "intelligence" | "voice" | "command";

export type CosmicSceneState = {
  scene: CosmicScene;
  localProgress: number;
};

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

export function getCosmicScene(progress: number): CosmicSceneState {
  const value = clamp01(progress);
  if (value < 1 / 3) return { scene: "intelligence", localProgress: value * 3 };
  if (value < 2 / 3) return { scene: "voice", localProgress: (value - 1 / 3) * 3 };
  return { scene: "command", localProgress: (value - 2 / 3) * 3 };
}

export function getParticleBudget({ width, height, dpr }: { width: number; height: number; dpr: number }): number {
  const areaScale = Math.sqrt((Math.max(320, width) * Math.max(568, height)) / (390 * 844));
  const densityScale = Math.min(1.3, Math.max(1, dpr / 2));
  return Math.round(Math.min(2200, Math.max(900, 950 * areaScale * densityScale)));
}
