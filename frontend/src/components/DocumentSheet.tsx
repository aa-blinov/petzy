import { useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Camera, FileUp } from 'lucide-react';

import { Fab } from './Fab';
import { setPendingDocumentFile } from '../utils/pendingDocumentFile';
import { documentsService, SCAN_EXTENSIONS } from '../services/documents.service';
import { AddSheet, AddTile, AddTiles } from './AddSheet';

/** The round «+» of the Documents list. */
export function DocumentFab({ onOpen }: { onOpen: () => void }) {
  return <Fab label="Добавить документ" onClick={onOpen} popup />;
}

/**
 * The shared «Что добавить?» sheet: the camera and the files one tap away. The person takes the picture (or picks the file) first, and the form
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
      <AddSheet visible={visible} onClose={onClose} maxHeight="85vh">
        <AddTiles single>
          <AddTile label="Сфотографировать" icon={Camera} color="cyan" onClick={() => cameraInput.current?.click()} />
          <AddTile label="Фото, PDF или архив из файлов" icon={FileUp} color="blue" onClick={() => fileInput.current?.click()} />
        </AddTiles>
      </AddSheet>
    </>
  );
}
