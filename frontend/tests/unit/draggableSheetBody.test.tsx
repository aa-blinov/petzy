import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { DEFAULT_SHEET_MAX_HEIGHT, DraggableSheetBody } from '../../src/components/DraggableSheetBody'

afterEach(cleanup)

describe('лист, который тянут вниз', () => {
  it('без своей высоты не растёт за экран: длинный список прокручивается внутри', () => {
    render(
      <DraggableSheetBody visible onClose={() => undefined} label="Все прививки и обработки">
        <p>список</p>
      </DraggableSheetBody>,
    )
    expect(screen.getByRole('dialog').style.maxHeight).toBe(DEFAULT_SHEET_MAX_HEIGHT)
  })

  it('своя высота листа важнее общей', () => {
    render(
      <DraggableSheetBody visible onClose={() => undefined} maxHeight="75vh" label="Фильтр">
        <p>список</p>
      </DraggableSheetBody>,
    )
    expect(screen.getByRole('dialog').style.maxHeight).toBe('75vh')
  })
})
