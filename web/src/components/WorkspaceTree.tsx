import { useState } from "react";

import type { FileNode } from "../api/types";

type WorkspaceTreeProps = {
  tree: FileNode[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
};

export function WorkspaceTree({ tree, selectedPath, onSelect }: WorkspaceTreeProps) {
  return (
    <section className="panel-section workspace-section" aria-label="工作区文件">
      <h2>工作区</h2>
      {tree.length === 0 ? (
        <p className="empty-text">暂无文件</p>
      ) : (
        <div className="tree-root">
          {tree.map((node) => (
            <TreeNode key={node.path} node={node} selectedPath={selectedPath} onSelect={onSelect} depth={0} />
          ))}
        </div>
      )}
    </section>
  );
}

type TreeNodeProps = {
  node: FileNode;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  depth: number;
};

function TreeNode({ node, selectedPath, onSelect, depth }: TreeNodeProps) {
  const [open, setOpen] = useState(false);
  const isDirectory = node.kind === "directory";
  const isSelected = selectedPath === node.path;

  return (
    <div>
      <button
        type="button"
        aria-label={node.name}
        className={isSelected ? "tree-item selected" : "tree-item"}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => {
          if (isDirectory) {
            setOpen((current) => !current);
          } else {
            onSelect(node.path);
          }
        }}
      >
        <span className="tree-icon">{isDirectory ? (open ? "v" : ">") : "-"}</span>
        <span>{node.name}</span>
      </button>
      {isDirectory && open
        ? node.children.map((child) => (
            <TreeNode key={child.path} node={child} selectedPath={selectedPath} onSelect={onSelect} depth={depth + 1} />
          ))
        : null}
    </div>
  );
}
