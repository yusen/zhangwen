import type { HardwareElectricalProps } from "@zhangwen/contracts";

export function operatingVoltageLabel(electrical: HardwareElectricalProps): string {
  const minimum = electrical.voltageMin ?? electrical.voltage;
  const maximum = electrical.voltageMax ?? electrical.voltage;
  if (minimum === maximum) return `${electrical.voltage}V`;
  return `${minimum}–${maximum}V（推荐 ${electrical.voltage}V）`;
}

export function supplyRailsLabel(electrical: HardwareElectricalProps): string | null {
  const rails = electrical.supplyVoltages ?? [];
  return rails.length > 0 ? rails.map((value) => `${value}V`).join(" / ") : null;
}
