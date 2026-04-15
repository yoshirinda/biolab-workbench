import { ProjectNode, Sequence, ApiResult } from './types/biolab';

const API_BASE = '/api'; // Vite proxy should handle this, or Flask static serving
const PROJECT_TREE_CACHE_TTL_MS = 15_000;
const PROJECT_DETAIL_CACHE_TTL_MS = 20_000;

type ApiError = Error & { status?: number; code?: string };
type TimedCache<T> = { value: T; ts: number };

let projectTreeCache: TimedCache<ProjectNode[]> | null = null;
let projectTreeInFlight: Promise<ProjectNode[]> | null = null;
const projectDetailCache = new Map<string, TimedCache<ProjectNode>>();
const projectDetailInFlight = new Map<string, Promise<ProjectNode>>();

function encodePathSegments(path: string): string {
  return path
    .split('/')
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join('/');
}

async function buildApiError(response: Response, fallback: string): Promise<ApiError> {
  let payload: any = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  const error = new Error(
    payload?.error?.message || payload?.message || fallback
  ) as ApiError;
  error.status = response.status;
  error.code = payload?.error?.code;
  return error;
}

function isCacheFresh<T>(cache: TimedCache<T> | null, ttlMs: number): cache is TimedCache<T> {
  return !!cache && (Date.now() - cache.ts) < ttlMs;
}

function invalidateProjectSubtree(path: string) {
  for (const key of Array.from(projectDetailCache.keys())) {
    if (key === path || key.startsWith(`${path}/`)) {
      projectDetailCache.delete(key);
    }
  }
  for (const key of Array.from(projectDetailInFlight.keys())) {
    if (key === path || key.startsWith(`${path}/`)) {
      projectDetailInFlight.delete(key);
    }
  }
}

export function invalidateProjectTreeCache() {
  projectTreeCache = null;
  projectTreeInFlight = null;
}

export function invalidateProjectDetailsCache(path?: string) {
  if (!path) {
    projectDetailCache.clear();
    projectDetailInFlight.clear();
    return;
  }
  invalidateProjectSubtree(path);
}

export function invalidateAllProjectCaches() {
  invalidateProjectTreeCache();
  invalidateProjectDetailsCache();
}

export async function fetchProjectTree(options?: { forceRefresh?: boolean }): Promise<ProjectNode[]> {
  const forceRefresh = !!options?.forceRefresh;
  if (!forceRefresh && isCacheFresh(projectTreeCache, PROJECT_TREE_CACHE_TTL_MS)) {
    return projectTreeCache.value;
  }
  if (!forceRefresh && projectTreeInFlight) {
    return projectTreeInFlight;
  }

  projectTreeInFlight = (async () => {
    const response = await fetch('/api/projects');
    if (!response.ok) throw await buildApiError(response, 'Failed to fetch project tree');
    const result: ApiResult<ProjectNode[]> = await response.json();
    if (!result.success && !Array.isArray(result)) throw new Error(result.message || 'Failed to fetch projects');
    const data = Array.isArray(result) ? result : (result.data || []);
    projectTreeCache = { value: data, ts: Date.now() };
    return data;
  })();

  try {
    return await projectTreeInFlight;
  } finally {
    projectTreeInFlight = null;
  }
}

export async function createProject(name: string, parentPath?: string) {
  const response = await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, parent_path: parentPath }),
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to create project');
  const payload = await response.json();
  invalidateAllProjectCaches();
  return payload;
}

