import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

type Drafts = typeof import('../../src/utils/sessionDraft')

// Node держит свой localStorage и он пустой, поэтому хранилище страницы берём у jsdom
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _localStorage?: Storage })._localStorage
  Object.defineProperty(window, 'localStorage', { value: jsdomStorage, configurable: true, writable: true })
})

/** Свежий модуль: выбранный питомец не должен переходить из теста в тест */
async function load(): Promise<Drafts> {
  const { vi } = await import('vitest')
  vi.resetModules()
  return (await import('../../src/utils/sessionDraft')) as Drafts
}

const OWNER = { path: '/form/weight', petId: 'p1' }

describe('черновики формы', () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
  })

  it('черновик возвращается на свой экран', async () => {
    const mod = await load()
    mod.registerDraftProvider(() => ({ owner: OWNER, values: { weight: 12.4 } }))
    mod.stashDraftsBeforeSignOut()
    expect(mod.takeDraft(OWNER)).toEqual({ weight: 12.4 })
  })

  it('черновик забирают один раз', async () => {
    const mod = await load()
    mod.registerDraftProvider(() => ({ owner: OWNER, values: { weight: 12.4 } }))
    mod.stashDraftsBeforeSignOut()
    mod.takeDraft(OWNER)
    expect(mod.takeDraft(OWNER)).toBeNull()
  })

  it('черновик другого питомца не отдают', async () => {
    const mod = await load()
    mod.registerDraftProvider(() => ({ owner: OWNER, values: { weight: 12.4 } }))
    mod.stashDraftsBeforeSignOut()
    expect(mod.takeDraft({ path: OWNER.path, petId: 'p2' })).toBeNull()
  })

  it('черновик другого экрана не отдают', async () => {
    const mod = await load()
    mod.registerDraftProvider(() => ({ owner: OWNER, values: { weight: 12.4 } }))
    mod.stashDraftsBeforeSignOut()
    expect(mod.takeDraft({ path: '/form/food', petId: 'p1' })).toBeNull()
  })

  it('форма, которой нечего писать, не оставляет черновика', async () => {
    const mod = await load()
    mod.registerDraftProvider(() => undefined)
    mod.stashDraftsBeforeSignOut()
    expect(mod.takeDraft(OWNER)).toBeNull()
  })

  it('пустая форма не мешает записать черновик другой', async () => {
    const mod = await load()
    mod.registerDraftProvider(() => undefined)
    mod.registerDraftProvider(() => ({ owner: OWNER, values: { weight: 12.4 } }))
    mod.stashDraftsBeforeSignOut()
    expect(mod.takeDraft(OWNER)).toEqual({ weight: 12.4 })
  })

  it('старый черновик не отдают', async () => {
    const mod = await load()
    sessionStorage.setItem(
      'petzy:sessionDrafts',
      JSON.stringify({ 'p1 /form/weight': { path: OWNER.path, petId: 'p1', values: { weight: 12.4 }, savedAt: Date.now() - 13 * 60 * 60 * 1000 } }),
    )
    expect(mod.takeDraft(OWNER)).toBeNull()
  })

  it('свежий черновик отдают', async () => {
    const mod = await load()
    sessionStorage.setItem(
      'petzy:sessionDrafts',
      JSON.stringify({ 'p1 /form/weight': { path: OWNER.path, petId: 'p1', values: { weight: 12.4 }, savedAt: Date.now() } }),
    )
    expect(mod.takeDraft(OWNER)).toEqual({ weight: 12.4 })
  })

  it('сломанное хранилище не отдаёт черновик', async () => {
    const mod = await load()
    sessionStorage.setItem('petzy:sessionDrafts', 'не json')
    expect(mod.takeDraft(OWNER)).toBeNull()
  })
})

