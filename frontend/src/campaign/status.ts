import type { CampaignAction, CampaignStatus } from "../types"

/*
 * A campaign's statuses and what each allows, as backend/app/campaigns.py's ACTIONS has them:
 * change them together. The server still decides: a stale screen offering a button gets a 409.
 */

export const STATUS_LABEL: Record<CampaignStatus, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  piloting: "Piloting",
  awaiting_approval: "Awaiting approval",
  running: "Running",
  ended: "Ended",
  cancelled: "Cancelled",
}

/** The badge per status: live ones stand out, finished ones fade. */
export const STATUS_BADGE: Record<CampaignStatus, string> = {
  draft: "bg-field text-ink",
  scheduled: "bg-field text-ink",
  piloting: "bg-star/15 text-star-ink",
  awaiting_approval: "bg-star/15 text-star-ink",
  running: "bg-positive/15 text-positive",
  ended: "bg-field text-ink-muted",
  cancelled: "bg-field text-ink-muted",
}

/** The statuses each action is allowed from. */
export const ACTIONS: Record<CampaignAction, CampaignStatus[]> = {
  launch: ["draft"],
  approve: ["awaiting_approval"],
  end: ["piloting", "running"],
  cancel: ["scheduled", "piloting", "awaiting_approval", "running"],
}

/** Everything a campaign's detail can offer: the actions, and editing or deleting a draft. */
export type Move = CampaignAction | "edit" | "delete"

export const MOVE_LABEL: Record<Move, string> = {
  edit: "Edit",
  launch: "Launch",
  delete: "Delete",
  approve: "Approve",
  end: "End now",
  cancel: "Cancel",
}

/** The moves that cannot be taken back ask first. Launch and Approve do not: they only move a campaign on. */
export const CONFIRM: Partial<Record<Move, string>> = {
  delete: "Delete this draft? This can't be undone.",
  cancel: "Cancel this campaign? This can't be undone.",
  end: "End this campaign now?",
}

/** The order the buttons show in. */
const ORDER: Move[] = ["edit", "launch", "delete", "approve", "end", "cancel"]

/** The moves a campaign with this status allows. Only a draft can be edited or deleted. */
export function actionsFor(status: CampaignStatus): Move[] {
  return ORDER.filter((move) => (move === "edit" || move === "delete" ? status === "draft" : ACTIONS[move].includes(status)))
}

/** What a stale screen is told when the server refused a move because the campaign had moved on. */
export const changedMessage = (status: CampaignStatus) => `This campaign changed. Status is now ${STATUS_LABEL[status]}.`