export async function createFolder(name: string, parentPath?: string) {
  const response = await fetch('/api/projects/folders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, parent_path: parentPath }),
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to create folder');
  const payload = await response.json();
  invalidateAllProjectCaches();
  return payload;
}

export async function getProjectDetails(path: string, options?: { forceRefresh?: boolean }): Promise<ProjectNode> {
  const forceRefresh = !!options?.forceRefresh;
  const cacheKey = path;
  if (!forceRefresh) {
    const cached = projectDetailCache.get(cacheKey);
    if (cached && (Date.now() - cached.ts) < PROJECT_DETAIL_CACHE_TTL_MS) {
      return cached.value;
    }
    const inflight = projectDetailInFlight.get(cacheKey);
    if (inflight) return inflight;
  }

  const encodedPath = encodePathSegments(path);
  const requestPromise = (async () => {
    const response = await fetch(`/api/projects/${encodedPath}`);
    if (!response.ok) throw await buildApiError(response, 'Failed to fetch project details');
    const result = await response.json();
    const data = result.success !== undefined ? result.data : result;
    projectDetailCache.set(cacheKey, { value: data, ts: Date.now() });
    return data;
  })();
  projectDetailInFlight.set(cacheKey, requestPromise);

  try {
    return await requestPromise;
  } finally {
    projectDetailInFlight.delete(cacheKey);
  }
}

export async function uploadSequences(file: File, projectPath: string) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('project_path', projectPath);

  const response = await fetch('/api/sequences/import', {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to upload sequences');
  const payload = await response.json();
  invalidateProjectTreeCache();
  invalidateProjectDetailsCache(projectPath);
  return payload;
}

export async function deleteProject(path: string) {
  const encodedPath = encodePathSegments(path);
  const response = await fetch(`/api/projects/${encodedPath}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to delete project');
  const payload = await response.json();
  invalidateProjectTreeCache();
  invalidateProjectDetailsCache(path);
  return payload;
}

export async function deleteSequence(projectPath: string, sequenceId: string) {
  const encodedProjectPath = encodePathSegments(projectPath);
  const encodedSequenceId = encodeURIComponent(sequenceId);
  const response = await fetch(`/api/sequences/${encodedProjectPath}/${encodedSequenceId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to delete sequence');
  const payload = await response.json();
  invalidateProjectTreeCache();
  invalidateProjectDetailsCache(projectPath);
  return payload;
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
  if (!response.ok) throw await buildApiError(response, 'Failed to move sequence');
  const payload = await response.json();
  invalidateProjectTreeCache();
  invalidateProjectDetailsCache(sourcePath);
  invalidateProjectDetailsCache(destPath);
  return payload;
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
  if (!response.ok) throw await buildApiError(response, 'Failed to copy sequence');
  const payload = await response.json();
  invalidateProjectTreeCache();
  invalidateProjectDetailsCache(sourcePath);
  invalidateProjectDetailsCache(destPath);
  return payload;
}

export async function getFeatureTypes() {
  const response = await fetch('/api/sequences/features/types');
  if (!response.ok) throw await buildApiError(response, 'Failed to fetch feature types');
  return response.json();
}

export async function addFeature(projectPath: string, sequenceId: string, feature: any) {
  const encodedProjectPath = encodePathSegments(projectPath);
  const encodedSequenceId = encodeURIComponent(sequenceId);
  const response = await fetch(`/api/sequences/${encodedProjectPath}/${encodedSequenceId}/features`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(feature),
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to add feature');
  const payload = await response.json();
  invalidateProjectDetailsCache(projectPath);
  return payload;
}

export async function updateFeature(projectPath: string, sequenceId: string, featureId: string, feature: any) {
  const encodedProjectPath = encodePathSegments(projectPath);
  const encodedSequenceId = encodeURIComponent(sequenceId);
  const encodedFeatureId = encodeURIComponent(featureId);
  const response = await fetch(`/api/sequences/${encodedProjectPath}/${encodedSequenceId}/features/${encodedFeatureId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(feature),
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to update feature');
  const payload = await response.json();
  invalidateProjectDetailsCache(projectPath);
  return payload;
}

export async function deleteFeature(projectPath: string, sequenceId: string, featureId: string) {
  const encodedProjectPath = encodePathSegments(projectPath);
  const encodedSequenceId = encodeURIComponent(sequenceId);
  const encodedFeatureId = encodeURIComponent(featureId);
  const response = await fetch(`/api/sequences/${encodedProjectPath}/${encodedSequenceId}/features/${encodedFeatureId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to delete feature');
  const payload = await response.json();
  invalidateProjectDetailsCache(projectPath);
  return payload;
}

export async function updateSequenceAnnotation(projectPath: string, sequenceId: string, annotation: string) {
  const encodedProjectPath = encodePathSegments(projectPath);
  const encodedSequenceId = encodeURIComponent(sequenceId);
  const response = await fetch(`/sequence/projects/${encodedProjectPath}/sequences/${encodedSequenceId}/annotation`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ annotation }),
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to update annotation');
  const payload = await response.json();
  invalidateProjectDetailsCache(projectPath);
  return payload;
}

export async function updateSequence(projectPath: string, sequenceId: string, updates: { description?: string; sequence?: string }) {
  const encodedProjectPath = encodePathSegments(projectPath);
  const encodedSequenceId = encodeURIComponent(sequenceId);
  const response = await fetch(`/sequence/projects/${encodedProjectPath}/sequences/${encodedSequenceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!response.ok) throw await buildApiError(response, 'Failed to update sequence');
  const payload = await response.json();
  invalidateProjectDetailsCache(projectPath);
  return payload;
}
