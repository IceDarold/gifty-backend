export type LiveSnapshotItem = {
  channel: string;
  seq: number;
  data: Record<string, unknown>;
};

export type LiveSnapshotResponse = {
  items: LiveSnapshotItem[];
};

export type LiveUpdateMessage = {
  type: "update" | "snapshot" | "heartbeat" | "error";
  channel?: string;
  seq?: number;
  data?: Record<string, unknown>;
  req_id?: string;
  code?: string;
  message?: string;
};
