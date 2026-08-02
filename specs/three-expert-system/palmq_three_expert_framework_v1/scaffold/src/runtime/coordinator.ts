import type { PendingItem, PendingPriority } from "../domain/types";

const PRIORITY_WEIGHT: Record<PendingPriority, number> = {
  safety: 600,
  blocking: 500,
  conflict: 400,
  confirmation: 300,
  missing_input: 200,
  normal: 100,
};

export function selectHighlightedPendingItem(
  candidates: PendingItem[],
): PendingItem | undefined {
  const open = candidates.filter((item) => item.status === "open");

  return open
    .slice()
    .sort((a, b) => {
      const priorityDiff =
        PRIORITY_WEIGHT[b.priority] - PRIORITY_WEIGHT[a.priority];
      if (priorityDiff !== 0) return priorityDiff;

      const expertImpactDiff =
        b.affectedExperts.length - a.affectedExperts.length;
      if (expertImpactDiff !== 0) return expertImpactDiff;

      return a.createdAt.localeCompare(b.createdAt);
    })[0];
}

export function enforceSingleHighlightedItem(
  candidates: PendingItem[],
): PendingItem[] {
  const selected = selectHighlightedPendingItem(candidates);
  return candidates.map((item) => ({
    ...item,
    isHighlighted: selected?.id === item.id,
  }));
}
