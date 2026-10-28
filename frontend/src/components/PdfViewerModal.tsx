"use client";

type Props = {
  url: string;
  title: string;
  onClose: () => void;
};

export function PdfViewerModal({ url, title, onClose }: Props) {
  return (
    <div className="pdf-modal-overlay" role="dialog" aria-modal="true">
      <div className="pdf-modal">
        <div className="pdf-modal-header">
          <strong>{title}</strong>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            Cerrar
          </button>
        </div>
        <iframe src={url} title={title} className="pdf-frame" />
      </div>
    </div>
  );
}
