import { createElement, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Popup } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import { Archive, Camera, FileUp, type LucideIcon } from 'lucide-react';

import { useFabAway } from '../hooks/useFabAway';
import { pastelColorMap } from '../utils/constants';
import { setPendingDocumentFile } from '../utils/pendingDocumentFile';
import { DraggableSheetBody } from './DraggableSheetBody';
import './RecordSheet.css';

/** The round «+» of the Documents list, the same as the feed's and the card's: in a portal, stepping aside on a scroll down. */
export function DocumentFab({ onOpen }: { onOpen: () => void }) {
  const away = useFabAway();
  return createPortal(
    <button type="button" className={`app-fab${away ? ' app-fab--away' : ''}`} aria-label="Добавить документ" aria-haspopup="dialog" onClick={onOpen}>
      <AddOutline fontSize={28} aria-hidden />
    </button>,
    document.body,
  );
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
 * that opens has it already, so that it only has to be named. Archives of scans have their own way in.
 */
export function DocumentSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const cameraInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const picked = (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setPendingDocumentFile(file);
    onClose();
    navigate('/documents/new');
  };

  const openScans = () => {
    onClose();
    navigate('/documents/new?category=imaging');
  };

  return (
    <>
      {/* Two inputs: one opens the camera, the other the gallery and files. Outside the sheet, so they are there when it is shut. */}
      <input ref={cameraInput} type="file" accept="image/*" capture="environment" hidden aria-label="Сфотографировать" onChange={(e) => { picked(e.target.files); e.target.value = ''; }} />
      <input ref={fileInput} type="file" accept="image/*,application/pdf" hidden aria-label="Выбрать файл" onChange={(e) => { picked(e.target.files); e.target.value = ''; }} />
      <Popup visible={visible} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
        <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="85vh" label="Что добавить">
          <h2 className="recsheet__title">Что добавить?</h2>
          <div className="recsheet__grid" style={{ marginTop: 'var(--spacing-lg)', gridTemplateColumns: '1fr' }}>
            <Tile label="Сфотографировать" icon={Camera} color="cyan" onClick={() => cameraInput.current?.click()} />
            <Tile label="Фото или PDF из файлов" icon={FileUp} color="blue" onClick={() => fileInput.current?.click()} />
            <Tile label="Снимки МРТ, КТ, архив" icon={Archive} color="purple" onClick={openScans} />
          </div>
        </DraggableSheetBody>
      </Popup>
    </>
  );
}
