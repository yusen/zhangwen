/** Explicit UI action only. This contract is never supplied as a model tool. */
export interface OpenProjectFolderInput {
  checkpointHash: string;
  /** Optional absolute path; otherwise a verified cached path or native chooser. */
  path?: string;
  chooseAgain?: boolean;
}
export type OpenProjectFolderResult = { status: 'canceled' } | {
  status: 'requested'; path: string; name: string;
};

export interface ManagedProjectFolder { path: string; name: string; checkpointHash: string | null; mainHash: string | null }
export interface ManagedFolderFile { path: string[]; sha256: string; content: string }
export interface ManagedFolderSync { snapshot: string; expectedCheckpointHash: string | null; files: ManagedFolderFile[] }
