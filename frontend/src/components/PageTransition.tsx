import React, { useRef, createRef, type ReactNode, type RefObject } from 'react';
import { useLocation, useNavigationType, Routes } from 'react-router-dom';
import { CSSTransition, TransitionGroup } from 'react-transition-group';
import './PageTransition.css';

interface PageTransitionProps {
  children: ReactNode;
}

export function PageTransition({ children }: PageTransitionProps) {
  const location = useLocation();
  const navigationType = useNavigationType();
  
  // Используем Map для хранения refs для каждого пути
  const nodeRefs = useRef(new Map<string, RefObject<HTMLDivElement | null>>());
  const currentKey = location.pathname;

  // Получаем или создаем ref для текущего пути
  let nodeRef = nodeRefs.current.get(currentKey);
  if (!nodeRef) {
    nodeRef = createRef<HTMLDivElement>();
    nodeRefs.current.set(currentKey, nodeRef);
  }

  // Определяем тип анимации: 'page' (обычная) или 'page-back' (обратная)
  // POP обычно означает переход назад (кнопка Back или navigate(-1))
  const animationClass = navigationType === 'POP' ? 'page-back' : 'page';

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <TransitionGroup 
        component={null}
        childFactory={(child) => {
          // Важно: применяем правильный класс анимации к уходящему компоненту
          return React.cloneElement(child as React.ReactElement<any>, {
            classNames: animationClass
          });
        }}
      >
        <CSSTransition
          key={currentKey}
          nodeRef={nodeRef}
          timeout={300}
          classNames={animationClass}
          unmountOnExit
        >
          <div ref={nodeRef} className="page-wrapper">
            <Routes location={location}>
              {children}
            </Routes>
          </div>
        </CSSTransition>
      </TransitionGroup>
    </div>
  );
}
