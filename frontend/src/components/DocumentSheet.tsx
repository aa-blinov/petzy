import { createElement, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Popup } from 'antd-mobile';
import { Camera, FileUp, type LucideIcon } from 'lucide-react';

import { Fab } from './Fab';
import { pastelColorMap } from '../utils/constants';
import { setPendingDocumentFile } from '../utils/pendingDocumentFile';
import { documentsService, SCAN_EXTENSIONS } from '../services/documents.service';
import { DraggableSheetBody } from './DraggableSheetBody';
import './RecordSheet.css';

/** The round «+» of the Documents list. */
export function DocumentFab({ onOpen }: { onOpen: () => void }) {
  return <Fab label="Добавить документ" onClick={onOpen} popup />;
}

function Tile({ label, icon, color, onClick }: { label: string; icon: LucideIcon; color: string; onClick: () => void }) {
  return (
    <button type="button" className="recsheet__tile tap-feedback" style={{ background: pastelColorMap[color] }} onClick={onClick}>
      <span className="recsheet__icon" aria-hidden>
        {createElement(icon, { size: 20, strokeWidth: 2 })}
      </span>
      <span className="recsheet__label">{label}</span>
    </button>
  );
}

/**
 * «Что добавить?»: the camera and the files one tap away. The person takes the picture (or picks the file) first, and the form
 * that opens has it already, so that it only has to be named. An archive of scans is one of the files: the form files it under
 * «Снимки» by itself.
 */
export function DocumentSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const cameraInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  // The same answer the form reads (one cache entry): the picker offers archives only where the server takes them.
  const { data: storageStatus } = useQuery({
    queryKey: ['documents-storage'],
    queryFn: () => documentsService.getStorageStatus(),
    staleTime: 5 * 60_000,
  });
  const fileAccept = storageStatus?.scans_enabled ? `image/*,application/pdf,${SCAN_EXTENSIONS.join(',')}` : 'image/*,application/pdf';

  const picked = (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setPendingDocumentFile(file);
    onClose();
    navigate('/documents/new');
  };

  return (
    <>
      {/* Two inputs: one opens the camera, the other the gallery and files. Outside the sheet, so they are there when it is shut. */}
      <input ref={cameraInput} type="file" accept="image/*" capture="environment" hidden aria-label="Сфотографировать" onChange={(e) => { picked(e.target.files); e.target.value = ''; }} />
      <input ref={fileInput} type="file" accept={fileAccept} hidden aria-label="Выбрать файл" onChange={(e) => { picked(e.target.files); e.target.value = ''; }} />
      <Popup visible={visible} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
        <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="85vh" label="Что добавить">
          <h2 className="recsheet__title">Что добавить?</h2>
          <div className="recsheet__grid" style={{ marginTop: 'var(--spacing-lg)', gridTemplateColumns: '1fr' }}>
            <Tile label="Сфотографировать" icon={Camera} color="cyan" onClick={() => cameraInput.current?.click()} />
            <Tile label="Фото, PDF или архив из файлов" icon={FileUp} color="blue" onClick={() => fileInput.current?.click()} />
          </div>
        </DraggableSheetBody>
      </Popup>
    </>
  );
}
