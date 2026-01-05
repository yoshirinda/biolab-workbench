import React from 'react';
import { Tree, Dropdown, MenuProps } from 'antd';
import { FolderOutlined, FileTextOutlined, CopyOutlined, ScissorOutlined, SnippetsOutlined, DeleteOutlined } from '@ant-design/icons';
import { FileNode } from '../types/biolab';

const { DirectoryTree } = Tree;

interface ProjectTreeProps {
  treeData: FileNode[];
  selectedKeys: string[];
  onSelect: (keys: React.Key[], info: any) => void;
  onContextMenuClick: (key: string, node: FileNode) => void;
  onDrop?: (info: any) => void;
}

const ProjectTree: React.FC<ProjectTreeProps> = ({ treeData, selectedKeys, onSelect, onContextMenuClick, onDrop }) => {
  
  const renderTreeNodes = (data: FileNode[]): any[] =>
    data.map((item) => ({
      title: item.title,
      key: item.key,
      isLeaf: !item.isFolder,
      icon: item.isFolder ? <FolderOutlined /> : <FileTextOutlined />,
      children: item.children ? renderTreeNodes(item.children) : [],
      data: item // Pass full object for context menu
    }));

  const handleRightClick = ({ event, node }: any) => {
    // Select the node on right click
    // onSelect([node.key], { node, selected: true }); 
    // Actually standard behavior is separate selection, but for UX let's auto-select
  };

  return (
    <div style={{ height: '100%', overflow: 'auto' }} onContextMenu={(e) => e.preventDefault()}>
      <DirectoryTree
        multiple
        selectedKeys={selectedKeys}
        onSelect={onSelect}
        onRightClick={handleRightClick}
        treeData={renderTreeNodes(treeData)}
        draggable
        onDrop={onDrop}
        titleRender={(nodeData: any) => {
            return (
                <Dropdown 
                    menu={{ 
                        items: [
                            { label: 'Copy', key: 'copy', icon: <CopyOutlined />, onClick: () => onContextMenuClick('copy', nodeData.data) },
                            { label: 'Cut', key: 'cut', icon: <ScissorOutlined />, onClick: () => onContextMenuClick('cut', nodeData.data) },
                            { label: 'Paste', key: 'paste', icon: <SnippetsOutlined />, onClick: () => onContextMenuClick('paste', nodeData.data), disabled: !nodeData.data.isFolder }, // Only paste into folders
                            { type: 'divider' },
                            { label: 'Rename', key: 'rename', onClick: () => onContextMenuClick('rename', nodeData.data) },
                            { label: 'Delete', key: 'delete', icon: <DeleteOutlined />, danger: true, onClick: () => onContextMenuClick('delete', nodeData.data) },
                        ] 
                    }} 
                    trigger={['contextMenu']}
                >
                    <span>{nodeData.title}</span>
                </Dropdown>
            );
        }}
      />
    </div>
  );
};

export default ProjectTree;