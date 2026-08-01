type DocumentViewerProps = {
  path: string | null;
  content: string | null;
  loading: boolean;
};

export function DocumentViewer({ path, content, loading }: DocumentViewerProps) {
  return (
    <section className="document-viewer" aria-label="文档查看器">
      <div className="panel-heading">
        <h2>文档查看器</h2>
        {path ? <span>{path}</span> : null}
      </div>
      {loading ? <p className="empty-text">正在加载文档</p> : null}
      {!loading && !path ? <p className="empty-text">请选择一个工作区文件</p> : null}
      {!loading && path && content !== null ? <pre className="document-content">{content}</pre> : null}
    </section>
  );
}
