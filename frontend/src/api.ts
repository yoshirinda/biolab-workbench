export type WorkflowRun = {
  id: string;
  workflow: string;
  status: string;
  created_at: string;
  title?: string;
  result_dir?: string;
};

export async function fetchRuns(): Promise<WorkflowRun[]> {
  const response = await fetch('/runs');
  if (!response.ok) {
    throw new Error(`Failed to fetch runs: ${response.status}`);
  }
  return response.json();
}
