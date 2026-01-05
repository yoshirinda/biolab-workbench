import { ProjectNode, Sequence, ApiResult } from './types/biolab';

const API_BASE = '/api'; // Vite proxy should handle this, or Flask static serving

export async function fetchProjectTree(): Promise<ProjectNode[]> {
  const response = await fetch('/api/projects');
  if (!response.ok) throw new Error('Failed to fetch project tree');
  const result: ApiResult<ProjectNode[]> = await response.json();
  if (!result.success && !Array.isArray(result)) throw new Error(result.message || 'Failed to fetch projects');
  // Handle both direct array (legacy) and wrapped response
  return Array.isArray(result) ? result : (result.data || []);
}

export async function createProject(name: string, parentPath?: string) {
  const response = await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, parent_path: parentPath }),
  });
  if (!response.ok) throw new Error('Failed to create project');
  return response.json();
}

export async function createFolder(name: string, parentPath?: string) {
  const response = await fetch('/api/projects/folders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, parent_path: parentPath }),
  });
  if (!response.ok) throw new Error('Failed to create folder');
  return response.json();
}

export async function getProjectDetails(path: string): Promise<ProjectNode> {
  // path needs to be URL encoded properly because it contains slashes
  // But wait, flask path param <path:project_path> handles slashes if not encoded? 
  // Let's use the path as is, assuming client paths are safe.
  const response = await fetch(`/api/projects/${path}`);
  if (!response.ok) throw new Error('Failed to fetch project details');
  const result = await response.json();
  // Unwrap if necessary
  return result.success !== undefined ? result.data : result;
}

export async function uploadSequences(file: File, projectPath: string) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('project_path', projectPath);

  const response = await fetch('/api/sequences/import', {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || 'Failed to upload sequences');
  }
  return response.json();
}

export async function deleteProject(path: string) {
  const response = await fetch(`/api/projects/${path}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete project');
  return response.json();
}

export async function deleteSequence(projectPath: string, sequenceId: string) {
  const response = await fetch(`/api/sequences/${projectPath}/${sequenceId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete sequence');
  return response.json();
}

export async function moveSequence(sourcePath: string, sequenceId: string, destPath: string) {
  const response = await fetch('/api/sequences/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_project: sourcePath,
      sequence_id: sequenceId,
      dest_project: destPath
    }),
  });
  if (!response.ok) throw new Error('Failed to move sequence');
  return response.json();
}

export async function copySequence(sourcePath: string, sequenceId: string, destPath: string) {
  const response = await fetch('/api/sequences/copy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_project: sourcePath,
      sequence_id: sequenceId,
      dest_project: destPath
    }),
  });
  if (!response.ok) throw new Error('Failed to copy sequence');
  return response.json();
}

export async function getFeatureTypes() {
  const response = await fetch('/api/sequences/features/types');
  if (!response.ok) throw new Error('Failed to fetch feature types');
  return response.json();
}

export async function addFeature(projectPath: string, sequenceId: string, feature: any) {
  const response = await fetch(`/api/sequences/${projectPath}/${sequenceId}/features`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(feature),
  });
  if (!response.ok) throw new Error('Failed to add feature');
  return response.json();
}

export async function updateFeature(projectPath: string, sequenceId: string, featureId: string, feature: any) {
  const response = await fetch(`/api/sequences/${projectPath}/${sequenceId}/features/${featureId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(feature),
  });
  if (!response.ok) throw new Error('Failed to update feature');
  return response.json();
}

export async function deleteFeature(projectPath: string, sequenceId: string, featureId: string) {
  const response = await fetch(`/api/sequences/${projectPath}/${sequenceId}/features/${featureId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete feature');
  return response.json();
}
