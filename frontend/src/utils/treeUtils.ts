import { FileNode } from '../types/biolab';
import { v4 as uuidv4 } from 'uuid';

/**
 * Deep clone a node and all its children, regenerating IDs.
 */
export const cloneNodeWithNewIds = (node: FileNode, newParentId: string | null): FileNode => {
  const newKey = uuidv4();
  
  // Clone data if exists
  let newData = undefined;
  if (node.data) {
    newData = {
      ...node.data,
      id: newKey, // Sync ID
      meta: {
        ...node.data.meta,
        created: new Date().toISOString()
      }
    };
  }

  const newNode: FileNode = {
    ...node,
    key: newKey,
    parentId: newParentId,
    data: newData,
    children: node.children ? node.children.map(child => cloneNodeWithNewIds(child, newKey)) : undefined
  };

  return newNode;
};

/**
 * Generate a unique name if conflict exists.
 * e.g., "pUC19" -> "pUC19 (Copy)" -> "pUC19 (Copy 2)"
 */
export const getUniqueName = (name: string, existingNames: Set<string>): string => {
  if (!existingNames.has(name)) return name;

  let baseName = name;
  let copyIndex = 1;
  
  // Check if it already ends with (Copy X)
  const match = name.match(/^(.*) \(Copy(?: (\d+))?\)$/);
  if (match) {
    baseName = match[1];
    copyIndex = match[2] ? parseInt(match[2]) + 1 : 2;
  } else {
    baseName = name;
    // Try "Name (Copy)" first
    const firstTry = `${baseName} (Copy)`;
    if (!existingNames.has(firstTry)) return firstTry;
    copyIndex = 2;
  }

  while (true) {
    const newName = `${baseName} (Copy ${copyIndex})`;
    if (!existingNames.has(newName)) return newName;
    copyIndex++;
  }
};

/**
 * Find a node by key in the tree
 */
export const findNode = (nodes: FileNode[], key: string): FileNode | null => {
  for (const node of nodes) {
    if (node.key === key) return node;
    if (node.children) {
      const found = findNode(node.children, key);
      if (found) return found;
    }
  }
  return null;
};

/**
 * Helper to update tree state immutably
 */
export const updateTree = (nodes: FileNode[], key: string, updater: (node: FileNode) => FileNode | null): FileNode[] => {
  return nodes.map(node => {
    if (node.key === key) {
      return updater(node);
    }
    if (node.children) {
      return {
        ...node,
        children: updateTree(node.children, key, updater)
      };
    }
    return node;
  }).filter(Boolean) as FileNode[]; // Remove nulls (deleted nodes)
};
