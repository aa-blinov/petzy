import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { dismissOnboarding, hadPets, isOnboardingDismissed, rememberHavingPets, resumeIndex } from '../../src/utils/onboarding'

// Node держит свой localStorage и он пустой, поэтому хранилище страницы берём у jsdom
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _localStorage?: Storage })._localStorage
  Object.defineProperty(window, 'localStorage', { value: jsdomStorage, configurable: true, writable: true })
})

describe('onboarding', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('не отправляет в знакомство, пока его не отключили', () => {
    expect(isOnboardingDismissed('anna')).toBe(false)
  })

  it('отключённое знакомство не показывается', () => {
    dismissOnboarding('anna')
    expect(isOnboardingDismissed('anna')).toBe(true)
  })

  it('у другого человека знакомство остаётся', () => {
    dismissOnboarding('anna')
    expect(isOnboardingDismissed('petr')).toBe(false)
  })

  it('без имени ключ свой', () => {
    dismissOnboarding(null)
    expect(isOnboardingDismissed(null)).toBe(true)
    expect(isOnboardingDismissed('anna')).toBe(false)
  })

  it('при запрещённом хранилище знакомство показывается', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage blocked')
    })
    expect(isOnboardingDismissed('anna')).toBe(false)
  })

  it('при запрещённом хранилище отключение не падает', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage blocked')
    })
    expect(() => dismissOnboarding('anna')).not.toThrow()
  })
})

describe('hadPets', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('до того, как питомец был, не считается', () => {
    expect(hadPets('anna')).toBe(false)
  })

  it('после питомца считается', () => {
    rememberHavingPets('anna')
    expect(hadPets('anna')).toBe(true)
  })

  it('у другого человека не считается', () => {
    rememberHavingPets('anna')
    expect(hadPets('petr')).toBe(false)
  })

  it('без имени ключ свой', () => {
    rememberHavingPets(null)
    expect(hadPets(null)).toBe(true)
  })

  it('при запрещённом хранилище не считается', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage blocked')
    })
    expect(hadPets('anna')).toBe(false)
  })
})

describe('resumeIndex', () => {
  const steps = ['welcome', 'diary', 'family', 'species', 'name', 'notify', 'done']
  const resumable = ['welcome', 'diary', 'family', 'species', 'name']

  it('comes back to the step the person was on, the name step included', () => {
    expect(resumeIndex(steps, 'diary', resumable)).toBe(1)
    expect(resumeIndex(steps, 'name', resumable)).toBe(4)
  })
  it('starts over when nothing, something unknown or a step after the pet was saved', () => {
    expect(resumeIndex(steps, null, resumable)).toBe(0)
    expect(resumeIndex(steps, '3', resumable)).toBe(0)
    expect(resumeIndex(steps, 'notify', resumable)).toBe(0)
  })
  it('starts over when the step is not in this flow', () => {
    expect(resumeIndex(['welcome', 'diary', 'family'], 'name', resumable)).toBe(0)
  })
})
