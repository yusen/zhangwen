import type { HardwareSkillDetail } from "@zhangwen/contracts";

export const HARDWARE_SKILL_UPDATED_EVENT = "zhangwen:hardware-skill-updated";

export function publishHardwareSkillUpdated(skill: HardwareSkillDetail): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<HardwareSkillDetail>(HARDWARE_SKILL_UPDATED_EVENT, {
      detail: skill,
    }),
  );
}

export function subscribeHardwareSkillUpdated(
  listener: (skill: HardwareSkillDetail) => void,
): () => void {
  if (typeof window === "undefined") return () => undefined;
  const handle = (event: Event) => {
    listener((event as CustomEvent<HardwareSkillDetail>).detail);
  };
  window.addEventListener(HARDWARE_SKILL_UPDATED_EVENT, handle);
  return () => window.removeEventListener(HARDWARE_SKILL_UPDATED_EVENT, handle);
}