describe('черновик прежней версии', () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
  })

  it('переходит на свой экран', async () => {
    const mod = await load()
    sessionStorage.setItem('petzy:sessionDraft', JSON.stringify({ path: '/form/weight', values: { weight: 12.4 } }))
    expect(mod.takeDraft(OWNER)).toEqual({ weight: 12.4 })
  })

  it('после перехода старой записи не остаётся', async () => {
    const mod = await load()
    sessionStorage.setItem('petzy:sessionDraft', JSON.stringify({ path: '/form/weight', values: { weight: 12.4 } }))
    mod.takeDraft(OWNER)
    expect(sessionStorage.getItem('petzy:sessionDraft')).toBeNull()
  })

  it('чужого экрана не трогает', async () => {
    const mod = await load()
    sessionStorage.setItem('petzy:sessionDraft', JSON.stringify({ path: '/form/food', values: { food: 200 } }))
    expect(mod.takeDraft(OWNER)).toBeNull()
    expect(sessionStorage.getItem('petzy:sessionDraft')).not.toBeNull()
  })
})

describe('выбранный питомец', () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
  })

  it('после входа питомец выбран снова', async () => {
    const mod = await load()
    localStorage.setItem('petzy:auth:username', 'anna')
    localStorage.setItem('selectedPetId', JSON.stringify('p1'))
    localStorage.setItem('selectedPetName', JSON.stringify('Рекс'))
    mod.stashPetBeforeSignOut()
    localStorage.removeItem('selectedPetId')
    mod.resumePetFor('anna')
    expect(localStorage.getItem('selectedPetId')).toBe('"p1"')
    expect(localStorage.getItem('selectedPetName')).toBe('"Рекс"')
  })

  it('другому человеку питомец не достаётся', async () => {
    const mod = await load()
    localStorage.setItem('petzy:auth:username', 'anna')
    localStorage.setItem('selectedPetId', JSON.stringify('p1'))
    mod.stashPetBeforeSignOut()
    localStorage.removeItem('selectedPetId')
    mod.resumePetFor('petr')
    expect(localStorage.getItem('selectedPetId')).toBeNull()
  })

  it('логин сверяется без учёта регистра', async () => {
    const mod = await load()
    localStorage.setItem('petzy:auth:username', 'anna')
    localStorage.setItem('selectedPetId', JSON.stringify('p1'))
    mod.stashPetBeforeSignOut()
    localStorage.removeItem('selectedPetId')
    mod.resumePetFor('ANNA')
    expect(localStorage.getItem('selectedPetId')).toBe('"p1"')
  })

  it('без входа питомца не выбрать', async () => {
    const mod = await load()
    localStorage.setItem('selectedPetId', JSON.stringify('p1'))
    mod.stashPetBeforeSignOut()
    localStorage.removeItem('selectedPetId')
    mod.resumePetFor('anna')
    expect(localStorage.getItem('selectedPetId')).toBeNull()
  })

  it('старый выбор питомца не отдают', async () => {
    vi.useFakeTimers()
    try {
      vi.setSystemTime(new Date('2026-01-01T10:00:00Z'))
      const mod = await load()
      localStorage.setItem('petzy:auth:username', 'anna')
      localStorage.setItem('selectedPetId', JSON.stringify('p1'))
      mod.stashPetBeforeSignOut()
      localStorage.removeItem('selectedPetId')
      vi.setSystemTime(new Date('2026-01-02T10:00:00Z'))
      mod.resumePetFor('anna')
      expect(localStorage.getItem('selectedPetId')).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('выбор отдают только один раз', async () => {
    const mod = await load()
    localStorage.setItem('petzy:auth:username', 'anna')
    localStorage.setItem('selectedPetId', JSON.stringify('p1'))
    mod.stashPetBeforeSignOut()
    localStorage.removeItem('selectedPetId')
    mod.resumePetFor('anna')
    localStorage.removeItem('selectedPetId')
    mod.resumePetFor('anna')
    expect(localStorage.getItem('selectedPetId')).toBeNull()
  })
})

describe('черновики при выходе из аккаунта', () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
  })

  it('сохраняет черновики всех экранов, а не только первого', async () => {
    const mod = await load()
    const first = { path: '/form/weight', petId: 'p1' }
    const second = { path: '/form/food', petId: 'p2' }
    mod.registerDraftProvider(() => ({ owner: first, values: { weight: 12.4 } }))
    mod.registerDraftProvider(() => ({ owner: second, values: { food: 'корм' } }))
    mod.stashDraftsBeforeSignOut()
    expect(mod.takeDraft(first)).toEqual({ weight: 12.4 })
    expect(mod.takeDraft(second)).toEqual({ food: 'корм' })
  })
})
