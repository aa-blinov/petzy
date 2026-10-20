import { afterEach, describe, expect, it, vi } from 'vitest'
import { goBack, hasPreviousAppPage, isMainTabPath, MAIN_TAB_PATHS, medicalCardPetId } from '../../src/utils/navigation'

describe('medicalCardPetId', () => {
  it('находит питомца по адресу медкарты', () => {
    expect(medicalCardPetId('/pets/p1/medical-card')).toBe('p1')
  })

  it('находит питомца с закрывающим слэшем', () => {
    expect(medicalCardPetId('/pets/p1/medical-card/')).toBe('p1')
  })

  it('на экране профиля питомца не находит', () => {
    expect(medicalCardPetId('/pets/p1/medical-profile')).toBeNull()
  })

  it('на экране внутри медкарты не находит', () => {
    expect(medicalCardPetId('/pets/p1/medical-card/records')).toBeNull()
  })

  it('на пустом адресе не находит', () => {
    expect(medicalCardPetId('/')).toBeNull()
  })
})

describe('isMainTabPath', () => {
  it('нижние вкладки считаются главными', () => {
    for (const path of MAIN_TAB_PATHS) {
      expect(isMainTabPath(path)).toBe(true)
    }
  })

  it('медкарта питомца тоже вкладка', () => {
    expect(isMainTabPath('/pets/p1/medical-card')).toBe(true)
  })

  it('экран поверх вкладки не вкладка', () => {
    expect(isMainTabPath('/pets/p1')).toBe(false)
    expect(isMainTabPath('/form/weight')).toBe(false)
  })
})

describe('hasPreviousAppPage', () => {
  afterEach(() => {
    window.history.replaceState(null, '', '/')
  })

  it('на первой странице приложения назад некуда', () => {
    window.history.replaceState(null, '', '/')
    expect(hasPreviousAppPage()).toBe(false)
  })

  it('после перехода внутри приложения есть куда назад', () => {
    window.history.replaceState({ idx: 1 }, '', '/')
    expect(hasPreviousAppPage()).toBe(true)
  })
})

describe('goBack', () => {
  afterEach(() => {
    window.history.replaceState(null, '', '/')
  })

  it('возвращается назад, когда есть своя предыдущая страница', () => {
    window.history.replaceState({ idx: 2 }, '', '/')
    const navigate = vi.fn()
    goBack(navigate as never, '/pets')
    expect(navigate).toHaveBeenCalledWith(-1)
  })

  it('с запасным адресом, когда предыдущей страницы нет', () => {
    window.history.replaceState(null, '', '/')
    const navigate = vi.fn()
    goBack(navigate as never, '/pets')
    expect(navigate).toHaveBeenCalledWith('/pets', { replace: true })
  })
})
