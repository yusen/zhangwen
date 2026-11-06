import type { ProgramRunSubmission, Project, UploadReceipt } from '../../../packages/contracts/src/platform';

/** Derive evidence for the displayed version; no independent device state machine. */
export function currentExecution(project: Project | null, dirty: boolean, receipt: UploadReceipt | null | undefined, run: ProgramRunSubmission | null) {
  const upload = !dirty && project && receipt?.projectId === project.id && receipt.revision === project.revision && receipt.sha256 === project.checksum ? receipt : null;
  const submitted = upload && run?.projectId === project?.id && run?.revision === upload.revision && run?.sha256 === upload.sha256
    && run?.boardId === project?.boardId && Date.parse(run.submittedAt) >= Date.parse(upload.verifiedAt) ? run : null;
  return { upload, submitted };
}
